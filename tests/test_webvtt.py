"""Testes da conversão para WebVTT (CT-08)."""

from __future__ import annotations

from translunar.core.models import Cue, SubtitleStyle
from translunar.core.srt import format_timestamp
from translunar.core.webvtt import srt_to_webvtt

CUES = [Cue(1, 1000, 2500, "Olá"), Cue(2, 3000, 5000, "Duas\nlinhas")]


def test_header_and_timestamps() -> None:
    vtt = srt_to_webvtt(CUES)
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:01.000 --> 00:00:02.500" in vtt
    assert "," not in vtt


def test_same_times_and_texts() -> None:
    vtt = srt_to_webvtt(CUES)
    for cue in CUES:
        times = f"{format_timestamp(cue.start_ms)} --> {format_timestamp(cue.end_ms)}"
        assert times.replace(",", ".") in vtt
        assert cue.text in vtt


def test_style_position() -> None:
    vtt = srt_to_webvtt(CUES, SubtitleStyle(font_file="x"))
    time_lines = [line for line in vtt.splitlines() if "-->" in line]
    assert len(time_lines) == 2
    for line in time_lines:
        assert "line:80%,end" in line
        assert "size:84%" in line
        assert "position:50%" in line
        assert line.endswith("align:center")


def test_no_style_has_no_settings() -> None:
    vtt = srt_to_webvtt(CUES)
    assert "line:" not in vtt
