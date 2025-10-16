from datetime import datetime
from typing import Any, Literal, AsyncIterable
import logging

from pydantic import BaseModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)
memory = MemorySaver()


@tool
def get_time_now() -> dict[str, str]:
    """Returns the current system time in HH:MM:SS format."""
    return {"current_time": datetime.now().strftime("%H:%M:%S")}

class ResponseFormat(BaseModel):
    status: Literal["completed", "input_required", "error"]  # Structured status of the agent reply
    message: str                                              # The message that will be shown to the user


class TellTimeAgent:
    """
    LangChain ReAct agent that answers time-related queries.
    - Only uses the get_time_now tool
    - Responds based on structured format
    - Powered by Gemini Flash model
    """

    SYSTEM_INSTRUCTION = (
        "You are a specialized assistant for time-related queries. "
        "Use the 'get_time_now' tool when users ask for the current time to get the time in HH:MM:SS format. "
        "Convert this time to the requested format by the user on your own. You are allowed to do that"
    )

    RESPONSE_FORMAT_INSTRUCTION = (
        "Use 'completed' if the task is done, 'input_required' if clarification is needed, "
        "and 'error' if something fails. Always include a user-facing message."
    )

    def __init__(self):
        # Initialize the Gemini LLM model (fast variant)
        self.model = ChatGoogleGenerativeAI(model="gemini-2.0-flash")

        # Register the available tools for this agent
        self.tools = [get_time_now]

        # Create a complete ReAct-style agent graph using LangGraph
        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=(self.RESPONSE_FORMAT_INSTRUCTION, ResponseFormat),
        )
        
    async def stream(self, query: str, session_id: str) -> AsyncIterable[dict[str, Any]]:
        """
        This function is used when a user sends a message to the agent.
        Instead of waiting for a single response, it gives us updates as they happen.

        - 'query' is the user’s question or command (e.g., "What time is it?")
        - 'session_id' is a unique ID for this user's interaction (to maintain context)
        - It yields updates such as "Looking up time...", "Processing...", and the final result.
        """
         # Set up a configuration that ties this request to a session.
        # LangGraph needs a session/thread ID to track the conversation.
        config: RunnableConfig = {
            "configurable": {
                "thread_id": session_id  # Unique ID to separate one user conversation from another
            }
        }

        # This is the input format LangGraph expects: a list of messages.
        # Each message is a tuple: ("who", "what they said").
        # Here, we send just one message from the "user".
        inputs = {"messages": [("user", query)]}

        # Begin streaming the agent's thinking steps using LangGraph.
        # Each 'item' is a step in the reasoning (like a thought bubble).
        # 'stream_mode="values"' tells it to yield useful results only.
        for item in self.graph.stream(inputs, config, stream_mode="values"):

            # 
            # Get the most recent message from the list of all messages.
            # The agent might add multiple messages during the thinking.
            # We only care about the last one for status.
            message = item["messages"][-1]

            # If the message is from the AI and includes tool usage,
            # that means the agent is about to call a tool like get_time_now.
            if isinstance(message, AIMessage) and message.tool_calls:
                yield {  # Yield means "send this result immediately" before continuing
                    "is_task_complete": False,         # Not done yet
                    "require_user_input": False,       # No follow-up question to the user (yet)
                    "content": "Looking up the current time...",  # What to display on the UI or CLI
                }

            # If the message is from the tool (like get_time_now),
            # this means the agent just received the result and is working on formatting it.
            elif isinstance(message, ToolMessage):
                yield {
                    "is_task_complete": False,         # Still not done yet
                    "require_user_input": False,       # No clarification from the user is needed
                    "content": "Processing the time result...",  # Let the user know progress
                }

        # 
        # Once the stream ends (no more partial steps), send the final result.
        # This could be a completed message or a follow-up question.
        yield self._final_response(config)

    # This private method gives the final structured result after the stream ends.
    # It reads the agent’s final decision and returns a dictionary with flags.
    def _final_response(self, config: RunnableConfig) -> dict[str, Any]:
        """
        After all streaming messages are done, this function checks what the agent finally decided.
        It uses the config to find the saved response (called 'structured_response').
        """

        # Get the internal memory state from the LangGraph session
        state = self.graph.get_state(config)

        # Pull out the structured result (should match the ResponseFormat schema)
        structured = state.values.get("structured_response")

        # If the structured result is valid, use its status and message.
        # The agent gives us:
        #   - status = "completed" or "input_required" or "error"
        #   - message = the final output or a clarification question
        if isinstance(structured, ResponseFormat):
            if structured.status == "completed":
                return {
                    "is_task_complete": True,              # Mark this as done
                    "require_user_input": False,           # No further input needed
                    "content": structured.message,         # Show the user the final result
                }
            if structured.status in ("input_required", "error"):
                return {
                    "is_task_complete": False,             # Not done yet
                    "require_user_input": True,            # Ask the user to clarify
                    "content": structured.message,         # The question or error to show
                }


        print("[DEBUG] structured response:", structured)  # Print for debugging in the console

        return {
            "is_task_complete": False,                     # Don't mark this task as complete
            "require_user_input": True,                    # Ask the user to rephrase
            "content": "Unable to process your request at the moment. Please try again.",  # Default fallback message
        }
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"] 