from datetime import datetime

from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.artifacts import InMemoryArtifactService

from google.adk.runners import Runner
#Runner manages the configuration and execution of agents, and it connects the agent, memory, session and files into a complete system.
from google.genai import types

from dotenv import load_dotenv
load_dotenv()

class TellTimeAgent:
    SUPPORTED_CONTENT_TYPES = ['text','text/plain']

    def __init__(self):
        """Initialize the TellTimeAgent with necessary services and configurations."""
        self._agent = self._build_agent()
        self._user_id = "time_agent_user"
        self._runner = Runner(
            app_name = self._agent.name,
            agent = self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )
    def _build_agent(self) -> LlmAgent:
        """
        Create and configure the LLMAgent with the necessary parameters.
        Returns:
            LlmAgent: Configured LlmAgent instance.
        """
        return LlmAgent(
            model = "gemini-2.5-flash",
            name='tell_time_agent',
            description="Tells the current time",
            instruction=" reply with the current time format YYYY-MM-DD HH:MM:SS when asked for the time.",
        )
    
    def invoke(self, query: str, session_id: str) -> str:
        """
        Invoke the agent with a user query and session ID.
        Args:
            query (str): The user query to be processed by the agent.
            session_id (str): The session ID for maintaining context.
        Returns:
            str: The agent's response to the user query.
        """
        #first try to use an existing session
        session = self._runner.session_service.get_session(
            app_name=self._agent.name,
            user_id=self._user_id,
            session_id=session_id,
        )

        if session is None:
            session = self._runner.session_service.create_session(
                app_name=self._agent.name,
                user_id=self._user_id,
                session_id=session_id,
                state={},
            )
        
        #shaping the user message in a way Gemini expects
        content= types.Content(
            role='user',
            parts=[types.Part.from_text(text=query)]
        )

        #now run the agent using runner and collect response events
        events= list(self._runner.run(
            user_id=self._user_id,
            session_id=session_id,
            new_message=content
        ))

        if not events or not events[-1].content or not events[-1].content.parts:
            return ""

        return "\n".join(
            [part.text for part in events[-1].content.parts if part.text]
        )
