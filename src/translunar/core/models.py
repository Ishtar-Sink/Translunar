"""Tipos compartilhados pelo núcleo, pela CLI e pelo painel."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Extensões de vídeo aceitas no acervo de entrada (RF-01).
VIDEO_EXTENSIONS: tuple[str, ...] = (".mp4", ".mov", ".mkv", ".webm", ".m4v")


class StepState(StrEnum):
    """Estado de uma etapa (transcrição, tradução ou queima) de um corte."""

    AGUARDANDO = "aguardando"
    TRANSCREVENDO = "transcrevendo"
    TRANSCRITO = "transcrito"
    TRADUZIDO = "traduzido"
    QUEIMANDO = "queimando"
    PRONTO = "pronto"
    DESATUALIZADO = "desatualizado"
    INTERROMPIDO = "interrompido"
    ERRO = "erro"


@dataclass(frozen=True)
class Cue:
    """Uma legenda: id, início e fim em milissegundos e o texto (linhas separadas por \\n)."""

    index: int
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class SubtitleLimits:
    """Limites de legenda (RN-04 e RN-05). Os valores reais vêm do config.yaml."""

    max_lines: int = 2
    max_chars_per_line: int = 32
    max_cps: float = 17.0
    min_duration_s: float = 1.0
    max_duration_s: float = 6.0


@dataclass(frozen=True)
class SubtitleStyle:
    """Estilo da legenda, igual na prévia e na queima (RN-08)."""

    font_file: str
    bold: bool = True
    text_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    size_pct_width: float = 5.8
    margin_bottom_pct: float = 20.0
    margin_side_pct: float = 8.0


@dataclass(frozen=True)
class ProbeResult:
    """Dados do vídeo lidos pelo ffprobe."""

    width: int
    height: int
    duration_s: float
    has_audio: bool
