"""Carrega a configuração do Translunar: config.yaml, perfis de idioma, glossário e .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from translunar.core.errors import ConfigError
from translunar.core.models import SubtitleLimits, SubtitleStyle

# Raiz do projeto: src/translunar/core/config.py -> parents[3].
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR_ENV = "TRANSLUNAR_CONFIG_DIR"


@dataclass(frozen=True)
class TranscriptionSettings:
    model: str


@dataclass(frozen=True)
class BurnSettings:
    ffmpeg: str
    ffprobe: str
    preset: str
    crf: int
    jobs: int


@dataclass(frozen=True)
class PanelSettings:
    host: str
    port: int
    upload_limit_mb: int
    login_attempts: int
    login_block_min: int


@dataclass(frozen=True)
class Settings:
    config_dir: Path
    data_dir: Path
    transcription: TranscriptionSettings
    limits: SubtitleLimits
    style: SubtitleStyle
    burn: BurnSettings
    panel: PanelSettings

    @property
    def input_dir(self) -> Path:
        return self.data_dir / "entrada"

    @property
    def output_dir(self) -> Path:
        return self.data_dir / "saida"

    @property
    def languages_dir(self) -> Path:
        return self.config_dir / "idiomas"

    @property
    def glossary_path(self) -> Path:
        return self.config_dir / "glossario.yaml"

    @property
    def font_path(self) -> Path:
        return PROJECT_ROOT / self.style.font_file

    @property
    def fonts_dir(self) -> Path:
        return self.font_path.parent


@dataclass(frozen=True)
class LanguageProfile:
    code: str
    name: str
    variant: str
    audience: str
    register: str
    rules: tuple[str, ...]


@dataclass(frozen=True)
class GlossaryTerm:
    term: str
    translations: dict[str, str]


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"arquivo de configuração não encontrado: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML inválido em {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path} precisa ser um mapa YAML")
    return data


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Sobrepõe `override` em `base`, recursivamente nos mapas."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _get(data: dict[str, Any], dotted: str) -> Any:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise ConfigError(f"chave obrigatória ausente no config.yaml: {dotted}")
        node = node[part]
    return node


def resolve_config_dir(config_dir: Path | None = None) -> Path:
    if config_dir is not None:
        return config_dir
    env = os.environ.get(CONFIG_DIR_ENV)
    return Path(env) if env else PROJECT_ROOT / "config"


def load_settings(config_dir: Path | None = None) -> Settings:
    """Lê config.yaml e, se existir, sobrepõe config.local.yaml."""
    directory = resolve_config_dir(config_dir)
    data = _read_yaml(directory / "config.yaml")
    local = directory / "config.local.yaml"
    if local.exists():
        data = _merge(data, _read_yaml(local))
    try:
        return Settings(
            config_dir=directory,
            data_dir=Path(str(_get(data, "pasta_dados"))).expanduser(),
            transcription=TranscriptionSettings(model=str(_get(data, "transcricao.modelo"))),
            limits=SubtitleLimits(
                max_lines=int(_get(data, "legenda.max_linhas")),
                max_chars_per_line=int(_get(data, "legenda.max_caracteres_linha")),
                max_cps=float(_get(data, "legenda.max_cps")),
                min_duration_s=float(_get(data, "legenda.duracao_min_s")),
                max_duration_s=float(_get(data, "legenda.duracao_max_s")),
            ),
            style=SubtitleStyle(
                font_file=str(_get(data, "estilo.fonte")),
                bold=bool(_get(data, "estilo.negrito")),
                text_color=str(_get(data, "estilo.cor_texto")),
                outline_color=str(_get(data, "estilo.cor_contorno")),
                size_pct_width=float(_get(data, "estilo.tamanho_pct_largura")),
                margin_bottom_pct=float(_get(data, "estilo.margem_inferior_pct")),
                margin_side_pct=float(_get(data, "estilo.margem_lateral_pct")),
            ),
            burn=BurnSettings(
                ffmpeg=str(_get(data, "queima.ffmpeg")),
                ffprobe=str(_get(data, "queima.ffprobe")),
                preset=str(_get(data, "queima.preset")),
                crf=int(_get(data, "queima.crf")),
                jobs=int(_get(data, "queima.jobs")),
            ),
            panel=PanelSettings(
                host=str(_get(data, "painel.host")),
                port=int(_get(data, "painel.porta")),
                upload_limit_mb=int(_get(data, "painel.limite_upload_mb")),
                login_attempts=int(_get(data, "painel.tentativas_login")),
                login_block_min=int(_get(data, "painel.bloqueio_login_min")),
            ),
        )
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"valor inválido no config.yaml: {exc}") from exc


def load_language_profiles(settings: Settings) -> dict[str, LanguageProfile]:
    """Lê config/idiomas/*.yaml. O `codigo` precisa ser igual ao nome do arquivo (RF-34)."""
    profiles: dict[str, LanguageProfile] = {}
    for path in sorted(settings.languages_dir.glob("*.yaml")):
        data = _read_yaml(path)
        code = str(_get(data, "codigo"))
        if code != path.stem:
            raise ConfigError(f"{path.name}: codigo '{code}' difere do nome do arquivo")
        profiles[code] = LanguageProfile(
            code=code,
            name=str(_get(data, "nome")),
            variant=str(_get(data, "variante")),
            audience=str(_get(data, "publico")),
            register=str(_get(data, "registro")),
            rules=tuple(str(rule) for rule in data.get("regras") or ()),
        )
    return profiles


def load_glossary(settings: Settings) -> tuple[GlossaryTerm, ...]:
    data = _read_yaml(settings.glossary_path)
    terms = []
    for item in data.get("termos") or ():
        translations = {str(k): str(v) for k, v in (item.get("traducoes") or {}).items()}
        terms.append(GlossaryTerm(term=str(item["termo"]), translations=translations))
    return tuple(terms)


def load_env_file(path: Path | None = None) -> None:
    """Carrega KEY=VALUE de um .env sem sobrescrever variáveis já definidas."""
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
