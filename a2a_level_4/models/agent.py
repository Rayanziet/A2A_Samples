from pydantic import BaseModel

class AgentCapabilities(BaseModel):
    can_tell_time: bool = False

class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str] = []
    examples: list[str] = []

class AgentCard(BaseModel):
    name: str
    desciption: str
    url: str
    version: str
    defaultInputModes: list[str] = []
    defaultOutputModes: list[str] = []
    capabilities: AgentCapabilities
    skills: list[AgentSkill] = []