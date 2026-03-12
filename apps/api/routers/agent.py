"""AI chat SSE endpoint – streams Vietnamese responses."""

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import db_session, llm
from core.logging import get_logger
from core.ports import LLMPort
from core.schemas import ChatRequest
from services.agent.agent import AgentService

router = APIRouter()
log = get_logger(__name__)


async def _sse_stream(
    request: ChatRequest,
    db: AsyncSession,
    llm_port: LLMPort,
) -> AsyncGenerator[str, None]:
    """Generate SSE events from agent responses."""
    agent_service = AgentService(db=db, llm=llm_port)

    try:
        async for chunk in agent_service.stream_response(
            messages=request.messages,
            branche=request.branche,
        ):
            event = json.dumps({"type": "chunk", "content": chunk})
            yield f"data: {event}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as exc:
        log.error("agent_stream_error", error=str(exc))
        error_event = json.dumps({"type": "error", "content": str(exc)})
        yield f"data: {error_event}\n\n"


@router.post("/chat")
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(db_session),
    llm_port: LLMPort = Depends(llm),
) -> StreamingResponse:
    return StreamingResponse(
        _sse_stream(request, db, llm_port),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
