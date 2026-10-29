"""Testes da transcrição e do fluxo do vídeo às legendas (CT-05)."""

from __future__ import annotations

import importlib.util
import shutil
import sys
import types
from collections.abc import Callable
from pathlib import Path

import pytest

from translunar.core.errors import DependencyMissingError, NoSpeechError, ProbeError
from translunar.core.models import SubtitleLimits
from translunar.core.segmentation import Segment, Word
from translunar.core.transcription import (
    FakeTranscriber,
    MlxWhisperTranscriber,
    transcribe_to_cues,
)

FFPROBE = shutil.which("ffprobe") or "ffprobe"
LIMITS = SubtitleLimits()

SEGMENTS = [
    Segment(0.0, 1.0, "Olá pessoal.", (Word(0.0, 0.5, " Olá"), Word(0.5, 1.0, " pessoal."))),
    Segment(1.2, 2.5, "Vamos lá", (Word(1.2, 1.8, " Vamos"), Word(1.8, 2.5, " lá"))),
]


def test_transcribe_to_cues(make_video: Callable[..., Path]) -> None:
    video = make_video(duration=3.0)
    progress: list[float] = []
    probe, cues = transcribe_to_cues(
        video, FakeTranscriber(SEGMENTS), LIMITS, FFPROBE, progress.append
    )
    assert (probe.width, probe.height) == (360, 640)
    assert probe.has_audio
    assert cues
    assert all(c.text.strip() for c in cues)
    assert progress[-1] == 1.0


def test_no_speech(make_video: Callable[..., Path]) -> None:
    video = make_video()
    with pytest.raises(NoSpeechError, match="nenhuma fala detectada"):
        transcribe_to_cues(video, FakeTranscriber([]), LIMITS, FFPROBE, lambda _: None)


def test_blank_segments_are_no_speech(make_video: Callable[..., Path]) -> None:
    video = make_video()
    blank = FakeTranscriber([Segment(0.0, 1.0, "  ", (Word(0.0, 1.0, " "),))])
    with pytest.raises(NoSpeechError):
        transcribe_to_cues(video, blank, LIMITS, FFPROBE, lambda _: None)


def test_no_audio(make_video: Callable[..., Path]) -> None:
    video = make_video(audio=False)
    with pytest.raises(ProbeError, match="sem áudio"):
        transcribe_to_cues(video, FakeTranscriber(SEGMENTS), LIMITS, FFPROBE, lambda _: None)


@pytest.mark.skipif(
    importlib.util.find_spec("mlx_whisper") is not None, reason="mlx-whisper instalado"
)
def test_mlx_whisper_missing(tmp_path: Path) -> None:
    with pytest.raises(DependencyMissingError, match="uv sync --extra mac"):
        MlxWhisperTranscriber("x").transcribe(tmp_path / "a.mp4", 1.0, lambda _: None)


def _install_fake_mlx(monkeypatch: pytest.MonkeyPatch, tqdm_module: types.ModuleType) -> None:
    """Simula o pacote mlx_whisper: a função `transcribe` usa `tqdm.tqdm` do módulo."""
    package = types.ModuleType("mlx_whisper")
    inner = types.ModuleType("mlx_whisper.transcribe")
    inner.tqdm = tqdm_module  # type: ignore[attr-defined]
    calls: dict[str, object] = {}

    def transcribe(audio: str, **kwargs: object) -> dict[str, object]:
        calls.update(kwargs)
        with inner.tqdm.tqdm(total=100, unit="frames") as bar:  # type: ignore[attr-defined]
            bar.update(50)
            bar.update(50)
        return {
            "segments": [
                {
                    "start": 0.0,
                    "end": 1.0,
                    "text": " oi",
                    "words": [{"word": " oi", "start": 0.0, "end": 1.0}],
                }
            ]
        }

    package.transcribe = transcribe  # type: ignore[attr-defined]
    package.calls = calls  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mlx_whisper", package)
    monkeypatch.setitem(sys.modules, "mlx_whisper.transcribe", inner)


def test_mlx_progress_hook(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tqdm_module = pytest.importorskip("tqdm")
    _install_fake_mlx(monkeypatch, tqdm_module)
    progress: list[float] = []
    segments = MlxWhisperTranscriber("modelo").transcribe(tmp_path / "a.mp4", 1.0, progress.append)
    assert progress == [0.5, 0.99, 1.0]
    assert segments == [Segment(0.0, 1.0, " oi", (Word(0.0, 1.0, " oi"),))]
    calls = sys.modules["mlx_whisper"].calls  # type: ignore[attr-defined]
    assert calls["language"] == "pt"
    assert calls["condition_on_previous_text"] is False
    assert calls["word_timestamps"] is True


def test_mlx_progress_hook_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Versão nova sem o atributo `tqdm`: segue sem progresso intermediário.
    package = types.ModuleType("mlx_whisper")
    package.transcribe = lambda audio, **kw: {"segments": []}  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mlx_whisper", package)
    monkeypatch.setitem(sys.modules, "mlx_whisper.transcribe", types.ModuleType("x"))
    progress: list[float] = []
    assert MlxWhisperTranscriber("m").transcribe(tmp_path / "a.mp4", 1.0, progress.append) == []
    assert progress == [1.0]
