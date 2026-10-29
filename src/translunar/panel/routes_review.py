"""Rotas da revisão: transcrição, `pt.srt`, contexto, prévia WebVTT e vídeo original."""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from translunar.core.config import Settings
from translunar.core.errors import SrtParseError, UsageError
from translunar.core.lock import is_locked
from translunar.core.pipeline import find_video, run_transcription, save_pt_srt, transcriber_for
from translunar.core.srt import read_srt
from translunar.core.state import clip_dir
from translunar.core.webvtt import srt_to_webvtt
from translunar.panel.auth import MUTATING, PROTECTED

router = APIRouter(prefix="/api")

MAX_TEXT_BYTES = 1024 * 1024
_LANG_RE = re.compile(r"^[a-z]{2,3}$")
_TEXT = "text/plain; charset=utf-8"


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _locate(request: Request, clip_id: str) -> tuple[Settings, Path, Path]:
    """Valida o `clip_id` (400) e acha o vídeo em `entrada/` (404)."""
    settings = _settings(request)
    try:
        directory = clip_dir(settings.output_dir, clip_id)
        video = find_video(settings, clip_id)
    except UsageError as exc:
        status = 404 if "não encontrado" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return settings, directory, video


def _busy(request: Request, clip_id: str, directory: Path) -> bool:
    jobs = getattr(request.app.state, "jobs", None)
    return bool((jobs is not None and jobs.is_busy(clip_id)) or is_locked(directory))


async def _text_body(request: Request) -> str:
    raw = await request.body()
    if len(raw) > MAX_TEXT_BYTES:
        raise HTTPException(status_code=413, detail="Texto grande demais.")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="O texto precisa estar em UTF-8.") from exc


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


@router.post("/cortes/{clip_id}/transcrever", status_code=202, dependencies=MUTATING)
async def transcribe(clip_id: str, request: Request) -> dict[str, bool]:
    settings, directory, _ = _locate(request, clip_id)
    force = False
    raw = await request.body()
    if raw.strip():
        try:
            data: Any = json.loads(raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="JSON inválido.") from exc
        force = isinstance(data, dict) and data.get("forcar") is True
    jobs = request.app.state.jobs
    if _busy(request, clip_id, directory):
        raise HTTPException(status_code=409, detail="O corte já está em processamento.")
    jobs.submit(
        "transcription",
        clip_id,
        None,
        lambda progress: run_transcription(
            settings, clip_id, transcriber_for(settings), force=force, on_progress=progress
        ),
    )
    return {"ok": True}


@router.get("/cortes/{clip_id}/pt-srt", dependencies=PROTECTED)
def get_pt_srt(clip_id: str, request: Request) -> Response:
    _, directory, _ = _locate(request, clip_id)
    path = directory / "pt.srt"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Este corte ainda não foi transcrito.")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type=_TEXT)


@router.put("/cortes/{clip_id}/pt-srt", dependencies=MUTATING)
async def put_pt_srt(clip_id: str, request: Request) -> Response:
    settings, directory, _ = _locate(request, clip_id)
    if _busy(request, clip_id, directory):
        raise HTTPException(status_code=409, detail="O corte está em processamento.")
    text = await _text_body(request)
    try:
        state = await run_in_threadpool(save_pt_srt, settings, clip_id, text)
    except SrtParseError as exc:
        return JSONResponse({"detail": str(exc), "linha": exc.line}, status_code=422)
    except UsageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(state.to_dict())


@router.get("/cortes/{clip_id}/contexto", dependencies=PROTECTED)
def get_context(clip_id: str, request: Request) -> Response:
    settings, _, video = _locate(request, clip_id)
    path = settings.input_dir / f"{video.stem}.contexto.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return PlainTextResponse(text, media_type=_TEXT)


@router.put("/cortes/{clip_id}/contexto", dependencies=MUTATING)
async def put_context(clip_id: str, request: Request) -> dict[str, bool]:
    settings, _, video = _locate(request, clip_id)
    text = await _text_body(request)
    await run_in_threadpool(_write_atomic, settings.input_dir / f"{video.stem}.contexto.md", text)
    return {"ok": True}


@router.get("/cortes/{clip_id}/legendas/{language}.vtt", dependencies=PROTECTED)
def subtitle_preview(clip_id: str, language: str, request: Request) -> Response:
    settings, directory, _ = _locate(request, clip_id)
    if not _LANG_RE.fullmatch(language):
        raise HTTPException(status_code=400, detail="Idioma inválido.")
    path = directory / f"{language}.srt"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Legenda não encontrada.")
    try:
        cues = read_srt(path)
    except SrtParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    vtt = srt_to_webvtt(cues, settings.style)
    return Response(vtt, media_type="text/vtt", headers={"Cache-Control": "no-store"})


@router.get("/cortes/{clip_id}/video", dependencies=PROTECTED)
def original_video(clip_id: str, request: Request) -> FileResponse:
    _, _, video = _locate(request, clip_id)
    return FileResponse(video)
