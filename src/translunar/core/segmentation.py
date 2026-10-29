"""Reagrupamento das palavras transcritas em legendas curtas para vídeo vertical (RF-08)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from translunar.core.models import Cue, SubtitleLimits

# Pontuação que encerra uma frase e permite fechar a legenda.
_SENTENCE_END: tuple[str, ...] = (".", "?", "!", "…")


@dataclass(frozen=True)
class Word:
    """Uma palavra com início e fim em segundos."""

    start_s: float
    end_s: float
    text: str


@dataclass(frozen=True)
class Segment:
    """Um trecho transcrito; `words` traz as palavras com tempo, quando disponíveis."""

    start_s: float
    end_s: float
    text: str
    words: tuple[Word, ...] = ()


def wrap_text(text: str, max_lines: int, max_chars: int) -> str | None:
    """Quebra o texto em até `max_lines` linhas de até `max_chars`, de forma equilibrada.

    Devolve `None` se não couber.
    """
    if len(text) <= max_chars:
        return text
    if max_lines < 2:
        return None
    best: str | None = None
    best_longest = 0
    for pos, char in enumerate(text):
        if char != " " or pos == 0 or pos > max_chars:
            continue
        first = text[:pos].rstrip()
        rest = wrap_text(text[pos + 1 :].lstrip(), max_lines - 1, max_chars)
        if not first or rest is None:
            continue
        longest = max(len(first), *(len(line) for line in rest.split("\n")))
        if best is None or longest < best_longest:
            best = f"{first}\n{rest}"
            best_longest = longest
    return best


def _collect_words(segments: Sequence[Segment]) -> list[Word]:
    """Junta as palavras de todos os segmentos, sem vazias e sem espaços nas pontas."""
    words: list[Word] = []
    for segment in segments:
        source = segment.words or (Word(segment.start_s, segment.end_s, segment.text),)
        for word in source:
            text = word.text.strip()
            if text:
                words.append(Word(word.start_s, word.end_s, text))
    return words


def _group_words(words: Sequence[Word], limits: SubtitleLimits) -> list[tuple[float, float, str]]:
    """Agrupa as palavras de forma gulosa; devolve (início, fim, texto quebrado)."""
    groups: list[tuple[float, float, str]] = []
    current: list[Word] = []

    def flush() -> None:
        if not current:
            return
        text = " ".join(w.text for w in current)
        wrapped = wrap_text(text, limits.max_lines, limits.max_chars_per_line)
        # Palavra isolada maior que a linha não cabe: sai como está (evita laço infinito).
        groups.append((current[0].start_s, current[-1].end_s, wrapped or text))
        current.clear()

    for word in words:
        if current:
            candidate = " ".join(w.text for w in current) + " " + word.text
            fits = wrap_text(candidate, limits.max_lines, limits.max_chars_per_line) is not None
            too_long = word.end_s - current[0].start_s > limits.max_duration_s
            if not fits or too_long:
                flush()
        current.append(word)
        ends_sentence = word.text.endswith(_SENTENCE_END)
        if ends_sentence and word.end_s - current[0].start_s >= limits.min_duration_s:
            flush()
    flush()
    return groups


def segment_words(segments: Sequence[Segment], limits: SubtitleLimits) -> list[Cue]:
    """Transforma segmentos em legendas dentro dos limites de linhas, caracteres e duração."""
    groups = _group_words(_collect_words(segments), limits)
    starts = [round(start * 1000) for start, _, _ in groups]
    ends = [round(end * 1000) for _, end, _ in groups]
    min_ms = round(limits.min_duration_s * 1000)
    cues: list[Cue] = []
    for i, (_, _, text) in enumerate(groups):
        start, end = starts[i], ends[i]
        next_start = starts[i + 1] if i + 1 < len(groups) else None
        if end - start < min_ms:
            end = start + min_ms
        if next_start is not None:
            end = min(end, max(next_start, start))
        cues.append(Cue(index=i + 1, start_ms=start, end_ms=end, text=text))
    return cues
