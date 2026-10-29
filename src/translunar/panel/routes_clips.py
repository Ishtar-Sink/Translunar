"""Rotas do acervo: listagem de cortes, miniatura e upload em streaming (RNF-01)."""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from python_multipart.multipart import MultipartParser, parse_options_header

from translunar.core.config import Settings
from translunar.core.errors import UsageError
from translunar.core.lock import is_locked
from translunar.core.models import VIDEO_EXTENSIONS
from translunar.core.probe import ProbeError, extract_thumbnail, is_vertical_9_16, probe_video
from translunar.core.state import (
    clip_dir,
    clip_id_for_video,
    load_state,
    save_state,
)
from translunar.panel.auth import MUTATING, PROTECTED
from translunar.panel.routes_storage import clip_total_bytes

router = APIRouter(prefix="/api")

THUMBNAIL_NAME = "miniatura.jpg"
# Quadro a 10% da duração: o primeiro segundo costuma ser preto ou uma vinheta.
THUMBNAIL_AT_FRACTION = 0.1
# Largura que cabe no cartão 16:9 sem perder nitidez.
THUMBNAIL_WIDTH = 480
UPLOAD_FIELD = "arquivo"
HEADERS_MARGIN = 64 * 1024
FREE_SPACE_MARGIN = 512 * 1024 * 1024
MAX_STEM_LENGTH = 100
_INVALID_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]")


