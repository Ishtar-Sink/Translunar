"""Filas de transcrição e de queima, isolamento de falhas e recuperação de jobs interrompidos."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from translunar.core.errors import ClipLockedError
from translunar.core.state import clip_dir, list_states, mark_interrupted, save_state
from translunar.panel.events import Event, EventBus

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float], None]
Work = Callable[[ProgressCallback], None]
Kind = Literal["transcription", "burn"]
JobKey = tuple[str, str, str | None]

_RUNNING = {"transcription": "transcrevendo", "burn": "queimando"}
_DONE = {"transcription": "transcrito", "burn": "pronto"}
_MIN_STEP = 0.01


class JobRunner:
    """Agenda os jobs, limita a concorrência por tipo, publica eventos e isola falhas.

    O `work` é síncrono, roda numa thread e grava o `estado.json`; o executor não conhece a
    pipeline.
    """

    def __init__(self, bus: EventBus, burn_jobs: int) -> None:
        self._bus = bus
        self._semaphores: dict[str, asyncio.Semaphore] = {
            "transcription": asyncio.Semaphore(1),
            "burn": asyncio.Semaphore(burn_jobs),
        }
        self._active: dict[JobKey, asyncio.Task[None]] = {}

    def _publish(
        self,
        kind: Kind,
        clip_id: str,
        language: str | None,
        state: str,
        progress: float,
        error: str | None = None,
    ) -> Event:
        event: Event = {
            "clip_id": clip_id,
            "kind": kind,
            "language": language,
            "state": state,
            "progress": progress,
            "error": error,
        }
        self._bus.publish(event)
        return event

    def submit(
        self, kind: Kind, clip_id: str, language: str | None, work: Work
    ) -> asyncio.Task[None]:
        key: JobKey = (clip_id, kind, language)
        if key in self._active:
            raise ClipLockedError(f"já há um job de {kind} ativo para o corte {clip_id}")
        self._publish(kind, clip_id, language, "aguardando", 0.0)
        task = asyncio.create_task(self._run(kind, clip_id, language, work, key))
        self._active[key] = task
        return task

    async def _run(
        self, kind: Kind, clip_id: str, language: str | None, work: Work, key: JobKey
    ) -> None:
        try:
            async with self._semaphores[kind]:
                self._publish(kind, clip_id, language, _RUNNING[kind], 0.0)
                last = 0.0

                def progress_cb(value: float) -> None:
                    nonlocal last
                    if value >= 1.0 or value - last >= _MIN_STEP:
                        last = value
                        self._bus.publish_threadsafe(
                            {
                                "clip_id": clip_id,
                                "kind": kind,
                                "language": language,
                                "state": _RUNNING[kind],
                                "progress": value,
                                "error": None,
                            }
                        )

                await asyncio.to_thread(work, progress_cb)
            self._publish(kind, clip_id, language, _DONE[kind], 1.0)
        except Exception as exc:
            logging.exception("falha no job de %s do corte %s", kind, clip_id)
            self._publish(kind, clip_id, language, "erro", 0.0, str(exc))
        finally:
            self._active.pop(key, None)

    def is_busy(self, clip_id: str) -> bool:
        return any(key[0] == clip_id for key in self._active)


def recover_interrupted(output_dir: Path) -> int:
    """Marca como interrompido o que estava em andamento; não reenfileira (RN-10)."""
    changed = 0
    for state in list_states(output_dir):
        if mark_interrupted(state):
            save_state(clip_dir(output_dir, state.clip_id), state)
            changed += 1
    return changed
