"""Fixtures compartilhadas pelos testes."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from translunar.core.config import PROJECT_ROOT, load_settings
from translunar.panel.app import create_app

FFMPEG = shutil.which("ffmpeg")


@pytest.fixture
def make_video(tmp_path: Path) -> Callable[..., Path]:
    """Gera um vídeo sintético (fundo preto, tom de 440 Hz) e devolve o caminho."""

    def _make(
        name: str = "corte.mp4",
        width: int = 360,
        height: int = 640,
        duration: float = 3.0,
        audio: bool = True,
    ) -> Path:
        if FFMPEG is None:
            pytest.skip("ffmpeg não encontrado no PATH")
        out = tmp_path / name
        cmd = [
            FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={width}x{height}:d={duration}",
        ]
        if audio:
            cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
            cmd += ["-c:a", "aac", "-shortest"]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)]
        subprocess.run(cmd, check=True)
        return out

    return _make


@pytest.fixture
def panel_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    """Painel com dados em `tmp_path`, `lifespan` ativo e sessão já logada.

    Devolve um objeto com `client`, `settings` e `csrf` (valor do cabeçalho `X-CSRF-Token`).
    """
    config_dir = tmp_path / "config"
    shutil.copytree(PROJECT_ROOT / "config", config_dir)
    data_dir = tmp_path / "dados"
    (config_dir / "config.local.yaml").write_text(f"pasta_dados: {data_dir}\n", encoding="utf-8")
    monkeypatch.setenv("TRANSLUNAR_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("TRANSLUNAR_PAINEL_SENHA", "teste")
    monkeypatch.setenv("TRANSLUNAR_PAINEL_SEGREDO", "segredo-de-teste")
    settings = load_settings()
    settings.input_dir.mkdir(parents=True)
    settings.output_dir.mkdir(parents=True)
    with TestClient(create_app()) as client:
        response = client.post("/api/login", json={"senha": "teste"})
        assert response.status_code == 200
        yield SimpleNamespace(client=client, settings=settings, csrf=response.json()["csrf"])
