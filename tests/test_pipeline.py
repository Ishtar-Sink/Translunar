"""Testes da orquestração com estado e lock (TASK-13: RF-20, RF-24, RN-03, CB-14)."""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from translunar.core.config import CONFIG_DIR_ENV, PROJECT_ROOT, Settings, load_settings
from translunar.core.errors import ClipLockedError, SrtParseError, UsageError
from translunar.core.lock import ClipLock
from translunar.core.models import StepState
from translunar.core.pipeline import (
    TRANSCRIBER_ENV,
    find_video,
    refresh_clip,
    register_translation,
    run_burn,
    run_transcription,
    save_pt_srt,
    transcriber_for,
)
from translunar.core.state import load_state, sha256_file


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    config = tmp_path / "config"
    shutil.copytree(PROJECT_ROOT / "config", config)
    (config / "config.local.yaml").write_text(
        yaml.safe_dump({"pasta_dados": str(tmp_path / "dados")}), encoding="utf-8"
    )
    monkeypatch.setenv(CONFIG_DIR_ENV, str(config))
    monkeypatch.setenv(TRANSCRIBER_ENV, "falso")
    loaded = load_settings()
    loaded.input_dir.mkdir(parents=True)
    return loaded


@pytest.fixture
def clip(settings: Settings, make_video: Callable[..., Path]) -> str:
    video = make_video("corte-01.mp4")
    shutil.move(video, settings.input_dir / "corte-01.mp4")
    return "corte-01"


def _transcribe(settings: Settings, clip_id: str, force: bool = False) -> None:
    run_transcription(settings, clip_id, transcriber_for(settings), force=force)


@pytest.mark.ffmpeg
def test_transcription_creates_pt_srt_and_state(settings: Settings, clip: str) -> None:
    state = run_transcription(settings, clip, transcriber_for(settings))
    pt = settings.output_dir / clip / "pt.srt"
    assert pt.exists()
    assert state.transcription.state == StepState.TRANSCRITO
    assert state.transcription.progress == 1.0
    assert state.probe is not None and state.probe.has_audio
    assert state.transcription.input_hash == sha256_file(settings.input_dir / "corte-01.mp4")
    assert state.transcription.srt_hash == sha256_file(pt)
    saved = load_state(settings.output_dir / clip, clip, "corte-01.mp4")
    assert saved.transcription.state == StepState.TRANSCRITO


@pytest.mark.ffmpeg
def test_second_transcription_is_skipped_and_force_rewrites(settings: Settings, clip: str) -> None:
    _transcribe(settings, clip)
    pt = settings.output_dir / clip / "pt.srt"
    os.utime(pt, ns=(1_000_000_000, 1_000_000_000))
    _transcribe(settings, clip)
    assert pt.stat().st_mtime_ns == 1_000_000_000
    _transcribe(settings, clip, force=True)
    assert pt.stat().st_mtime_ns != 1_000_000_000


@pytest.mark.ffmpeg
def test_manual_edit_is_not_overwritten_without_force(settings: Settings, clip: str) -> None:
    _transcribe(settings, clip)
    pt = settings.output_dir / clip / "pt.srt"
    edited = "1\n00:00:00,500 --> 00:00:03,000\nTexto editado à mão.\n"
    pt.write_text(edited, encoding="utf-8")
    _transcribe(settings, clip)
    assert pt.read_text(encoding="utf-8") == edited


@pytest.mark.ffmpeg
def test_save_pt_srt_rejects_invalid_text(settings: Settings, clip: str) -> None:
    _transcribe(settings, clip)
    pt = settings.output_dir / clip / "pt.srt"
    before = pt.read_text(encoding="utf-8")
    with pytest.raises(SrtParseError):
        save_pt_srt(settings, clip, "isto não é um SRT")
    assert pt.read_text(encoding="utf-8") == before


