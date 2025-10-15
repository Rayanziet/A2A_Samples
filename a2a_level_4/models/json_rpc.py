from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, Field

class JSONRPCMessage(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str = Field(default_factory=lambda: uuid4().hex)

class JSONRPCRequest(JSONRPCMessage):
    method: str
    params: dict[str, Any] = {}

class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Any = None

class JSONRPCResponse(JSONRPCMessage):
    result: Any = None
    error: JSONRPCError | None = None

class InternalError(JSONRPCError):
    def __init__(self, code: int = -32603, message: str = "Internal error", data: Any = None):
        super().__init__(code=code, message=message, data=data)