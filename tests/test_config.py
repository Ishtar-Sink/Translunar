"""Testes do carregador de configuração (TASK-02, RF-34, RN-04 a RN-08)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
import yaml

from translunar.core.config import (
    CONFIG_DIR_ENV,
    PROJECT_ROOT,
    load_env_file,
    load_glossary,
    load_language_profiles,
    load_settings,
)
from translunar.core.errors import ConfigError


def _copy_config(tmp_path: Path) -> Path:
    destino = tmp_path / "config"
    shutil.copytree(PROJECT_ROOT / "config", destino)
    return destino


def test_load_default_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(CONFIG_DIR_ENV, raising=False)
    settings = load_settings()
    assert settings.limits.max_chars_per_line == 32
    assert settings.limits.max_cps == 17.0
    assert settings.burn.jobs == 2
    assert settings.panel.port == 8770
    assert settings.input_dir.name == "entrada"


def test_local_override_wins(tmp_path: Path) -> None:
    copia = _copy_config(tmp_path)
    (copia / "config.local.yaml").write_text(
        yaml.safe_dump({"queima": {"ffmpeg": "/opt/x/ffmpeg"}}), encoding="utf-8"
    )
    settings = load_settings(copia)
    assert settings.burn.ffmpeg == "/opt/x/ffmpeg"
    assert settings.burn.preset == "veryfast"


def test_missing_key_raises_config_error(tmp_path: Path) -> None:
    copia = _copy_config(tmp_path)
    data = yaml.safe_load((copia / "config.yaml").read_text(encoding="utf-8"))
    del data["legenda"]
    (copia / "config.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ConfigError, match="legenda"):
        load_settings(copia)


def test_env_var_selects_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    copia = _copy_config(tmp_path)
    monkeypatch.setenv(CONFIG_DIR_ENV, str(copia))
    assert load_settings().config_dir == copia


def test_language_profiles_loaded() -> None:
    settings = load_settings(PROJECT_ROOT / "config")
    profiles = load_language_profiles(settings)
    assert set(profiles) == {"en", "es", "fr"}
    assert "não usar vosotros" in profiles["es"].rules


def test_new_language_needs_only_a_file(tmp_path: Path) -> None:
    copia = _copy_config(tmp_path)
    (copia / "idiomas" / "it.yaml").write_text(
        yaml.safe_dump(
            {
                "codigo": "it",
                "nome": "Italiano",
                "variante": "italiano neutro",
                "publico": "falantes de italiano",
                "registro": "segue o do original, natural e conversacional",
                "regras": ["evitar gírias regionais"],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    profiles = load_language_profiles(load_settings(copia))
    assert "it" in profiles


def test_profile_code_must_match_file_name(tmp_path: Path) -> None:
    copia = _copy_config(tmp_path)
    (copia / "idiomas" / "de.yaml").write_text(
        yaml.safe_dump(
            {
                "codigo": "xx",
                "nome": "Alemão",
                "variante": "alemão",
                "publico": "falantes de alemão",
                "registro": "conversacional",
                "regras": [],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_language_profiles(load_settings(copia))


def test_glossary_terms() -> None:
    termos = {t.term: t for t in load_glossary(load_settings(PROJECT_ROOT / "config"))}
    assert "Ishtar Sink" in termos
    assert termos["Ishtar Sink"].translations == {}


def test_env_file_does_not_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    arquivo = tmp_path / ".env"
    arquivo.write_text("TRANSLUNAR_X=arquivo\n", encoding="utf-8")
    monkeypatch.setenv("TRANSLUNAR_X", "ambiente")
    load_env_file(arquivo)
    assert os.environ["TRANSLUNAR_X"] == "ambiente"
