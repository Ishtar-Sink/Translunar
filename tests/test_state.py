"""Testes do estado, hashes e desatualização (CT-17)."""

from __future__ import annotations

from pathlib import Path

import pytest

from translunar.core.errors import UsageError
from translunar.core.models import ProbeResult, StepState
from translunar.core.state import (
    BurnRecord,
    ClipState,
    TranslationRecord,
    clip_dir,
    clip_id_for_video,
    is_current,
    load_state,
    mark_interrupted,
    now_iso,
    refresh_outdated,
    save_state,
    sha256_file,
    validate_clip_id,
)


def _state_with_en() -> ClipState:
    state = ClipState("corte-01", "corte-01.mp4")
    state.translations["en"] = TranslationRecord(
        state=StepState.TRADUZIDO, srt_hash="e1", source_hash="h1"
    )
    state.burns["en"] = BurnRecord(state=StepState.PRONTO, srt_hash="e1")
    return state


def test_roundtrip_to_from_dict() -> None:
    state = _state_with_en()
    state.probe = ProbeResult(width=1080, height=1920, duration_s=12.5, has_audio=True)
    data = state.to_dict()
    assert data["translations"]["en"]["state"] == "traduzido"
    assert data["probe"] == {"width": 1080, "height": 1920, "duration_s": 12.5, "has_audio": True}
    assert ClipState.from_dict(data) == state


def test_probe_none_roundtrip() -> None:
    state = ClipState("a", "a.mp4")
    assert state.to_dict()["probe"] is None
    assert ClipState.from_dict(state.to_dict()) == state


def test_save_and_load_state(tmp_path: Path) -> None:
    directory = tmp_path / "saida" / "corte-01"
    state = _state_with_en()
    save_state(directory, state)
    assert (directory / "estado.json").is_file()
    assert not (directory / ".estado.json.tmp").exists()
    assert load_state(directory, "corte-01", "corte-01.mp4") == state


def test_load_state_missing_returns_new(tmp_path: Path) -> None:
    state = load_state(tmp_path, "x", "x.mp4")
    assert state.clip_id == "x"
    assert state.transcription.state == StepState.AGUARDANDO


def test_sha256_file(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("um", encoding="utf-8")
    first = sha256_file(f)
    assert first.startswith("sha256:")
    f.write_text("dois", encoding="utf-8")
    assert sha256_file(f) != first


def test_now_iso_format() -> None:
    value = now_iso()
    assert value.endswith("Z")
    assert "." not in value


def test_validate_clip_id() -> None:
    assert validate_clip_id("corte-01") == "corte-01"
    for bad in ["../config", "a/b", ".oculto", "", "a..b"]:
        with pytest.raises(UsageError):
            validate_clip_id(bad)


def test_clip_id_for_video() -> None:
    assert clip_id_for_video("corte-01.mp4") == "corte-01"
    with pytest.raises(UsageError):
        clip_id_for_video(".mp4")


def test_clip_dir(tmp_path: Path) -> None:
    assert clip_dir(tmp_path, "corte-01") == tmp_path / "corte-01"
    with pytest.raises(UsageError):
        clip_dir(tmp_path, "../fora")


def test_clip_dir_rejects_symlink_escape(tmp_path: Path) -> None:
    out = tmp_path / "saida"
    out.mkdir()
    (out / "link").symlink_to(tmp_path)
    with pytest.raises(UsageError):
        clip_dir(out, "link")


def test_is_current() -> None:
    done = {StepState.PRONTO}
    assert is_current("h", "h", StepState.PRONTO, done, False) is True
    assert is_current("h", "x", StepState.PRONTO, done, False) is False
    assert is_current("h", "h", StepState.PRONTO, done, True) is False
    assert is_current("h", "h", StepState.ERRO, done, False) is False
    assert is_current(None, None, StepState.PRONTO, done, False) is False


def test_refresh_outdated_pt_changed() -> None:
    state = _state_with_en()
    changed = refresh_outdated(state, "h2", {"en": "e1"})
    assert changed == ["translations.en", "burns.en"]
    assert state.translations["en"].state == StepState.DESATUALIZADO
    assert state.burns["en"].state == StepState.DESATUALIZADO


def test_refresh_outdated_translation_edited() -> None:
    state = _state_with_en()
    changed = refresh_outdated(state, "h1", {"en": "e2"})
    assert changed == ["translations.en", "burns.en"]
    assert state.burns["en"].state == StepState.DESATUALIZADO


def test_refresh_outdated_nothing_changed() -> None:
    state = _state_with_en()
    assert refresh_outdated(state, "h1", {"en": "e1"}) == []
    assert state.burns["en"].state == StepState.PRONTO


def test_refresh_outdated_burn_without_translation() -> None:
    state = ClipState("a", "a.mp4")
    state.burns["fr"] = BurnRecord(state=StepState.PRONTO, srt_hash="x")
    assert refresh_outdated(state, "h1", {}) == ["burns.fr"]


def test_refresh_outdated_ignores_running_and_error() -> None:
    state = _state_with_en()
    state.burns["en"].state = StepState.QUEIMANDO
    state.translations["pt"] = TranslationRecord(state=StepState.ERRO, source_hash="h1")
    assert refresh_outdated(state, "h2", {}) == ["translations.en"]
    assert state.burns["en"].state == StepState.QUEIMANDO
    assert state.translations["pt"].state == StepState.ERRO


def test_mark_interrupted() -> None:
    state = ClipState("a", "a.mp4")
    assert mark_interrupted(state) is False
    state.transcription.state = StepState.TRANSCREVENDO
    state.burns["en"] = BurnRecord(state=StepState.QUEIMANDO)
    state.burns["es"] = BurnRecord(state=StepState.PRONTO)
    assert mark_interrupted(state) is True
    assert state.transcription.state == StepState.INTERROMPIDO
    assert state.burns["en"].state == StepState.INTERROMPIDO
    assert state.burns["es"].state == StepState.PRONTO
