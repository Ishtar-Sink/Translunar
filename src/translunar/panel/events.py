"""Barramento de eventos de progresso e a rota SSE `GET /api/eventos`."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Literal, TypedDict

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from translunar.panel.auth import PROTECTED

logger = logging.getLogger(__name__)

QUEUE_SIZE = 100
PING_INTERVAL_S = 15.0


class Event(TypedDict):
    """Evento de progresso de um job (transcrição ou queima)."""

    clip_id: str
    kind: Literal["transcription", "burn"]
    language: str | None
    state: str
    progress: float
    error: str | None


class EventBus:
    """Distribui eventos para os assinantes (uma fila por conexão SSE)."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queues: set[asyncio.Queue[Event]] = set()

    def bind_loop(self) -> None:
        """Guarda o loop em execução; chamado na subida do app."""
        self._loop = asyncio.get_running_loop()

    def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        self._queues.discard(queue)

    def publish(self, event: Event) -> None:
        """Publica no loop; numa fila cheia o evento é descartado em vez de bloquear."""
        for queue in list(self._queues):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("fila de eventos cheia; evento descartado")

    def publish_threadsafe(self, event: Event) -> None:
        """Publica a partir de outra thread."""
        if self._loop is None:
            raise RuntimeError("bind_loop() não foi chamado")
        self._loop.call_soon_threadsafe(self.publish, event)


def format_sse(event: Event) -> str:
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"event: progresso\ndata: {data}\n\n"


router = APIRouter(prefix="/api")


@router.get("/eventos", dependencies=PROTECTED)
async def stream_events(request: Request) -> StreamingResponse:
    bus: EventBus = request.app.state.bus

    async def generate() -> AsyncIterator[str]:
        queue = bus.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=PING_INTERVAL_S)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield format_sse(event)
        except asyncio.CancelledError:
            pass
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
