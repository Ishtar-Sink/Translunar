"""Testes das filas, do progresso por eventos, do isolamento de falhas e da recuperação."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from translunar.core.config import load_settings
from translunar.core.errors import ClipLockedError
from translunar.core.models import StepState
from translunar.core.state import (
    BurnRecord,
    ClipState,
    clip_dir,
    load_state,
    save_state,
)
from translunar.panel.app import create_app
from translunar.panel.events import Event, EventBus, format_sse
from translunar.panel.jobs import JobRunner, ProgressCallback, recover_interrupted


class Concurrency:
    """Conta quantos `work` rodam ao mesmo tempo e guarda o máximo observado."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current = 0
        self.maximum = 0

    def work(self, progress: ProgressCallback) -> None:
        with self._lock:
            self._current += 1
            self.maximum = max(self.maximum, self._current)
        time.sleep(0.2)
        with self._lock:
            self._current -= 1


def _drain(queue: asyncio.Queue[Event]) -> list[Event]:
    events: list[Event] = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


def test_transcriptions_run_one_at_a_time() -> None:
    counter = Concurrency()

    async def scenario() -> None:
        bus = EventBus()
        bus.bind_loop()
        runner = JobRunner(bus, burn_jobs=2)
        tasks = [runner.submit("transcription", f"corte-{i}", None, counter.work) for i in range(3)]
        await asyncio.gather(*tasks)

    asyncio.run(scenario())
    assert counter.maximum == 1


def test_burns_respect_burn_jobs_limit() -> None:
    counter = Concurrency()

    async def scenario() -> None:
        bus = EventBus()
        bus.bind_loop()
        runner = JobRunner(bus, burn_jobs=2)
        tasks = [runner.submit("burn", f"corte-{i}", "en", counter.work) for i in range(4)]
        await asyncio.gather(*tasks)

    asyncio.run(scenario())
    assert counter.maximum == 2


def test_progress_is_published_until_done() -> None:
    def work(progress: ProgressCallback) -> None:
        progress(0.25)
        progress(0.5)
        progress(1.0)

    async def scenario() -> list[Event]:
        bus = EventBus()
        bus.bind_loop()
        queue = bus.subscribe()
        runner = JobRunner(bus, burn_jobs=2)
        await runner.submit("transcription", "corte", None, work)
        await asyncio.sleep(0.05)  # deixa os call_soon_threadsafe pendentes rodarem
        return _drain(queue)

    events = asyncio.run(scenario())
    states = [e["state"] for e in events]
    assert states[0] == "aguardando"
    assert states[1] == "transcrevendo"
    assert states[-1] == "transcrito"
    assert events[-1]["progress"] == 1.0
    running = [e["progress"] for e in events if e["state"] == "transcrevendo"]
    assert running == sorted(running)
    assert {0.25, 0.5} <= set(running)
    assert all(e["clip_id"] == "corte" and e["kind"] == "transcription" for e in events)


def test_burn_success_publishes_pronto() -> None:
    async def scenario() -> list[Event]:
        bus = EventBus()
        bus.bind_loop()
        queue = bus.subscribe()
        runner = JobRunner(bus, burn_jobs=1)
        await runner.submit("burn", "corte", "en", lambda progress: None)
        await asyncio.sleep(0.05)
        return _drain(queue)

    events = asyncio.run(scenario())
    assert [e["state"] for e in events] == ["aguardando", "queimando", "pronto"]
    assert events[-1]["language"] == "en"
    assert events[-1]["progress"] == 1.0


