"""Testes da segmentação em legendas curtas (CT-06)."""

from __future__ import annotations

from translunar.core.models import Cue, SubtitleLimits
from translunar.core.segmentation import Segment, Word, segment_words, wrap_text

LIMITS = SubtitleLimits()


def make_segment(sentence: str, start: float = 0.0, step: float = 0.3) -> Segment:
    """Gera palavras de `step` segundos cada a partir de uma frase."""
    words = []
    t = start
    for token in sentence.split():
        words.append(Word(t, t + step, token))
        t += step
    return Segment(start, t, sentence, tuple(words))


def check_limits(cues: list[Cue]) -> None:
    for i, cue in enumerate(cues):
        lines = cue.text.split("\n")
        assert len(lines) <= LIMITS.max_lines
        assert all(len(line) <= LIMITS.max_chars_per_line for line in lines)
        assert (cue.end_ms - cue.start_ms) / 1000 <= LIMITS.max_duration_s
        assert cue.index == i + 1
        if i + 1 < len(cues):
            assert cue.end_ms <= cues[i + 1].start_ms


def test_long_text_respects_limits() -> None:
    sentence = " ".join(f"palavra{i % 7}" for i in range(60))
    cues = segment_words([make_segment(sentence)], LIMITS)
    assert len(cues) > 1
    check_limits(cues)


def test_short_phrase_extended_to_min_duration() -> None:
    cues = segment_words([make_segment("Oi.")], LIMITS)
    assert len(cues) == 1
    assert cues[0].end_ms - cues[0].start_ms >= 1000


def test_short_phrase_not_extended_past_next_cue() -> None:
    limits = SubtitleLimits(max_lines=1, max_chars_per_line=10)
    cues = segment_words([make_segment("aaaa bbbbbbbb")], limits)
    assert [c.text for c in cues] == ["aaaa", "bbbbbbbb"]
    assert cues[0].end_ms == cues[1].start_ms == 300
    assert cues[1].end_ms - cues[1].start_ms >= 1000


def test_breaks_on_punctuation() -> None:
    segments = [make_segment("Oi, tudo bem? Vamos começar.", step=0.5)]
    cues = segment_words(segments, LIMITS)
    assert len(cues) == 2
    assert cues[0].text.endswith("bem?")
    check_limits(cues)


def test_huge_word_is_its_own_cue() -> None:
    huge = "x" * 40
    cues = segment_words([make_segment(f"antes {huge} depois")], LIMITS)
    assert [c.text for c in cues] == ["antes", huge, "depois"]


def test_segment_without_words_is_one_word() -> None:
    cues = segment_words([Segment(1.0, 3.0, "  olá mundo ")], LIMITS)
    assert cues == [Cue(1, 1000, 3000, "olá mundo")]


def test_empty_input() -> None:
    assert segment_words([], LIMITS) == []


def test_wrap_text_balanced() -> None:
    assert wrap_text("curto", 2, 32) == "curto"
    assert wrap_text("aaaa bbbb cccc dddd", 2, 10) == "aaaa bbbb\ncccc dddd"


def test_wrap_text_returns_none_when_not_fitting() -> None:
    assert wrap_text("a" * 40, 2, 32) is None
    assert wrap_text("aaaa bbbb cccc dddd", 1, 10) is None
    assert wrap_text("aaaa bbbb cccc dddd eeee ffff", 2, 10) is None


def test_wrap_text_three_lines() -> None:
    assert wrap_text("aaaa bbbb cccc dddd eeee ffff", 3, 10) == "aaaa bbbb\ncccc dddd\neeee ffff"
