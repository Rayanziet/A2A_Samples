import json
from uuid import uuid4
import httpx
from httpx_sse import connect_sse
from typing import Any

from models.request import SendTaskRequest, GetTaskRequest

from models.json_rpc import JSONRPCRequest

from models.task import Task, TaskSendParams
from models.agent import AgentCard

# Custom Error classes
class A2AClientHttpError(Exception):
    """Custom exception for HTTP errors in A2AClient."""
    pass

class A2AClientJSONError(Exception):
    """Custom exception for JSON parsing errors in A2AClient."""
    pass

class A2AClient:

    def __init__(self, agent_card: AgentCard=None, base_url: str = None):
        if agent_card:
            self.base_url = agent_card.url
        elif base_url:
            self.base_url = base_url
        else:
            raise ValueError("Either agent_card or base_url must be provided.")
        
    async def send_task( self, paloud: dict[str, Any]):
        request = SendTaskRequest(
            id = uuid4().hex,
            params = TaskSendParams(**paloud) #like **kwargs, acceptes any number of keyword arguments
        )

        response = await self._send_request(request)
        return Task(**response["result"]) #extrcat the result field from the response
    
    async def _send_request(self, request: JSONRPCRequest) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.base_url,
                    json=request.model_dump(),
                    timeout=30
                )
                response.raise_for_status()
                return response.json() 
            except httpx.HTTPError as e:
                raise A2AClientHttpError(f"HTTP error occurred: {e}") from e
            
            except json.JSONDecodeError as e:
                raise A2AClientJSONError(f"Error parsing JSON response: {e}") from e
            