class UploadError(Exception):
    """Falha de validação do upload, com o status HTTP e a mensagem para o usuário."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _is_busy(request: Request, clip_id: str, directory: Path) -> bool:
    jobs = getattr(request.app.state, "jobs", None)
    return bool((jobs is not None and jobs.is_busy(clip_id)) or is_locked(directory))


def _clip_item(request: Request, settings: Settings, video: Path) -> dict[str, Any] | None:
    try:
        clip_id = clip_id_for_video(video.name)
        directory = clip_dir(settings.output_dir, clip_id)
    except UsageError:
        return None
    stat = video.stat()
    busy = _is_busy(request, clip_id, directory)
    state = load_state(directory, clip_id, video.name)
    error: str | None = None
    if state.probe is None:
        try:
            state.probe = probe_video(video, settings.burn.ffprobe)
        except ProbeError as exc:
            error = str(exc)
        else:
            if not busy:  # com um job rodando, quem grava o estado é o job
                save_state(directory, state)
    thumbnail: str | None = None
    if state.probe is not None:
        thumb_path = directory / THUMBNAIL_NAME
        if not thumb_path.exists():
            with contextlib.suppress(ProbeError):  # falha → miniatura: null
                extract_thumbnail(
                    video,
                    thumb_path,
                    settings.burn.ffmpeg,
                    at_s=state.probe.duration_s * THUMBNAIL_AT_FRACTION,
                    width=THUMBNAIL_WIDTH,
                )
        if thumb_path.exists():
            thumbnail = f"/api/cortes/{clip_id}/miniatura"
    warning: str | None = None
    if state.probe is not None and not is_vertical_9_16(state.probe):
        warning = f"Vídeo fora de 9:16 ({state.probe.width}x{state.probe.height})"
    pt_srt = directory / "pt.srt"
    return {
        "id": clip_id,
        "video": video.name,
        "tamanho_bytes": stat.st_size,
        "tamanho_total_bytes": clip_total_bytes(settings, video, clip_id),
        "modificado_em": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        "duracao_s": state.probe.duration_s if state.probe else None,
        "largura": state.probe.width if state.probe else None,
        "altura": state.probe.height if state.probe else None,
        "aviso": warning,
        "miniatura": thumbnail,
        "pt_srt": str(pt_srt.resolve()) if pt_srt.is_file() else None,
        "em_processamento": busy,
        "estado": state.to_dict(),
        "erro": error,
    }


@router.get("/cortes", dependencies=PROTECTED)
def list_clips(request: Request) -> list[dict[str, Any]]:
    settings = _settings(request)
    if not settings.input_dir.is_dir():
        return []
    videos = [
        path
        for path in settings.input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    ]
    videos.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    items = (_clip_item(request, settings, video) for video in videos)
    return [item for item in items if item is not None]


@router.get("/cortes/{clip_id}/miniatura", dependencies=PROTECTED)
def clip_thumbnail(clip_id: str, request: Request) -> FileResponse:
    try:
        thumb = clip_dir(_settings(request).output_dir, clip_id) / THUMBNAIL_NAME
    except UsageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not thumb.is_file():
        raise HTTPException(status_code=404, detail="miniatura não encontrada")
    return FileResponse(thumb, media_type="image/jpeg")


def safe_video_name(filename: str) -> tuple[str, str]:
    """Normaliza o nome enviado: sem acento, só `[A-Za-z0-9._-]`, extensão minúscula."""
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    path = Path(base)
    extension = path.suffix.lower()
    stem = unicodedata.normalize("NFKD", path.stem)
    stem = "".join(char for char in stem if not unicodedata.combining(char))
    stem = _INVALID_CHARS_RE.sub("-", stem)
    stem = re.sub(r"\.{2,}", ".", stem).strip("._-")[:MAX_STEM_LENGTH].strip("._-")
    return stem or "corte", extension


def _stem_taken(directory: Path, stem: str) -> bool:
    return any((directory / f"{stem}{ext}").exists() for ext in VIDEO_EXTENSIONS)


def _publish(part: Path, directory: Path, stem: str, extension: str) -> str:
    """Move o `.part` para um nome livre (`corte.mp4`, `corte-1.mp4`...) sem sobrescrever."""
    number = 0
    while True:
        candidate = stem if number == 0 else f"{stem}-{number}"
        number += 1
        if _stem_taken(directory, candidate):
            continue
        target = directory / f"{candidate}{extension}"
        try:
            os.link(part, target)  # falha se já existe: nunca sobrescreve (corrida entre envios)
        except FileExistsError:
            continue
        part.unlink()
        return target.name


class _UploadSink:
    """Recebe os eventos do parser multipart e grava a parte do arquivo no `.part`."""

    def __init__(self, directory: Path) -> None:
        self.part_path = directory / f".upload-{uuid.uuid4().hex}.part"
        self.filename: str | None = None
        self.parts = 0
        self._handle: BinaryIO | None = None
        self._field = b""
        self._value = b""
        self._headers: dict[bytes, bytes] = {}
        self.bytes_written = 0

    def callbacks(self) -> dict[str, Any]:
        return {
            "on_part_begin": self._on_part_begin,
            "on_header_field": self._on_header_field,
            "on_header_value": self._on_header_value,
            "on_header_end": self._on_header_end,
            "on_headers_finished": self._on_headers_finished,
            "on_part_data": self._on_part_data,
            "on_part_end": self._on_part_end,
        }

    def _on_part_begin(self) -> None:
        self.parts += 1
        self._headers = {}

    def _on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._field += data[start:end]

    def _on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._value += data[start:end]

    def _on_header_end(self) -> None:
        self._headers[self._field.lower()] = self._value
        self._field = b""
        self._value = b""

    def _on_headers_finished(self) -> None:
        if self.parts > 1 or self.filename is not None:
            raise UploadError(400, "Envie um único arquivo por vez.")
        _, params = parse_options_header(self._headers.get(b"content-disposition", b""))
        name = params.get(b"name", b"").decode("utf-8", "replace")
        raw_filename = params.get(b"filename")
        if name != UPLOAD_FIELD or raw_filename is None:
            raise UploadError(400, "Envie o vídeo no campo 'arquivo'.")
        filename = raw_filename.decode("utf-8", "replace")
        if Path(filename.replace("\\", "/")).suffix.lower() not in VIDEO_EXTENSIONS:
            aceitos = ", ".join(VIDEO_EXTENSIONS)
            raise UploadError(400, f"Formato não suportado. Use um destes: {aceitos}.")
        self.filename = filename
        self._handle = self.part_path.open("wb")

    def _on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._handle is not None:
            self._handle.write(data[start:end])
            self.bytes_written += end - start

    def _on_part_end(self) -> None:
        self.close()

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def discard(self) -> None:
        self.close()
        self.part_path.unlink(missing_ok=True)


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status_code)


@router.post("/cortes/upload", status_code=201, dependencies=MUTATING)
async def upload_clip(request: Request) -> JSONResponse:
    settings = _settings(request)
    raw_length = request.headers.get("content-length")
    if raw_length is None or not raw_length.isdigit():
        return _error(411, "O tamanho do envio não foi informado.")
    length = int(raw_length)
    limit_mb = settings.panel.upload_limit_mb
    if length > limit_mb * 1024 * 1024 + HEADERS_MARGIN:
        return _error(413, f"Arquivo acima do limite de {limit_mb} MB.")
    settings.input_dir.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(settings.input_dir).free < length + FREE_SPACE_MARGIN:
        return _error(507, "Sem espaço livre no servidor para este arquivo.")
    content_type, params = parse_options_header(request.headers.get("content-type", ""))
    boundary = params.get(b"boundary")
    if content_type != b"multipart/form-data" or not boundary:
        return _error(400, "Envio inválido: esperado multipart/form-data.")

    sink = _UploadSink(settings.input_dir)
    parser = MultipartParser(boundary, sink.callbacks())  # type: ignore[arg-type]
    try:
        async for chunk in request.stream():
            await run_in_threadpool(parser.write, chunk)
        await run_in_threadpool(parser.finalize)
        sink.close()
        if sink.filename is None or sink.bytes_written == 0:
            raise UploadError(400, "Nenhum arquivo recebido.")
        stem, extension = safe_video_name(sink.filename)
        name = await run_in_threadpool(
            _publish, sink.part_path, settings.input_dir, stem, extension
        )
    except UploadError as exc:
        sink.discard()
        return _error(exc.status_code, exc.detail)
    except BaseException:
        sink.discard()  # desconexão ou erro inesperado: nada fica em `entrada/` (CB-05)
        raise
    sink.discard()
    return JSONResponse({"id": clip_id_for_video(name), "video": name}, status_code=201)
