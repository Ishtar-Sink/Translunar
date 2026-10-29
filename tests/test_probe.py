from pathlib import Path

import pytest

from translunar.core.errors import DependencyMissingError, ProbeError
from translunar.core.models import ProbeResult
from translunar.core.probe import (
    extract_thumbnail,
    is_vertical_9_16,
    probe_video,
    require_audio,
)


def test_probe_vertical_video_with_audio(make_video) -> None:  # type: ignore[no-untyped-def]
    result = probe_video(make_video(width=360, height=640, duration=2.0))
    assert (result.width, result.height) == (360, 640)
    assert result.has_audio
    assert 1.8 <= result.duration_s <= 2.3
    assert is_vertical_9_16(result)


def test_video_without_audio_is_rejected(make_video) -> None:  # type: ignore[no-untyped-def]
    result = probe_video(make_video(audio=False))
    assert not result.has_audio
    with pytest.raises(ProbeError, match="sem áudio"):
        require_audio(result)


def test_horizontal_video_is_not_9_16(make_video) -> None:  # type: ignore[no-untyped-def]
    assert not is_vertical_9_16(probe_video(make_video(width=640, height=360)))


def test_corrupted_file_raises_probe_error(tmp_path: Path) -> None:
    broken = tmp_path / "quebrado.mp4"
    broken.write_bytes(b"isto nao e um video")
    with pytest.raises(ProbeError):
        probe_video(broken)


def test_missing_binary_raises_dependency_error(tmp_path: Path) -> None:
    with pytest.raises(DependencyMissingError):
        probe_video(tmp_path / "x.mp4", ffprobe="ffprobe-que-nao-existe")


def test_thumbnail_is_created(make_video, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    thumb = extract_thumbnail(make_video(), tmp_path / "miniatura.jpg", at_s=0.5)
    assert thumb.exists() and thumb.stat().st_size > 0


def test_ratio_helper() -> None:
    assert is_vertical_9_16(ProbeResult(1080, 1920, 10.0, True))