@pytest.mark.ffmpeg
def test_register_translation_ok(settings: Settings, clip: str) -> None:
    """CT-15: tradução igual ao pt.srt (texto curto) é aprovada e registrada."""
    _transcribe(settings, clip)
    folder = settings.output_dir / clip
    shutil.copy(folder / "pt.srt", folder / "en.srt")
    state, problems = register_translation(settings, folder / "en.srt")
    assert problems == []
    assert state is not None
    record = state.translations["en"]
    assert record.state == StepState.TRADUZIDO
    assert record.srt_hash == sha256_file(folder / "en.srt")
    assert record.source_hash == sha256_file(folder / "pt.srt")
    assert load_state(folder, clip, "").translations["en"].state == StepState.TRADUZIDO


@pytest.mark.ffmpeg
def test_register_translation_rejected_does_not_touch_state(settings: Settings, clip: str) -> None:
    _transcribe(settings, clip)
    folder = settings.output_dir / clip
    (folder / "en.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")
    state, problems = register_translation(settings, folder / "en.srt")
    assert state is None
    assert problems
    assert load_state(folder, clip, "").translations == {}


@pytest.mark.ffmpeg
def test_register_translation_usage_errors(settings: Settings, clip: str, tmp_path: Path) -> None:
    _transcribe(settings, clip)
    folder = settings.output_dir / clip
    shutil.copy(folder / "pt.srt", folder / "de.srt")
    with pytest.raises(UsageError, match="idioma sem perfil"):
        register_translation(settings, folder / "de.srt")
    outside = tmp_path / "en.srt"
    shutil.copy(folder / "pt.srt", outside)
    with pytest.raises(UsageError):
        register_translation(settings, outside)
    with pytest.raises(UsageError):
        register_translation(settings, folder / "pt.srt")


@pytest.mark.ffmpeg
def test_edit_pt_marks_translation_outdated_and_burn_refuses(settings: Settings, clip: str) -> None:
    """CB-14: pt.srt editado depois da tradução desatualiza o idioma e bloqueia a queima."""
    _transcribe(settings, clip)
    folder = settings.output_dir / clip
    shutil.copy(folder / "pt.srt", folder / "en.srt")
    register_translation(settings, folder / "en.srt")
    (folder / "pt.srt").write_text(
        "1\n00:00:00,500 --> 00:00:03,000\nOutro texto.\n", encoding="utf-8"
    )
    state = refresh_clip(settings, clip)
    assert state.translations["en"].state == StepState.DESATUALIZADO
    with pytest.raises(UsageError, match="ausente ou desatualizada"):
        run_burn(settings, clip, "en")


@pytest.mark.ffmpeg
def test_burn_generates_mp4_and_marks_ready(settings: Settings, clip: str) -> None:
    _transcribe(settings, clip)
    folder = settings.output_dir / clip
    shutil.copy(folder / "pt.srt", folder / "en.srt")
    register_translation(settings, folder / "en.srt")
    state = run_burn(settings, clip, "en")
    assert (folder / "en.mp4").exists()
    assert state.burns["en"].state == StepState.PRONTO
    assert state.burns["en"].progress == 1.0
    assert state.burns["en"].srt_hash == state.translations["en"].srt_hash
    stamp = state.burns["en"].updated_at
    again = run_burn(settings, clip, "en")
    assert again.burns["en"].updated_at == stamp


@pytest.mark.ffmpeg
def test_locked_clip_raises(settings: Settings, clip: str) -> None:
    with ClipLock(settings.output_dir / clip), pytest.raises(ClipLockedError):
        _transcribe(settings, clip)


def test_find_video_missing(settings: Settings) -> None:
    with pytest.raises(UsageError, match=re.escape("corte não encontrado: nada")):
        find_video(settings, "nada")


def test_fake_transcriber_selected_by_env(settings: Settings) -> None:
    segments = transcriber_for(settings).transcribe(Path("x"), 3.0, lambda _p: None)
    assert segments[0].text == "Olá, este é um teste do Translunar."
    assert (segments[0].start_s, segments[0].end_s) == (0.5, 3.0)
    assert segments[0].words
