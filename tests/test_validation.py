"""Testes da validação de traduções (CT-13 e CT-14)."""

from __future__ import annotations

from translunar.core.models import Cue, SubtitleLimits
from translunar.core.srt import format_srt
from translunar.core.validation import Problem, check_limits, validate_translation

LIMITS = SubtitleLimits()
SOURCE = [
    Cue(1, 0, 2000, "Um"),
    Cue(2, 2000, 4000, "Dois"),
    Cue(3, 4000, 6000, "Três"),
]


def _translated(*cues: Cue) -> str:
    return format_srt(cues)


def test_identical_short_passes() -> None:
    assert validate_translation(SOURCE, _translated(*SOURCE), LIMITS) == []


def test_missing_id() -> None:
    problems = validate_translation(SOURCE, _translated(SOURCE[0], SOURCE[2]), LIMITS)
    assert [(p.id, p.kind) for p in problems] == [(2, "missing_id")]


def test_duplicate_id() -> None:
    problems = validate_translation(SOURCE, _translated(*SOURCE, SOURCE[2]), LIMITS)
    assert [(p.id, p.kind) for p in problems] == [(3, "duplicate_id")]


def test_extra_id() -> None:
    extra = Cue(9, 6000, 8000, "Nove")
    problems = validate_translation(SOURCE, _translated(*SOURCE, extra), LIMITS)
    assert [(p.id, p.kind) for p in problems] == [(9, "extra_id")]


def test_timestamp_differs() -> None:
    changed = Cue(1, 0, 2200, "Um")
    problems = validate_translation(SOURCE, _translated(changed, SOURCE[1], SOURCE[2]), LIMITS)
    assert [(p.id, p.kind) for p in problems] == [(1, "timestamp")]
    assert (
        problems[0].detail
        == "00:00:00,000 --> 00:00:02,200 difere de 00:00:00,000 --> 00:00:02,000"
    )


def test_format_error_is_single_problem() -> None:
    problems = validate_translation(SOURCE, "só texto solto\nsem timestamp\n", LIMITS)
    assert len(problems) == 1
    assert problems[0].kind == "format"
    assert problems[0].id is None


def test_three_lines() -> None:
    cue = Cue(1, 0, 6000, "a\nb\nc")
    problems = check_limits([cue], LIMITS)
    assert [(p.id, p.kind, p.detail) for p in problems] == [(1, "lines", "3 > 2")]


def test_long_line() -> None:
    cue = Cue(1, 0, 6000, "x" * 40)
    problems = check_limits([cue], LIMITS)
    assert [(p.kind, p.detail) for p in problems] == [("chars", "40 > 32 (linha 1)")]


def test_cps() -> None:
    cue = Cue(1, 0, 2000, "a" * 16 + "\n" + "b" * 24)
    problems = check_limits([cue], LIMITS)
    assert [(p.kind, p.detail) for p in problems] == [("cps", "20.0 > 17")]


def test_problem_to_dict() -> None:
    problem = Problem(12, "cps", "19.4 > 17")
    assert problem.to_dict() == {"id": 12, "kind": "cps", "detail": "19.4 > 17"}
