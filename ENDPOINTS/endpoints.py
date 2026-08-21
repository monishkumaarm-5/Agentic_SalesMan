import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from WORKFLOW.ORCHE import ask

router = APIRouter(prefix="/api", tags=["sales-agent"])


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Customer's message")
    thread_id: Optional[str] = Field(
        default=None,
        description=(
            "Conversation id used to keep chat history/context between "
            "calls. A new one is generated and returned if omitted."
        ),
    )


class ChatResponse(BaseModel):
    answer: str
    context: str
    thread_id: str


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    thread_id = payload.thread_id or str(uuid.uuid4())
    try:
        result = ask(payload.question, thread_id=thread_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(
        answer=result["answer"],
        context=result["context"],
        thread_id=thread_id,
    )
