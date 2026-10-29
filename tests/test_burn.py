"""Testes da queima: ASS, comando do ffmpeg e queima real com vídeo sintético (CT-16)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from translunar.core.burn import (
    ass_timestamp,
    build_burn_command,
    burn_cues,
    cues_to_ass,
    escape_filter_path,
    hex_to_ass,
)
from translunar.core.config import PROJECT_ROOT, BurnSettings
from translunar.core.errors import DependencyMissingError, TranslunarError
from translunar.core.models import Cue, ProbeResult, SubtitleStyle
from translunar.core.probe import probe_video

FONT = PROJECT_ROOT / "assets" / "fonts" / "Inter-Bold.ttf"
STYLE = SubtitleStyle(font_file="assets/fonts/Inter-Bold.ttf")
CUES = [
    Cue(index=1, start_ms=0, end_ms=900, text="Olá, mundo\nsegunda linha {x}"),
    Cue(index=2, start_ms=1000, end_ms=1900, text="Outra legenda"),
]


def _burn_settings() -> BurnSettings:
    return BurnSettings(ffmpeg="ffmpeg", ffprobe="ffprobe", preset="ultrafast", crf=20, jobs=1)


def test_hex_to_ass() -> None:
    assert hex_to_ass("#FFFFFF") == "&H00FFFFFF"
    assert hex_to_ass("#FF0000") == "&H000000FF"
    assert hex_to_ass("#102030") == "&H00302010"


def test_ass_timestamp() -> None:
    assert ass_timestamp(3723450) == "1:02:03.45"
    assert ass_timestamp(0) == "0:00:00.00"


def test_cues_to_ass_style_and_events() -> None:
    ass = cues_to_ass(CUES, 360, 640, STYLE)
    assert "PlayResX: 360" in ass
    assert "PlayResY: 640" in ass
    assert "WrapStyle: 2" in ass
    assert "Style: Default,Inter,21,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1," in ass
    assert ",2,29,29,128,1" in ass
    assert "\\N" in ass
    assert "{" not in ass
    assert "(x)" in ass
    assert "Dialogue: 0,0:00:00.00,0:00:00.90,Default,,0,0,0,,Olá, mundo\\Nsegunda" in ass


def test_escape_filter_path() -> None:
    assert escape_filter_path(Path("/a/b c/it's:x")) == "/a/b c/it\\'s\\:x"
    assert escape_filter_path(Path("C:\\x")) == "C\\:\\\\x"


def test_build_burn_command_is_list() -> None:
    cmd = build_burn_command(
        "ffmpeg", Path("/v.mp4"), Path("/s.ass"), Path("/fonts"), Path("/o.mp4"), "veryfast", 20
    )
    assert isinstance(cmd, list)
    assert cmd[cmd.index("-c:a") + 1] == "copy"
    assert cmd[cmd.index("-crf") + 1] == "20"
    assert cmd[cmd.index("-vf") + 1] == "ass=filename='/s.ass':fontsdir='/fonts'"
    assert "shell" not in cmd
    assert cmd[-1] == "/o.mp4"


@pytest.mark.ffmpeg
def test_burn_real_video(tmp_path: Path, make_video: Callable[..., Path]) -> None:
    video = make_video(width=360, height=640, duration=2.0)
    probe = probe_video(video)
    output = tmp_path / "saida" / "corte.mp4"
    output.parent.mkdir()
    progress: list[float] = []
    result = burn_cues(video, CUES, output, probe, STYLE, _burn_settings(), FONT, progress.append)
    assert result == output
    burned = probe_video(output)
    assert (burned.width, burned.height) == (probe.width, probe.height)
    assert abs(burned.duration_s - probe.duration_s) <= 0.1
    assert burned.has_audio
    assert progress[-1] == 1.0
    assert all(0.0 <= p <= 1.0 for p in progress)
    assert sorted(p.name for p in output.parent.iterdir()) == ["corte.mp4"]


@pytest.mark.ffmpeg
def test_burn_corrupted_input(tmp_path: Path, make_video: Callable[..., Path]) -> None:
    video = tmp_path / "ruim.mp4"
    video.write_bytes(b"isto nao e um video")
    output = tmp_path / "saida" / "ruim.mp4"
    output.parent.mkdir()
    probe = ProbeResult(width=360, height=640, duration_s=2.0, has_audio=True)
    with pytest.raises(TranslunarError):
        burn_cues(video, CUES, output, probe, STYLE, _burn_settings(), FONT, lambda _p: None)
    assert list(output.parent.iterdir()) == []


def test_burn_missing_font(tmp_path: Path) -> None:
    probe = ProbeResult(width=360, height=640, duration_s=2.0, has_audio=True)
    with pytest.raises(DependencyMissingError):
        burn_cues(
            tmp_path / "v.mp4",
            CUES,
            tmp_path / "o.mp4",
            probe,
            STYLE,
            _burn_settings(),
            tmp_path / "nao-existe.ttf",
            lambda _p: None,
        )
