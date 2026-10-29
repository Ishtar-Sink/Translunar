"""Rotas de queima, download com Range e .zip do corte (RF-21, RF-25, RF-26)."""

from __future__ import annotations

import json
import re
import threading
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from translunar.core.config import Settings
from translunar.core.errors import ClipLockedError, UsageError
from translunar.core.models import StepState
from translunar.core.pipeline import list_clip_states, refresh_clip, run_burn
from translunar.core.state import ClipState, clip_dir
from translunar.panel.auth import MUTATING, PROTECTED

router = APIRouter(prefix="/api")

_LANG_RE = re.compile(r"^[a-z]{2,3}$")
_FILE_RE = re.compile(r"^([a-z]{2,3})\.(srt|mp4)$")
_MEDIA_TYPES = {"mp4": "video/mp4", "srt": "application/x-subrip"}

# Idiomas do mesmo corte queimam um de cada vez: o `run_burn` segura o lock do corte e
# recusaria a segunda queima com "corte em processamento". Cortes diferentes seguem em paralelo.
_burn_locks: dict[str, threading.Lock] = {}
_burn_locks_guard = threading.Lock()


def _burn_lock(clip_id: str) -> threading.Lock:
    with _burn_locks_guard:
        return _burn_locks.setdefault(clip_id, threading.Lock())


def _serialized_burn(
    settings: Settings, clip_id: str, language: str, force: bool, progress: Any
) -> None:
    with _burn_lock(clip_id):
        run_burn(settings, clip_id, language, force=force, on_progress=progress)


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _locate(request: Request, clip_id: str) -> tuple[Settings, Path]:
    """Valida o `clip_id` (400) e confere que a pasta do corte existe (404)."""
    settings = _settings(request)
    try:
        directory = clip_dir(settings.output_dir, clip_id)
    except UsageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not directory.is_dir():
        raise HTTPException(status_code=404, detail="Corte não encontrado.")
    return settings, directory


def _fresh_state(request: Request, settings: Settings, clip_id: str) -> ClipState:
    """Estado com a desatualização recalculada; só grava quando não há job no corte."""
    jobs = getattr(request.app.state, "jobs", None)
    try:
        if jobs is not None and jobs.is_busy(clip_id):
            return list_clip_states(settings, clip_id)[0]  # quem grava o estado é o job
        return refresh_clip(settings, clip_id)
    except UsageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def _burn_body(request: Request) -> tuple[list[str], bool]:
    try:
        data: Any = json.loads(await request.body())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="JSON inválido.") from exc
    languages = data.get("idiomas") if isinstance(data, dict) else None
    if (
        not isinstance(languages, list)
        or not languages
        or not all(isinstance(item, str) and _LANG_RE.fullmatch(item) for item in languages)
        or "pt" in languages
    ):
        raise HTTPException(status_code=400, detail="Escolha ao menos um idioma válido.")
    return list(dict.fromkeys(languages)), data.get("forcar") is True


@router.post("/cortes/{clip_id}/queimar", status_code=202, dependencies=MUTATING)
async def burn(clip_id: str, request: Request) -> dict[str, list[str]]:
    settings, _ = _locate(request, clip_id)
    languages, force = await _burn_body(request)
    state = await run_in_threadpool(_fresh_state, request, settings, clip_id)
    for language in languages:  # CB-14: recusa tudo antes de enfileirar qualquer idioma
        record = state.translations.get(language)
        if record is None or record.state != StepState.TRADUZIDO:
            raise HTTPException(
                status_code=409, detail=f"tradução de {language} ausente ou desatualizada"
            )
    jobs = request.app.state.jobs
    for language in languages:
        try:
            jobs.submit(
                "burn",
                clip_id,
                language,
                lambda progress, language=language: _serialized_burn(
                    settings, clip_id, language, force, progress
                ),
            )
        except ClipLockedError as exc:
            raise HTTPException(
                status_code=409, detail=f"a queima de {language} já está em andamento"
            ) from exc
    return {"idiomas": languages}


@router.get("/cortes/{clip_id}/idiomas", dependencies=PROTECTED)
def languages(clip_id: str, request: Request) -> dict[str, dict[str, Any]]:
    """Idiomas do corte com o estado atual (desatualização calculada) e os arquivos prontos."""
    settings, directory = _locate(request, clip_id)
    try:
        state = list_clip_states(settings, clip_id)[0]
    except UsageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result: dict[str, dict[str, Any]] = {}
    for language, record in sorted(state.translations.items()):
        burn_record = state.burns.get(language)
        result[language] = {
            "traducao": str(record.state),
            "queima": str(burn_record.state) if burn_record else None,
            "progresso": burn_record.progress if burn_record else 0.0,
            "erro": burn_record.error if burn_record else None,
            "mp4": (directory / f"{language}.mp4").is_file(),
        }
    return result


@router.get("/cortes/{clip_id}/arquivos/{name}", dependencies=PROTECTED)
def download(clip_id: str, name: str, request: Request, baixar: int = 0) -> FileResponse:
    _, directory = _locate(request, clip_id)
    match = _FILE_RE.fullmatch(name)
    if match is None:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")
    path = directory / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    headers = {"Content-Disposition": f'attachment; filename="{clip_id}-{name}"'} if baixar else {}
    return FileResponse(path, media_type=_MEDIA_TYPES[match.group(2)], headers=headers)


def _build_zip(directory: Path, target: Path) -> bool:
    """Monta o .zip do corte; devolve False quando não há nenhum vídeo pronto."""
    videos = sorted(directory.glob("*.mp4"))
    videos = [path for path in videos if _FILE_RE.fullmatch(path.name)]
    if not videos:
        return False
    subtitles = [
        path
        for path in sorted(directory.glob("*.srt"))
        if _FILE_RE.fullmatch(path.name) or path.name == "pt.srt"
    ]
    with zipfile.ZipFile(target, "w") as archive:
        for path in subtitles:
            archive.write(path, path.name, compress_type=zipfile.ZIP_DEFLATED)
        for path in videos:
            archive.write(path, path.name, compress_type=zipfile.ZIP_STORED)
    return True


@router.get("/cortes/{clip_id}/zip", dependencies=PROTECTED)
async def download_zip(clip_id: str, request: Request) -> FileResponse:
    _, directory = _locate(request, clip_id)
    target = directory / f".zip-{uuid.uuid4().hex}.zip"
    try:
        built = await run_in_threadpool(_build_zip, directory, target)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    if not built:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail="Nenhum vídeo pronto neste corte.")
    return FileResponse(
        target,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{clip_id}.zip"'},
        background=BackgroundTask(target.unlink, missing_ok=True),
    )