def test_failure_is_isolated_and_published() -> None:
    def ok(progress: ProgressCallback) -> None:
        time.sleep(0.05)

    def broken(progress: ProgressCallback) -> None:
        raise RuntimeError("arquivo corrompido")

    async def scenario() -> list[Event]:
        bus = EventBus()
        bus.bind_loop()
        queue = bus.subscribe()
        runner = JobRunner(bus, burn_jobs=2)
        tasks = [
            runner.submit("transcription", "a", None, ok),
            runner.submit("transcription", "b", None, broken),
            runner.submit("transcription", "c", None, ok),
        ]
        await asyncio.gather(*tasks)  # não pode levantar
        await asyncio.sleep(0.05)
        return _drain(queue)

    events = asyncio.run(scenario())
    final = {e["clip_id"]: e for e in events if e["state"] in {"transcrito", "erro"}}
    assert final["a"]["state"] == "transcrito"
    assert final["c"]["state"] == "transcrito"
    assert final["b"]["state"] == "erro"
    assert final["b"]["error"] == "arquivo corrompido"


def test_same_key_twice_raises_clip_locked() -> None:
    async def scenario() -> None:
        bus = EventBus()
        bus.bind_loop()
        runner = JobRunner(bus, burn_jobs=1)
        first = runner.submit("transcription", "corte", None, lambda progress: time.sleep(0.1))
        assert runner.is_busy("corte")
        assert not runner.is_busy("outro")
        with pytest.raises(ClipLockedError):
            runner.submit("transcription", "corte", None, lambda progress: None)
        await first
        assert not runner.is_busy("corte")
        # a chave foi liberada: pode submeter de novo
        await runner.submit("transcription", "corte", None, lambda progress: None)

    asyncio.run(scenario())


def test_recover_interrupted_marks_running_steps(tmp_path: Path) -> None:
    state = ClipState("corte", "corte.mp4")
    state.transcription.state = StepState.TRANSCREVENDO
    state.burns["en"] = BurnRecord(state=StepState.QUEIMANDO)
    state.burns["es"] = BurnRecord(state=StepState.PRONTO)
    save_state(clip_dir(tmp_path, "corte"), state)
    idle = ClipState("parado", "parado.mp4")
    save_state(clip_dir(tmp_path, "parado"), idle)

    assert recover_interrupted(tmp_path) == 1

    reloaded = load_state(clip_dir(tmp_path, "corte"), "corte", "corte.mp4")
    assert reloaded.transcription.state == StepState.INTERROMPIDO
    assert reloaded.burns["en"].state == StepState.INTERROMPIDO
    assert reloaded.burns["es"].state == StepState.PRONTO
    assert recover_interrupted(tmp_path) == 0


def test_format_sse_is_valid() -> None:
    event: Event = {
        "clip_id": "corte",
        "kind": "burn",
        "language": "en",
        "state": "queimando",
        "progress": 0.5,
        "error": None,
    }
    text = format_sse(event)
    assert text.startswith("event: progresso\ndata: ")
    assert text.endswith("\n\n")
    payload = text.split("data: ", 1)[1].strip()
    assert json.loads(payload) == event


def test_publish_drops_event_on_full_queue() -> None:
    async def scenario() -> int:
        bus = EventBus()
        bus.bind_loop()
        queue = bus.subscribe()
        event: Event = {
            "clip_id": "c",
            "kind": "burn",
            "language": None,
            "state": "queimando",
            "progress": 0.1,
            "error": None,
        }
        for _ in range(150):
            bus.publish(event)
        size = queue.qsize()
        bus.unsubscribe(queue)
        bus.publish(event)
        return size

    assert asyncio.run(scenario()) == 100


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[], TestClient]:
    monkeypatch.setenv("TRANSLUNAR_PAINEL_SENHA", "certa")
    monkeypatch.setenv("TRANSLUNAR_PAINEL_SEGREDO", "segredo-fixo-de-teste")
    settings = dataclasses.replace(load_settings(), data_dir=tmp_path)
    return lambda: TestClient(create_app(settings))


def test_events_without_session_is_401(client: Callable[[], TestClient]) -> None:
    assert client().get("/api/eventos").status_code == 401


def test_app_lifespan_creates_bus_and_runner(client: Callable[[], TestClient]) -> None:
    with client() as http:
        assert isinstance(http.app.state.bus, EventBus)  # type: ignore[attr-defined]
        assert isinstance(http.app.state.jobs, JobRunner)  # type: ignore[attr-defined]
