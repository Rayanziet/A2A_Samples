
# starlette is used for building ASGI web applications in Python.
#starlette is like Flask but used for async applications.

from fastapi.encoders import jsonable_encoder
from starlette.applications import Starlette #to create a web app
from starlette.responses import JSONResponse #to send JSON responses
from starlette.requests import Request #to handle incoming requests

from models.agent import AgentCard
from models.request import SendTaskRequest, A2ARequest
from models.json_rpc import JSONRPCResponse, InternalError #for structured request/response handling
from agents import task_manager
import json
import logging

logger = logging.getLogger(__name__)

class A2AServer:
    def __init__(self, host="0.0.0.0", port=5000, agent_card: AgentCard=None, task_manager: task_manager = None):
        self.host = host
        self.port = port
        self.agent_card = agent_card
        self.task_manager = task_manager

        self.app = Starlette()
        # registering a route for handling incoming requests
        self.app.add_route("/", self.handle_request, methods=["POST"])
        # registering a route for serving the agent's metadata
        self.app.add_route("/.well-known/agent.json", self._get_agent_card, methods=["GET"])

    def start(self): #launch the starlette server
        if not self.agent_card or not self.task_manager:
            raise ValueError("Agent card and task manager must be provided to start the server.")
        
        import uvicorn
        uvicorn.run(self.app, host=self.host, port=self.port)

    def _get_agent_card(self, request: Request):
        """Serve the agent's metadata as a JSON response."""
        return JSONResponse(self.agent_card.model_dump(execlude_none=True))

    async def handle_request(self, request: Request):
        """
        Handle incoming JSON-RPC requests, process them, and return appropriate responses.
        parse the incoming request, validate it, and route it to the appropriate handler.
        """

        try:
            # parse incoming request body
            body = await request.body()

            # Parse and validate the JSON-RPC request
            json_rpc = A2ARequest.validate_python(body)

            # Check if it is a SendTaskRequest, if so call the task manager
            if isinstance(json_rpc, SendTaskRequest):
                response = await self.task_manager.on_send_task(json_rpc)

            else:
                raise ValueError(f"Unsupported request type: {type(json_rpc)}")
            
            # convert the result into a proper JSON response
            return self._create_response(response)
        
        except Exception as e:
            logger.exception("Error handling request")
            error = InternalError(data=str(e))
            return JSONResponse(
                JSONRPCResponse(id=None, error=InternalError(message=str(e))).model_dump(),
                status_code=400
            )
        
    def _create_response(self, response) -> JSONResponse:
        """Create a JSON-RPC response from the given result.
        Args:
            response: The result to be included in the response.
        Returns:
            JSONResponse: Starlette-compatible HTTP response with JSON body.
        """
        if isinstance(response, JSONRPCResponse):
            return JSONResponse(content=jsonable_encoder(response.model_dump(exclude_none=True)))
        
        else:
            raise ValueError(f"Unsupported response type: {type(response)}")