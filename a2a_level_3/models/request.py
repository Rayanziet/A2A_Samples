from typing import Annotated, Union, Literal
from pydantic import BaseModel, Field
from pydantic.type_adapter import TypeAdapter

from models.json_rpc import JSONRPCRequest, JSONRPCResponse
from models.task import Task, TaskSendParams
from models.task import TaskQueryParams

class SendTaskRequest(JSONRPCRequest):
    method: Literal["tasks/send"] = "tasks/send"
    params: TaskSendParams

class GetTaskRequest(JSONRPCRequest):
    method: Literal["tasks/get"] = "tasks/get"
    params: TaskQueryParams

A2ARequest = TypeAdapter[Annotated[Union[SendTaskRequest, GetTaskRequest], Field(discriminator="method")]]

class SendTaskResponse(JSONRPCResponse):
    result: Task | None = None

class GetTaskResponse(JSONRPCResponse):
    result: Task | None = None