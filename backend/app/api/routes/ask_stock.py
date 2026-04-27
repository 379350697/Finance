from uuid import uuid4

from fastapi import APIRouter

from app.schemas.ask_stock import AskMessageCreate, AskSessionCreate
from app.services.ask_stock.agent import AskStockAgent
from app.services.ask_stock.tools import AskStockTools

router = APIRouter(prefix="/ask-stock", tags=["ask-stock"])

_sessions: dict[str, dict] = {}
_messages: dict[str, list[dict]] = {}


@router.post("/sessions", status_code=201)
def create_session(request: AskSessionCreate) -> dict:
    session_id = str(uuid4())
    session = {"id": session_id, "title": request.title}
    _sessions[session_id] = session
    _messages[session_id] = []
    return session


@router.post("/sessions/{session_id}/messages")
def send_message(session_id: str, request: AskMessageCreate) -> dict:
    user_message = {
        "id": str(uuid4()),
        "role": "user",
        "content": request.content,
        "tool_context": {},
    }
    agent = AskStockAgent(tools=AskStockTools(), llm_provider=None)
    answer = agent.answer(request.content)
    assistant_message = {
        "id": str(uuid4()),
        "role": "assistant",
        "content": answer,
        "tool_context": {},
    }
    _messages.setdefault(session_id, []).extend([user_message, assistant_message])
    return {"session_id": session_id, "messages": [user_message, assistant_message]}
