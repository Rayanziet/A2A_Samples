import os
import uuid
import logging
from dotenv import load_dotenv

load_dotenv()

from google.adk.agents.llm_agent import LlmAgent

from google.adk.sessions import InMemorySessionService

from google.adk.memory.in_memory_memory_service import InMemoryMemoryService

from google.adk.artifacts import InMemoryArtifactService

from google.adk.runners import Runner

from google.adk.agents.readonly_context import ReadonlyContext

from google.adk.tools.tool_context import ToolContext

from google.adk.tools.function_tool import FunctionTool 

from google.genai import types           

from server.task_manager import InMemoryTaskManager

from models.request import SendTaskRequest, SendTaskResponse

from models.task import Message, TaskStatus, TaskState, TextPart

from a2a_level_4.utilities.a2a.agent_connector import AgentConnector

from a2a_level_4.utilities.mcp.mcp_connector import MCPConnector



from models.agent import AgentCard

logger = logging.getLogger(__name__)

class OrchestratorAgent:
    """
    OrchestratorAgent:
      - Discovers A2A agents via DiscoveryClient → list of AgentCards
      - Connects to each A2A agent with AgentConnector
      - Discovers MCP servers via MCPConnector and loads MCP tools
      - Exposes each A2A action and each MCP tool as its own callable tool
      - Routes user queries by picking and invoking the correct tool
    """

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self, agent_cards: list[AgentCard]):
        """
        Initialize the orchestrator with discovered A2A agents and MCP tools.

        Args:
            agent_cards (list[AgentCard]): Metadata for each A2A child agent.
        """
        self.connectors =  {}
        for card in agent_cards:
            self.connectors[card.name] = AgentConnector(card.name, card.url)
            logger.info(f"Registered A2A connector for {card.name}")
        
        self.mcp = MCPConnector()
        mcp_tools = self.mcp.get_tools()
        logger.info(f"Loaded {len(mcp_tools)} MCP tools")

        # Now I have the tools, I need to implement a way to run them
        self._mcp_wrapper = []
        def make_wrapper(tool):
            async def wrapper(args: dict):
                return await tool.run(args)
            wrapper.__name__ = tool.name
            return wrapper
        
        for tool in mcp_tools:
            fn = make_wrapper(tool)
            self._mcp_wrapper.append(FunctionTool(fn))
            logger.info(f"Wrapped MCP tool for LLM : {tool.name}")


        self._agent = self._build_agent()
        self._user_id = "orchestrator_user"

        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )
    
    def _build_agent(self) -> LlmAgent:
        """
        Construct the Gemini-based LlmAgent with:
        - Model name
        - Agent name/description
        - System instruction callback
        - Available tool functions
        """

        return LlmAgent(
            model="gemini-1.5-flash-latest",  
            name="orchestrator_agent",          
            description="Routes requests to A2A agents or MCP tools.",
            instruction=self._root_instruction, 
            tools=[
                self._list_agents,              
                self._delegate_task,
                *self._mcp_wrapper 
            ],# * operator is used to unpack the list of tools
        )
    
    def _root_instruction(self, context: ReadonlyContext) -> str:
        """
        System prompt generator: instructs the LLM how to use available tools.

        Args:
            context (ReadonlyContext): Read-only context (unused here).
        """
        return (
            "You are an orchestrator with two tool categories:\n"
            "1) A2A agent tools: list_agents(), delegate_task(agent_name, message)\n"
            "2) MCP tools: one FunctionTool per tool name\n"
            "Pick exactly the right tool by its name and call it with correct args. Do NOT hallucinate."
        )
    
    def _list_agents(self) -> list[str]:
        """
        Tool function: returns the list of child-agent names currently registered.
        Called by the LLM when it wants to discover available agents.
        """
        return list(self.connectors.keys())
    
    async def _delegate_task(
        self,
        agent_name: str,
        message: str,
        tool_context: ToolContext
    ) -> str:
        """
        Tool function: forwards the `message` to the specified child agent
        (via its AgentConnector), waits for the response, and returns the
        text of the last reply.
        """
        # Validate agent_name exists
        if agent_name not in self.connectors:
            raise ValueError(f"Unknown agent: {agent_name}")
        connector = self.connectors[agent_name]

        # Ensure session_id persists across tool calls via tool_context.state
        state = tool_context.state
        if "session_id" not in state:
            state["session_id"] = str(uuid.uuid4())
        session_id = state["session_id"]

        # Delegate task asynchronously and await Task result
        child_task = await connector.send_task(message, session_id)

        # Extract text from the last history entry if available
        if child_task.history and len(child_task.history) > 1:
            return child_task.history[-1].parts[0].text
        return ""
    
    async def invoke(self, query: str, session_id: str) -> str:
        """
        Main entry: receives a user query + session_id,
        sets up or retrieves a session, wraps the query for the LLM,
        runs the Runner (with tools enabled), and returns the final text.
        Summary of changes:
        1. Agent's invoke method is made async
        2. All async calls (get_session, create_session, run_async) 
            are awaited inside invoke method
        3. task manager's on_send_task updated to await the invoke call
        """
        session = await self._runner.session_service.get_session(
            app_name=self._agent.name,
            user_id=self._user_id,
            session_id=session_id
        )
        if session is None:
            session = await self._runner.session_service.create_session(
                app_name=self._agent.name,
                user_id=self._user_id,
                session_id=session_id,
                state={}
            )

        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=query)]
        )

        last_event = None
        async for event in self._runner.run_async(
            user_id=self._user_id,
            session_id=session.id,
            new_message=content
        ):
            last_event = event

        if not last_event or not last_event.content or not last_event.content.parts:
            return ""

        return "\n".join([p.text for p in last_event.content.parts if p.text])
    


class OrchestratorTaskManager(InMemoryTaskManager):
    """
    TaskManager wrapper: exposes OrchestratorAgent.invoke() over the
    A2A JSON-RPC `tasks/send` endpoint, handling in-memory storage and
    response formatting.
    """
    def __init__(self, agent: OrchestratorAgent):
        super().__init__()       # Initialize base in-memory storage
        self.agent = agent       # Store our orchestrator logic

    def _get_user_text(self, request: SendTaskRequest) -> str:
        """
        Helper: extract the user's raw input text from the request object.
        """
        return request.params.message.parts[0].text

    async def on_send_task(self, request: SendTaskRequest) -> SendTaskResponse:
        """
        Called by the A2A server when a new task arrives:
        1. Store the incoming user message
        2. Invoke the OrchestratorAgent to get a response
        3. Append response to history, mark completed
        4. Return a SendTaskResponse with the full Task
        """
        logger.info(f"OrchestratorTaskManager received task {request.params.id}")

        # Step 1: save the initial message
        task = await self.upsert_task(request.params)

        # Step 2: run orchestration logic
        user_text = self._get_user_text(request)
        response_text = await self.agent.invoke(user_text, request.params.sessionId)

        # Step 3: wrap the LLM output into a Message
        reply = Message(role="agent", parts=[TextPart(text=response_text)])
        async with self.lock:
            task.status = TaskStatus(state=TaskState.COMPLETED)
            task.history.append(reply)

        # Step 4: return structured response
        return SendTaskResponse(id=request.id, result=task)