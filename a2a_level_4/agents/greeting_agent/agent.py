
#     1) Discovers all registered A2A agents via DiscoveryClient
#     2) Invokes the TellTimeAgent to fetch the current time
#     3) Generates a 2–3 line poetic greeting referencing that time

import logging                             
from dotenv import load_dotenv              

load_dotenv()  

from google.adk.agents.llm_agent import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.runners import Runner

from google.genai import types

from google.adk.tools.function_tool import FunctionTool

from a2a_level_4.utilities.a2a.discovery import DiscoveryClient
from a2a_level_4.utilities.a2a.agent_connector import AgentConnector

logger = logging.getLogger(__name__)


class GreetingAgent:
    """
    Orchestrator “meta-agent” that:
      - Provides two LLM tools: list_agents() and call_agent(...)
      - On a “greet me” request:
          1) Calls list_agents() to see which agents are up
          2) Calls call_agent("TellTimeAgent", "What is the current time?")
          3) Crafts a 2–3 line poetic greeting referencing that time
    """

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        """
        Constructor: build the internal orchestrator LLM, runner, discovery client.
        """
        # Build the LLM with its tools and system instruction
        self.orchestrator = self._build_orchestrator()

        # A fixed user_id to group all greeting calls into one session
        self.user_id = "greeting_user"

        # Runner wires together: agent logic, sessions, memory, artifacts
        self.runner = Runner(
            app_name=self.orchestrator.name,
            agent=self.orchestrator,
            artifact_service=InMemoryArtifactService(),       # file blobs, unused here
            session_service=InMemorySessionService(),         # in-memory sessions
            memory_service=InMemoryMemoryService(),           # conversation memory
        )

        # A helper client to discover what agents are registered
        self.discovery = DiscoveryClient()

        # Cache for created connectors so we reuse them
        self.connectors: dict[str, AgentConnector] = {}


    def _build_orchestrator(self) -> LlmAgent:
        """
        Internal: define the LLM, its system instruction, and wrap tools.
        """

        # --- Tool 1: list_agents ---
        async def list_agents() -> list[dict]:
            """
            Fetch all AgentCard metadata from the registry,
            return as a list of plain dicts.
            """
            cards = await self.discovery.list_agent_cards()
            return [card.model_dump(exclude_none=True) for card in cards]


        # --- Tool 2: call_agent ---
        async def call_agent(agent_name: str, message: str) -> str:
            """
            Given an agent_name string and a user message,
            find that agent’s URL, send the task, and return its reply.
            """
            # Re-fetch registry each call to catch new agents dynamically
            cards = await self.discovery.list_agent_cards()

            # Try to match exactly by name or id (case-insensitive)
            matched = next(
                (c for c in cards
                 if c.name.lower() == agent_name.lower()
                 or getattr(c, "id", "").lower() == agent_name.lower()),
                None
            )

            # Fallback: substring match if no exact found
            if not matched:
                matched = next(
                    (c for c in cards if agent_name.lower() in c.name.lower()),
                    None
                )

            # If still nothing, error out
            if not matched:
                raise ValueError(f"Agent '{agent_name}' not found.")

            # Use Pydantic model’s name field as key
            key = matched.name
            # If we haven’t built a connector yet, create and cache one
            if key not in self.connectors:
                self.connectors[key] = AgentConnector(
                    name=matched.name,
                    base_url=matched.url
                )
            connector = self.connectors[key]

            # Use a single session per greeting agent run (could be improved)
            session_id = self.user_id

            # Delegate the task and wait for the full Task object
            task = await connector.send_task(message, session_id=session_id)

            # Pull the final agent reply out of the history
            if task.history and task.history[-1].parts:
                return task.history[-1].parts[0].text

            return ""


        system_instr = (
            "You have two tools:\n"
            "1) list_agents() → returns metadata for all available agents.\n"
            "2) call_agent(agent_name: str, message: str) → fetches a reply from that agent.\n"
            "When asked to greet, first call list_agents(), then "
            "call_agent('TellTimeAgent','What is the current time?'), "
            "then craft a 2–3 line poetic greeting referencing that time."
        )

        # Wrap our Python functions into ADK FunctionTool objects
        tools = [
            FunctionTool(list_agents),   # auto-uses function name and signature
            FunctionTool(call_agent),
        ]

        # Finally, create and return the LlmAgent with everything wired up
        return LlmAgent(
            model="gemini-1.5-flash-latest",               
            name="greeting_orchestrator",                
            description="Orchestrates time fetching and generates poetic greetings.",
            instruction=system_instr,                    
            tools=tools,                                 
        )


    async def invoke(self, query: str, session_id: str) -> str:
        """
        Public: send a user query through the orchestrator LLM pipeline,
        ensuring session reuse or creation, and return the final text reply.
        Summary of changes:
        1. Agent's invoke method is made async
        2. All async calls (get_session, create_session, run_async) 
            are awaited inside invoke method
        3. task manager's on_send_task updated to await the invoke call

        """
        session = await self.runner.session_service.get_session(
            app_name=self.orchestrator.name,
            user_id=self.user_id,
            session_id=session_id,
        )

        if session is None:
            session = await self.runner.session_service.create_session(
                app_name=self.orchestrator.name,
                user_id=self.user_id,
                session_id=session_id,
                state={},  # you could prefill memory here if desired
            )

        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=query)]
        )

        last_event = None
        async for event in self.runner.run_async(
            user_id=self.user_id,
            session_id=session.id,
            new_message=content
        ):
            last_event = event

        if not last_event or not last_event.content or not last_event.content.parts:
            return ""

        return "\n".join([p.text for p in last_event.content.parts if p.text])