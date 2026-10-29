"""Leitura, escrita e gravação atômica de arquivos SRT."""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from pathlib import Path

from translunar.core.errors import SrtParseError
from translunar.core.models import Cue

_TIMESTAMP_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})$")
_SEPARATOR = " --> "


def format_timestamp(ms: int) -> str:
    """Formata milissegundos como `HH:MM:SS,mmm`."""
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def parse_timestamp(value: str) -> int:
    """Converte `HH:MM:SS,mmm` em milissegundos; qualquer outro formato levanta ValueError."""
    match = _TIMESTAMP_RE.match(value)
    if match is None:
        raise ValueError(f"timestamp inválido: {value!r}")
    hours, minutes, seconds, millis = (int(g) for g in match.groups())
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def _split_blocks(lines: list[str]) -> list[tuple[int, list[str]]]:
    """Agrupa linhas não vazias em blocos, com a linha (1-based) onde cada bloco começa."""
    blocks: list[tuple[int, list[str]]] = []
    current: list[str] = []
    start = 0
    for number, line in enumerate(lines, start=1):
        if line.strip() == "":
            if current:
                blocks.append((start, current))
                current = []
        else:
            if not current:
                start = number
            current.append(line)
    if current:
        blocks.append((start, current))
    return blocks


def parse_srt(text: str) -> list[Cue]:
    """Lê um SRT. Levanta SrtParseError com a linha do problema; os ids não são renumerados."""
    text = text.removeprefix("﻿").replace("\r\n", "\n")
    if text.strip() == "":
        raise SrtParseError(1, "SRT vazio")

    cues: list[Cue] = []
    for start, block in _split_blocks(text.split("\n")):
        id_text = block[0].strip()
        if not id_text.isascii() or not id_text.isdigit():
            raise SrtParseError(start, "id inválido")
        time_line_no = start + 1
        if len(block) < 2:
            raise SrtParseError(time_line_no, "timestamp inválido")
        parts = block[1].split(_SEPARATOR)
        if len(parts) != 2:
            raise SrtParseError(time_line_no, "timestamp inválido")
        try:
            start_ms = parse_timestamp(parts[0])
            end_ms = parse_timestamp(parts[1])
        except ValueError:
            raise SrtParseError(time_line_no, "timestamp inválido") from None
        if end_ms < start_ms:
            raise SrtParseError(time_line_no, "fim antes do início")
        if len(block) < 3:
            raise SrtParseError(start + 2, "texto ausente")
        cues.append(Cue(int(id_text), start_ms, end_ms, "\n".join(block[2:])))
    return cues


def format_srt(cues: Sequence[Cue]) -> str:
    """Gera o texto SRT: blocos separados por uma linha vazia, terminando com `\\n`."""
    blocks = [
        f"{c.index}\n{format_timestamp(c.start_ms)}{_SEPARATOR}{format_timestamp(c.end_ms)}\n{c.text}"
        for c in cues
    ]
    return "\n\n".join(blocks) + "\n"


def read_srt(path: Path) -> list[Cue]:
    """Lê um arquivo SRT em UTF-8."""
    return parse_srt(path.read_text(encoding="utf-8"))


def write_srt_atomic(path: Path, cues: Sequence[Cue]) -> None:
    """Grava num arquivo temporário na mesma pasta e renomeia, sem deixar SRT parcial."""
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_text(format_srt(cues), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
