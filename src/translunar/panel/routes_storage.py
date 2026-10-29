"""Rotas de armazenamento: espaço em disco e exclusão de cortes (RF-27, RF-28, RF-29)."""

from __future__ import annotations

import contextlib
import os
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from translunar.core.config import Settings
from translunar.core.errors import ClipLockedError, UsageError
from translunar.core.lock import ClipLock, is_locked
from translunar.core.models import VIDEO_EXTENSIONS
from translunar.core.state import clip_dir, validate_clip_id
from translunar.panel.auth import MUTATING, PROTECTED

router = APIRouter(prefix="/api")

TARGETS = ("original", "saidas", "tudo")
CONTEXT_SUFFIX = ".contexto.md"
BUSY_DETAIL = "corte em processamento"


def tree_size(path: Path) -> int:
    """Soma recursiva dos tamanhos dos arquivos, sem seguir links simbólicos."""
    try:
        if path.is_symlink():
            return 0
        if path.is_file():
            return path.stat().st_size
    except OSError:
        return 0
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                entry = Path(root) / name
                if not entry.is_symlink():
                    total += entry.stat().st_size
            except OSError:
                continue
    return total


def find_video(input_dir: Path, clip_id: str) -> Path | None:
    """Vídeo de `entrada/` cujo nome sem extensão é o id do corte."""
    if not input_dir.is_dir():
        return None
    for path in input_dir.iterdir():
        if path.stem == clip_id and path.suffix.lower() in VIDEO_EXTENSIONS and path.is_file():
            return path
    return None


def context_files(video: Path) -> list[Path]:
    """Arquivos de contexto do vídeo (`<video>.contexto.md`), com ou sem a extensão no nome."""
    candidates = (
        video.with_name(video.name + CONTEXT_SUFFIX),
        video.with_name(video.stem + CONTEXT_SUFFIX),
    )
    unique: list[Path] = []
    for candidate in candidates:
        if candidate.is_file() and candidate not in unique:
            unique.append(candidate)
    return unique


def clip_total_bytes(settings: Settings, video: Path, clip_id: str) -> int:
    """Vídeo + contexto + `saida/<id>/` (RF-27)."""
    total = tree_size(video) + sum(tree_size(path) for path in context_files(video))
    with contextlib.suppress(UsageError):
        total += tree_size(clip_dir(settings.output_dir, clip_id))
    return total


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _inside(path: Path, base: Path) -> bool:
    return path.resolve().is_relative_to(base.resolve())


def _plan(settings: Settings, clip_id: str, target: str) -> tuple[Path, list[Path]]:
    """Pasta do corte e lista do que apagar, já conferida contra `entrada/` e `saida/`."""
    directory = clip_dir(settings.output_dir, clip_id)
    video = find_video(settings.input_dir, clip_id)
    paths: list[Path] = []
    if target in ("original", "tudo") and video is not None:
        paths.append(video)
        paths.extend(context_files(video))
    if target in ("saidas", "tudo") and directory.is_dir():
        paths.append(directory)
    for path in paths:
        allowed = _inside(path, settings.input_dir) or _inside(path, settings.output_dir)
        # A própria pasta-raiz nunca é alvo: só o que está dentro dela.
        is_root = path.resolve() in (settings.input_dir.resolve(), settings.output_dir.resolve())
        if not allowed or is_root:
            raise HTTPException(status_code=400, detail="caminho fora das pastas do Translunar")
    return directory, paths


@router.get("/disco", dependencies=PROTECTED)
def disk_usage(request: Request) -> dict[str, int]:
    settings = _settings(request)
    probe = settings.data_dir
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    usage = shutil.disk_usage(probe)
    return {
        "total_bytes": usage.total,
        "usado_bytes": usage.used,
        "livre_bytes": usage.free,
        "dados_bytes": tree_size(settings.input_dir) + tree_size(settings.output_dir),
    }


@router.delete("/cortes/{clip_id}", dependencies=MUTATING)
def delete_clip(clip_id: str, request: Request, alvo: str = "tudo") -> dict[str, Any]:
    settings = _settings(request)
    try:
        validate_clip_id(clip_id)
    except UsageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if alvo not in TARGETS:
        raise HTTPException(status_code=400, detail="alvo inválido: use original, saidas ou tudo")
    try:
        directory = clip_dir(settings.output_dir, clip_id)
    except UsageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if find_video(settings.input_dir, clip_id) is None and not directory.is_dir():
        raise HTTPException(status_code=404, detail="corte não encontrado")
    jobs = getattr(request.app.state, "jobs", None)
    if (jobs is not None and jobs.is_busy(clip_id)) or is_locked(directory):
        raise HTTPException(status_code=409, detail=BUSY_DETAIL)
    try:
        directory, paths = _plan(settings, clip_id, alvo)
    except UsageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    freed = sum(tree_size(path) for path in paths)
    try:
        # Segura o lock durante a exclusão: um job que comece agora espera de fora.
        with ClipLock(directory) if directory.is_dir() else _NoLock():
            for path in paths:
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
    except ClipLockedError as exc:
        raise HTTPException(status_code=409, detail=BUSY_DETAIL) from exc
    return {"liberado_bytes": freed}


class _NoLock:
    """Substituto do lock quando a pasta do corte não existe."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *_args: object) -> None:
        return None
