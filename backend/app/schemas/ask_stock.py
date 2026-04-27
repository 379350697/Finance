from pydantic import BaseModel, Field


class AskSessionCreate(BaseModel):
    title: str = "新问股会话"


class AskSessionRead(BaseModel):
    id: str
    title: str


class AskMessageCreate(BaseModel):
    content: str


class AskMessageRead(BaseModel):
    id: str
    role: str
    content: str
    tool_context: dict = Field(default_factory=dict)
