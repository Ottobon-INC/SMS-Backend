"""FastAPI router for WhatsApp Simulator module."""

from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse

from app.modules.whatsapp_simulator.schemas import MetaOutboundPayload
from app.modules.whatsapp_simulator.service import simulator_manager

router = APIRouter(prefix="/whatsapp-simulator", tags=["whatsapp-simulator"])


@router.get("/stream")
async def stream_simulator_events(request: Request):
    """Server-Sent Events (SSE) live stream endpoint for WhatsApp Simulator."""
    return StreamingResponse(
        simulator_manager.stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/messages")
def get_recent_simulator_messages():
    """Returns recent message history buffer."""
    return simulator_manager.get_messages()


@router.delete("/messages")
def clear_simulator_messages():
    """Clears all simulator message logs."""
    simulator_manager.clear_messages()
    return {"status": "cleared"}


@router.post("/outbound", status_code=status.HTTP_200_OK)
def receive_meta_outbound_payload(payload: dict):
    """Receives Meta Cloud API outbound JSON payload and broadcasts to simulator subscribers."""
    msg = simulator_manager.add_message(payload)
    return {"status": "success", "message_id": msg["id"]}
