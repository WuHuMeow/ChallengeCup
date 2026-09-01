"""Async transport adapter for run-scoped realtime events."""

from __future__ import annotations

import asyncio

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


async def stream_run_events(websocket: WebSocket, service, run_id: str) -> None:
    if service.get(run_id) is None:
        await websocket.close(code=4404, reason="unknown run_id")
        return

    await websocket.accept()
    subscription = service.realtime_hub.subscribe(run_id)

    async def forward_events() -> None:
        async for message in subscription:
            await websocket.send_json(message)

    async def wait_for_disconnect() -> None:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return

    tasks = {
        asyncio.create_task(forward_events()),
        asyncio.create_task(wait_for_disconnect()),
    }
    try:
        done, _ = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            await task
    except WebSocketDisconnect:
        return
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await subscription.aclose()
