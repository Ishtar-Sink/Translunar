"""Testes do lock por corte (CT-26)."""

from __future__ import annotations

import multiprocessing
from pathlib import Path

import pytest

from translunar.core.errors import ClipLockedError
from translunar.core.lock import ClipLock, is_locked


def _child(directory: str, queue: multiprocessing.Queue[str]) -> None:
    try:
        with ClipLock(Path(directory)):
            queue.put("acquired")
    except ClipLockedError as exc:
        queue.put(f"locked:{exc.exit_code}")


def test_is_locked_inside_and_after(tmp_path: Path) -> None:
    d = tmp_path / "corte-01"
    assert is_locked(d) is False
    with ClipLock(d):
        assert is_locked(d) is True
    assert is_locked(d) is False


def test_nested_lock_raises(tmp_path: Path) -> None:
    d = tmp_path / "corte-01"
    with ClipLock(d), pytest.raises(ClipLockedError) as info, ClipLock(d):
        pass
    assert info.value.exit_code == 4


def test_child_process_cannot_lock(tmp_path: Path) -> None:
    d = tmp_path / "corte-01"
    ctx = multiprocessing.get_context("spawn")
    queue: multiprocessing.Queue[str] = ctx.Queue()
    with ClipLock(d):
        proc = ctx.Process(target=_child, args=(str(d), queue))
        proc.start()
        result = queue.get(timeout=60)
        proc.join(timeout=60)
    assert result == "locked:4"
    # liberado o lock, o filho consegue
    proc2 = ctx.Process(target=_child, args=(str(d), queue))
    proc2.start()
    assert queue.get(timeout=60) == "acquired"
    proc2.join(timeout=60)
