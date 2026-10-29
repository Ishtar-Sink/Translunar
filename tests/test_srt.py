"""Testes da leitura e da escrita de SRT."""

from __future__ import annotations

from pathlib import Path

import pytest

from translunar.core.errors import SrtParseError
from translunar.core.models import Cue
from translunar.core.srt import (
    format_srt,
    format_timestamp,
    parse_srt,
    parse_timestamp,
    read_srt,
    write_srt_atomic,
)

SAMPLE = (
    "1\n00:00:00,000 --> 00:00:02,000\nOlá, mundo\n\n"
    "2\n00:00:02,000 --> 00:00:04,500\nPrimeira linha\nSegunda linha\n\n"
    "3\n00:00:05,000 --> 00:00:07,000\nFim\n"
)


def test_round_trip() -> None:
    cues = parse_srt(SAMPLE)
    assert len(cues) == 3
    assert cues[1].text == "Primeira linha\nSegunda linha"
    assert format_srt(cues) == SAMPLE


def test_bom_and_crlf_accepted() -> None:
    raw = "﻿" + SAMPLE.replace("\n", "\r\n")
    assert parse_srt(raw) == parse_srt(SAMPLE)


def test_ids_are_not_renumbered() -> None:
    cues = parse_srt("7\n00:00:00,000 --> 00:00:01,000\na\n\n9\n00:00:01,000 --> 00:00:02,000\nb\n")
    assert [c.index for c in cues] == [7, 9]


def test_timestamp_helpers() -> None:
    assert format_timestamp(3723004) == "01:02:03,004"
    assert parse_timestamp("01:02:03,004") == 3723004
    with pytest.raises(ValueError):
        parse_timestamp("1:02:03,004")


def test_empty_text() -> None:
    with pytest.raises(SrtParseError) as exc:
        parse_srt("  \n")
    assert exc.value.line == 1
    assert "SRT vazio" in str(exc.value)


def test_invalid_id_line() -> None:
    text = "1\n00:00:00,000 --> 00:00:01,000\na\n\nabc\n00:00:01,000 --> 00:00:02,000\nb\n"
    with pytest.raises(SrtParseError) as exc:
        parse_srt(text)
    assert exc.value.line == 5
    assert "id inválido" in str(exc.value)


def test_invalid_timestamp() -> None:
    with pytest.raises(SrtParseError) as exc:
        parse_srt("1\n00:00:00.000 --> 00:00:01,000\na\n")
    assert exc.value.line == 2
    assert "timestamp inválido" in str(exc.value)


def test_missing_text() -> None:
    with pytest.raises(SrtParseError) as exc:
        parse_srt("1\n00:00:00,000 --> 00:00:01,000\n")
    assert exc.value.line == 3
    assert "texto ausente" in str(exc.value)


def test_end_before_start() -> None:
    with pytest.raises(SrtParseError) as exc:
        parse_srt("1\n00:00:02,000 --> 00:00:01,000\na\n")
    assert exc.value.line == 2
    assert "fim antes do início" in str(exc.value)


def test_write_atomic_leaves_no_tmp(tmp_path: Path) -> None:
    target = tmp_path / "pt.srt"
    cues = [Cue(1, 0, 1000, "a"), Cue(2, 1000, 2000, "b\nc")]
    write_srt_atomic(target, cues)
    assert read_srt(target) == cues
    assert not (tmp_path / ".pt.srt.tmp").exists()
    assert [p.name for p in tmp_path.iterdir()] == ["pt.srt"]
