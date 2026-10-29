"""Leitura de vídeo com ffprobe e extração de miniatura com ffmpeg."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from translunar.core.errors import DependencyMissingError, ProbeError
from translunar.core.models import ProbeResult


def _require_binary(binary: str) -> str:
    """Confirma que o binário existe (no PATH ou como caminho absoluto)."""
    found = shutil.which(binary)
    if found is None:
        raise DependencyMissingError(f"binário não encontrado: {binary}")
    return found


def probe_video(path: Path, ffprobe: str = "ffprobe") -> ProbeResult:
    """Lê largura, altura, duração e presença de áudio (RF-07)."""
    binary = _require_binary(ffprobe)
    cmd = [
        binary,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,width,height:format=duration",
        "-of",
        "json",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise ProbeError(
            f"não foi possível ler o vídeo: {proc.stderr.strip() or 'erro do ffprobe'}"
        )
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ProbeError("saída do ffprobe ilegível") from exc
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise ProbeError("arquivo sem faixa de vídeo")
    try:
        duration = float((data.get("format") or {}).get("duration") or 0)
    except ValueError:
        duration = 0.0
    if duration <= 0:
        raise ProbeError("duração do vídeo inválida")
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    return ProbeResult(
        width=int(video["width"]),
        height=int(video["height"]),
        duration_s=duration,
        has_audio=has_audio,
    )


def require_audio(result: ProbeResult) -> None:
    """Recusa vídeo sem faixa de áudio (CB-01)."""
    if not result.has_audio:
        raise ProbeError("vídeo sem áudio")


def is_vertical_9_16(result: ProbeResult, tolerance: float = 0.01) -> bool:
    """True se a proporção é 9:16; fora disso o painel só mostra um aviso (CB-04)."""
    return abs(result.width / result.height - 9 / 16) <= tolerance


def extract_thumbnail(
    video: Path,
    output: Path,
    ffmpeg: str = "ffmpeg",
    at_s: float = 1.0,
    width: int = 270,
) -> Path:
    """Extrai um quadro JPEG do vídeo para a miniatura do acervo (inferência L)."""
    binary = _require_binary(ffmpeg)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        binary,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{at_s}",
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-vf",
        f"scale={width}:-2",
        str(output),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not output.exists():
        raise ProbeError(f"falha ao extrair miniatura: {proc.stderr.strip()}")
    return output
