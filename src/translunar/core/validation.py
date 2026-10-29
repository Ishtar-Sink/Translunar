"""Validação estrutural e de limites de uma tradução contra o `pt.srt` (RF-18, RF-19)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from translunar.core.errors import SrtParseError
from translunar.core.models import Cue, SubtitleLimits
from translunar.core.srt import format_timestamp, parse_srt


@dataclass(frozen=True)
class Problem:
    """Um problema numa legenda. `kind`: format, missing_id, duplicate_id, extra_id,
    timestamp, lines, chars ou cps."""

    id: int | None
    kind: str
    detail: str

    def to_dict(self) -> dict[str, int | str | None]:
        """Forma usada na saída JSON de `legendar validar`."""
        return {"id": self.id, "kind": self.kind, "detail": self.detail}


def cues_per_second(cue: Cue) -> float:
    """Caracteres (sem quebras de linha) por segundo; duração <= 0 dá infinito."""
    duration_s = (cue.end_ms - cue.start_ms) / 1000
    if duration_s <= 0:
        return float("inf")
    return len(cue.text.replace("\n", "")) / duration_s


def check_limits(cues: Sequence[Cue], limits: SubtitleLimits) -> list[Problem]:
    """Confere linhas, caracteres por linha e cps de cada legenda."""
    problems: list[Problem] = []
    for cue in cues:
        lines = cue.text.split("\n")
        if len(lines) > limits.max_lines:
            problems.append(Problem(cue.index, "lines", f"{len(lines)} > {limits.max_lines}"))
        for number, line in enumerate(lines, start=1):
            if len(line) > limits.max_chars_per_line:
                detail = f"{len(line)} > {limits.max_chars_per_line} (linha {number})"
                problems.append(Problem(cue.index, "chars", detail))
        cps = cues_per_second(cue)
        if cps > limits.max_cps:
            problems.append(Problem(cue.index, "cps", f"{cps:.1f} > {limits.max_cps:g}"))
    return problems


def _range(cue: Cue) -> str:
    return f"{format_timestamp(cue.start_ms)} --> {format_timestamp(cue.end_ms)}"


def validate_translation(
    source: Sequence[Cue], translated_text: str, limits: SubtitleLimits
) -> list[Problem]:
    """Valida a tradução contra o `pt.srt`. Lista vazia = aprovado."""
    try:
        translated = parse_srt(translated_text)
    except SrtParseError as error:
        return [Problem(None, "format", str(error))]

    problems: list[Problem] = []
    counts = Counter(c.index for c in translated)
    source_by_id = {c.index: c for c in source}

    for cue_id, count in counts.items():
        if count > 1:
            problems.append(Problem(cue_id, "duplicate_id", f"id repetido {count} vezes"))
    for cue_id in source_by_id:
        if cue_id not in counts:
            problems.append(Problem(cue_id, "missing_id", "id do pt.srt ausente na tradução"))
    for cue_id in counts:
        if cue_id not in source_by_id:
            problems.append(Problem(cue_id, "extra_id", "id inexistente no pt.srt"))

    for cue in translated:
        original = source_by_id.get(cue.index)
        if original is None:
            continue
        if (cue.start_ms, cue.end_ms) != (original.start_ms, original.end_ms):
            problems.append(
                Problem(cue.index, "timestamp", f"{_range(cue)} difere de {_range(original)}")
            )

    problems.extend(check_limits(translated, limits))
    return sorted(problems, key=lambda p: (p.id is None, p.id or 0, p.kind))
