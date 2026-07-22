import asyncio
import json
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from app.core.agent_bus import agent_bus

router = APIRouter(prefix="/api/agent-console", tags=["AI Agent Console"])

@router.get("/stream")
async def agent_console_stream(
    request: Request,
    request_id: str = Query(..., description="Unique request ID mapping to a background agentic process")
):
    """
    Server-Sent Events (SSE) stream for real-time agent collaboration logs.
    """
    async def event_generator():
        q = agent_bus.subscribe(request_id)
        try:
            while True:
                # If client disconnects, request.is_disconnected() handles the break,
                # but we also need a timeout to occasionally check disconnection if queue is idle.
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=2.0)
                    
                    # Convert to SSE format
                    data_str = json.dumps(payload)
                    yield f"event: agent_step\ndata: {data_str}\n\n"
                    
                    if payload.get("action_summary") == "DONE":
                        # Optional sentinel convention to close stream gracefully if we want
                        yield "event: done\ndata: {}\n\n"
                        break
                        
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
        finally:
            agent_bus.unsubscribe(request_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
