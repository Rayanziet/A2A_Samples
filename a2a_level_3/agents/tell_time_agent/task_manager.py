# This class connects the agent with the server
# It receives the user query, invokes the agent, and returns the response

import asyncio
import logging
from adk_agent import TellTimeAgent
from models.request import SendTaskRequest, SendTaskResponse
from models.task import Message, Task, TextPart, TaskStatus, TaskState


logger = logging.getLogger(__name__)

class AgentTaskManager:
    """Manages tasks using the TellTimeAgent.
    This class extends InMemoryTaskManager to handle tasks by invoking the TellTimeAgent.
    It processes user queries, maintains session context, and updates task statuses.
    """
    def __init__(self, agent:TellTimeAgent):
        self._agent = agent
        self._tasks = {}  # Simple in-memory storage
        self.lock = asyncio.Lock()

    def _get_user_query(self, request: SendTaskRequest) -> str:
        """Extracts the user query from the request.
        Args:
            request (SendTaskRequest): The incoming task request containing messages.
        Returns:
            str: The user query extracted from the request.
        """
        
        return request.params.message.parts[0].text
    
    # task is used for conversation history
    #     User: "What time is it?"
    # ↓ (Creates/Updates Task)
    # Agent: "2024-01-15 14:30:25"
    # ↓ (Task status = COMPLETED, history updated)

    # User: "What about tomorrow?"
    # ↓ (Same sessionId, adds to existing Task history)
    # Agent: "Tomorrow will be 2024-01-16..."

    
    async def upsert_task(self, params):
        async with self.lock:
            task_id = params.sessionId
            if task_id not in self._tasks:
                self._tasks[task_id] = Task(
                    id=task_id,
                    status=TaskState(state=TaskState.PENDING),
                    history=[]
                )
            return self._tasks[task_id]

    async def on_send_task(self, request: SendTaskRequest) -> SendTaskResponse:
        """Handles sending a task by invoking the TellTimeAgent.
        This method processes the incoming task request, invokes the agent with the user query,
        and updates the task status based on the agent's response.
        Args:
            request (SendTaskRequest): The incoming task request containing messages and session ID.
        Returns:
            SendTaskResponse: The response containing the updated task information.
        """

        task = await self.upsert_task(request.params)
        user_query = self._get_user_query(request)
        response = self._agent.invoke(user_query, request.params.sessionId)

        agent_message = Message(
            role="agent",
            parts=[TextPart(text=response)]
        )

        async with self.lock:
            task.status = TaskState(state=TaskState.COMPLETED)
            task.history.append(agent_message)

        return SendTaskResponse(id=request.id, result=task)