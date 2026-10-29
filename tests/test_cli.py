"""Testes do contrato da CLI `legendar` (TASK-13: RF-35, RF-36, CT-15, CT-18, CT-28, CT-29)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from translunar.cli import main
from translunar.core.config import CONFIG_DIR_ENV, PROJECT_ROOT, Settings, load_settings
from translunar.core.lock import ClipLock
from translunar.core.pipeline import TRANSCRIBER_ENV

pytestmark = pytest.mark.ffmpeg


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = tmp_path / "config"
    shutil.copytree(PROJECT_ROOT / "config", config)
    (config / "config.local.yaml").write_text(
        yaml.safe_dump({"pasta_dados": str(tmp_path / "dados")}), encoding="utf-8"
    )
    monkeypatch.setenv(CONFIG_DIR_ENV, str(config))
    monkeypatch.setenv(TRANSCRIBER_ENV, "falso")
    return config


@pytest.fixture
def settings(config_dir: Path) -> Settings:
    loaded = load_settings(config_dir)
    loaded.input_dir.mkdir(parents=True)
    return loaded


@pytest.fixture
def clip(settings: Settings, make_video: Callable[..., Path]) -> str:
    shutil.move(make_video("corte-01.mp4"), settings.input_dir / "corte-01.mp4")
    return "corte-01"


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, Any, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    payload = json.loads(captured.out) if "--json" in argv else captured.out
    return code, payload, captured.err


def _transcribed(settings: Settings, capsys: pytest.CaptureFixture[str], clip: str) -> Path:
    code, _, _ = _run(capsys, "transcrever", clip, "--json")
    assert code == 0
    return settings.output_dir / clip


def test_transcrever_json_then_skip_then_force(
    settings: Settings, clip: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, data, _ = _run(capsys, "transcrever", "--json")
    assert code == 0
    assert data["resultados"][0]["clip_id"] == "corte-01"
    assert data["resultados"][0]["estado"] == "transcrito"
    code, data, _ = _run(capsys, "transcrever", "--json")
    assert code == 0
    assert data["resultados"][0]["estado"] == "pulado"
    code, data, _ = _run(capsys, "transcrever", "corte-01.mp4", "--forcar", "--json")
    assert code == 0
    assert data["resultados"][0]["estado"] == "transcrito"


def test_transcrever_text_output(
    settings: Settings, clip: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = _run(capsys, "transcrever", clip)
    assert code == 0
    assert out.strip() == "corte-01: transcrito"


def test_transcrever_unknown_video_exits_2(
    settings: Settings, clip: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, data, _ = _run(capsys, "transcrever", "nada.mp4", "corte-01", "--json")
    assert code == 2
    assert data["resultados"][0]["erro"]
    assert data["resultados"][1]["estado"] == "transcrito"


def test_validar_ok_registers_translation(
    settings: Settings, clip: str, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = _transcribed(settings, capsys, clip)
    shutil.copy(folder / "pt.srt", folder / "en.srt")
    code, data, _ = _run(capsys, "validar", str(folder / "en.srt"), "--json")
    assert code == 0
    assert data == {"ok": True, "file": str(folder / "en.srt"), "language": "en", "problems": []}
    state = json.loads((folder / "estado.json").read_text(encoding="utf-8"))
    assert state["translations"]["en"]["state"] == "traduzido"


def test_validar_refused_exits_3(
    settings: Settings, clip: str, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = _transcribed(settings, capsys, clip)
    (folder / "en.srt").write_text("2\n00:00:00,500 --> 00:00:03,000\nHello\n", encoding="utf-8")
    code, data, _ = _run(capsys, "validar", str(folder / "en.srt"), "--json")
    assert code == 3
    assert data["ok"] is False
    kinds = {p["kind"] for p in data["problems"]}
    assert "missing_id" in kinds
    assert data["problems"][0]["kind"] == "missing_id"


def test_validar_refused_text_lines(
    settings: Settings, clip: str, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = _transcribed(settings, capsys, clip)
    (folder / "en.srt").write_text("2\n00:00:00,500 --> 00:00:03,000\nHello\n", encoding="utf-8")
    code, out, _ = _run(capsys, "validar", str(folder / "en.srt"))
    assert code == 3
    assert "id 1 missing_id:" in out


def test_validar_new_language_needs_only_profile(
    settings: Settings, config_dir: Path, clip: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """CT-28: idioma novo só com o perfil em config/idiomas."""
    folder = _transcribed(settings, capsys, clip)
    (config_dir / "idiomas" / "it.yaml").write_text(
        yaml.safe_dump(
            {
                "codigo": "it",
                "nome": "Italiano",
                "variante": "italiano padrão",
                "publico": "falantes de italiano",
                "registro": "natural",
                "regras": [],
            }
        ),
        encoding="utf-8",
    )
    shutil.copy(folder / "pt.srt", folder / "it.srt")
    code, data, _ = _run(capsys, "validar", str(folder / "it.srt"), "--json")
    assert code == 0
    assert data["language"] == "it"


def test_validar_language_without_profile_exits_2(
    settings: Settings, clip: str, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = _transcribed(settings, capsys, clip)
    shutil.copy(folder / "pt.srt", folder / "de.srt")
    code = main(["validar", str(folder / "de.srt"), "--json"])
    assert code == 2
    assert "idioma sem perfil" in capsys.readouterr().err


def test_queimar_unknown_clip_exits_2(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["queimar", "corte-inexistente", "en"])
    assert code == 2
    assert "corte não encontrado" in capsys.readouterr().out


def test_queimar_locked_exits_4(
    settings: Settings, clip: str, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = _transcribed(settings, capsys, clip)
    with ClipLock(folder):
        code = main(["queimar", clip, "en"])
    assert code == 4


def test_queimar_missing_ffmpeg_exits_5(
    settings: Settings, config_dir: Path, clip: str, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = _transcribed(settings, capsys, clip)
    shutil.copy(folder / "pt.srt", folder / "en.srt")
    assert _run(capsys, "validar", str(folder / "en.srt"), "--json")[0] == 0
    (config_dir / "config.local.yaml").write_text(
        yaml.safe_dump(
            {"pasta_dados": str(settings.data_dir), "queima": {"ffmpeg": "ffmpeg-inexistente"}}
        ),
        encoding="utf-8",
    )
    code = main(["queimar", clip, "en", "--json"])
    assert code == 5


def test_queimar_json_ok_then_skipped(
    settings: Settings, clip: str, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = _transcribed(settings, capsys, clip)
    shutil.copy(folder / "pt.srt", folder / "en.srt")
    assert _run(capsys, "validar", str(folder / "en.srt"), "--json")[0] == 0
    code, data, _ = _run(capsys, "queimar", clip, "en", "--json")
    assert code == 0
    assert data["resultados"][0]["estado"] == "pronto"
    assert (folder / "en.mp4").exists()
    code, data, _ = _run(capsys, "queimar", clip, "en", "--json")
    assert code == 0
    assert data["resultados"][0]["estado"] == "pulado"


def test_status_json(settings: Settings, clip: str, capsys: pytest.CaptureFixture[str]) -> None:
    _transcribed(settings, capsys, clip)
    code, data, _ = _run(capsys, "status", "--json")
    assert code == 0
    item = data["cortes"][0]
    assert item["clip_id"] == "corte-01"
    assert Path(item["pt_srt"]).is_absolute()
    assert item["pt_srt"].endswith("corte-01/pt.srt")
    assert item["estado"]["transcription"]["state"] == "transcrito"
    code, data, _ = _run(capsys, "status", "corte-01", "--json")
    assert code == 0 and len(data["cortes"]) == 1
    assert main(["status", "outro"]) == 2


def test_status_empty_is_valid_json(settings: Settings, capsys: pytest.CaptureFixture[str]) -> None:
    code, data, _ = _run(capsys, "status", "--json")
    assert code == 0
    assert data == {"cortes": []}
