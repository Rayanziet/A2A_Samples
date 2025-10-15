# this class is used to send tasks from the orchestrator to remote agents
# using their urls


import uuid                          
import logging                     

from client.client import A2AClient
from models.task import Task

logger = logging.getLogger(__name__)

class AgentConnector:
    """
    Connects to a remote A2A agent and provides a uniform method to delegate tasks.

    Attributes:
        name (str): Human-readable identifier of the remote agent.
        client (A2AClient): HTTP client pointing at the agent's URL.
    """
    def __init__(self, name, base_url: str):
        self.name = name
        self.client = A2AClient(base_url=base_url)
        logger.info(f"Initialized AgentConnector for {self.name} at {base_url}")

    async def send_task(self, message, session_id: str = None) -> Task:
        """
        Sends a task to the remote agent.

        Args:
            message (str): The user message to send.
            session_id (str, optional): Session ID for context continuity. Defaults to None.

        Returns:
            Task: The response task from the remote agent.
        """
        task_id = uuid.uuid4().hex
        payload = {
            "id": task_id,
            "sessionId": session_id,
            "message": {
                "role": "user",               
                "parts": [                      
                    {"type": "text", "text": message}
                ]
            }
        }
        task_result = await self.client.send_task(payload)
        logger.info(f"Sent task {task_id} to {self.name}")
        return task_result