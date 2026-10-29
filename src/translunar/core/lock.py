"""Lock por corte entre processos (CLI e painel), baseado em `fcntl.flock`."""

from __future__ import annotations

import fcntl
from pathlib import Path
from types import TracebackType
from typing import IO

from translunar.core.errors import ClipLockedError

LOCK_FILE = ".lock"


class ClipLock:
    """Gerenciador de contexto que segura o lock exclusivo da pasta de um corte."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._handle: IO[str] | None = None

    def __enter__(self) -> ClipLock:
        self.directory.mkdir(parents=True, exist_ok=True)
        handle = (self.directory / LOCK_FILE).open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            raise ClipLockedError(f"corte em processamento: {self.directory.name}") from None
        self._handle = handle
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._handle is not None:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            finally:
                self._handle.close()
                self._handle = None


def is_locked(directory: Path) -> bool:
    """`True` se outro descritor segura o lock do corte. Pasta inexistente → `False`."""
    if not directory.is_dir():
        return False
    try:
        with ClipLock(directory):
            return False
    except ClipLockedError:
        return True
