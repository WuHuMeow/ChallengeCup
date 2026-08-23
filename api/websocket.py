"""Async transport adapter for run-scoped realtime events."""

from __future__ import annotations

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


async def stream_run_events(websocket: WebSocket, service, run_id: str) -> None:
    if service.get(run_id) is None:
        await websocket.close(code=4404, reason="unknown run_id")
        return

    await websocket.accept()
    try:
        async for message in service.realtime_hub.subscribe(run_id):
            await websocket.send_json(message)
    except WebSocketDisconnect:
        return
