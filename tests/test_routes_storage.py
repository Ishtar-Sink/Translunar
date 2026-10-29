"""Testes de espaço em disco e exclusão de cortes (CT-21 a CT-23)."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from translunar.core.lock import ClipLock
from translunar.panel.auth import CSRF_HEADER

MakeVideo = Callable[..., Path]


def _add_clip(panel: SimpleNamespace, name: str, saida_bytes: int = 4096) -> Path:
    """Cria um corte falso (vídeo + contexto + saídas) dentro de `tmp_path`."""
    video = panel.settings.input_dir / f"{name}.mp4"
    video.write_bytes(b"v" * 2048)
    (panel.settings.input_dir / f"{name}.mp4.contexto.md").write_text("contexto", encoding="utf-8")
    saida = panel.settings.output_dir / name
    (saida / "videos").mkdir(parents=True)
    (saida / "pt.srt").write_bytes(b"s" * saida_bytes)
    (saida / "videos" / "pt.mp4").write_bytes(b"m" * saida_bytes)
    return video


def _delete(
    panel: SimpleNamespace, clip_id: str, alvo: str | None = None, csrf: bool = True
) -> Any:
    headers = {CSRF_HEADER: panel.csrf} if csrf else {}
    params = {"alvo": alvo} if alvo else {}
    return panel.client.delete(f"/api/cortes/{clip_id}", params=params, headers=headers)


def test_disk_usage_and_clip_total(panel_client: SimpleNamespace, make_video: MakeVideo) -> None:
    """CT-21: os quatro campos do disco e o tamanho total de cada corte."""
    entrada = panel_client.settings.input_dir
    video = entrada / "a.mp4"
    shutil.copy(make_video("a.mp4"), video)
    (entrada / "a.mp4.contexto.md").write_text("contexto", encoding="utf-8")
    saida = panel_client.settings.output_dir / "a"
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "pt.srt").write_bytes(b"x" * 1000)

    disco = panel_client.client.get("/api/disco")

    assert disco.status_code == 200
    corpo = disco.json()
    assert set(corpo) == {"total_bytes", "usado_bytes", "livre_bytes", "dados_bytes"}
    assert corpo["dados_bytes"] >= video.stat().st_size
    assert corpo["total_bytes"] > 0

    item = panel_client.client.get("/api/cortes").json()[0]
    assert item["tamanho_total_bytes"] >= video.stat().st_size + len("contexto") + 1000
    assert item["tamanho_total_bytes"] > item["tamanho_bytes"]


def test_disk_requires_session(panel_client: SimpleNamespace) -> None:
    panel_client.client.post("/api/logout", headers={CSRF_HEADER: panel_client.csrf})
    assert panel_client.client.get("/api/disco").status_code == 401


def test_delete_outputs_of_two_clips_keeps_videos(panel_client: SimpleNamespace) -> None:
    """CT-22: `alvo=saidas` apaga as pastas de saída e mantém os vídeos."""
    for nome in ("a", "b"):
        _add_clip(panel_client, nome)

    for nome in ("a", "b"):
        resposta = _delete(panel_client, nome, "saidas")
        assert resposta.status_code == 200
        assert resposta.json()["liberado_bytes"] >= 8192

    for nome in ("a", "b"):
        assert not (panel_client.settings.output_dir / nome).exists()
        assert (panel_client.settings.input_dir / f"{nome}.mp4").is_file()
        assert (panel_client.settings.input_dir / f"{nome}.mp4.contexto.md").is_file()


def test_delete_original_keeps_outputs(panel_client: SimpleNamespace) -> None:
    _add_clip(panel_client, "a")

    resposta = _delete(panel_client, "a", "original")

    assert resposta.status_code == 200
    assert resposta.json()["liberado_bytes"] == 2048 + len("contexto")
    assert not (panel_client.settings.input_dir / "a.mp4").exists()
    assert not (panel_client.settings.input_dir / "a.mp4.contexto.md").exists()
    assert (panel_client.settings.output_dir / "a" / "pt.srt").is_file()


def test_delete_all_removes_video_context_and_outputs(panel_client: SimpleNamespace) -> None:
    _add_clip(panel_client, "a")
    _add_clip(panel_client, "b")

    resposta = _delete(panel_client, "a", "tudo")

    assert resposta.status_code == 200
    assert resposta.json()["liberado_bytes"] == 2048 + len("contexto") + 8192
    assert list(panel_client.settings.input_dir.glob("a.*")) == []
    assert not (panel_client.settings.output_dir / "a").exists()
    assert (panel_client.settings.input_dir / "b.mp4").is_file()
    assert (panel_client.settings.output_dir / "b" / "pt.srt").is_file()
    assert panel_client.client.get("/api/cortes").json() is not None


def test_delete_default_target_is_all(panel_client: SimpleNamespace) -> None:
    _add_clip(panel_client, "a")
    assert _delete(panel_client, "a").status_code == 200
    assert not (panel_client.settings.input_dir / "a.mp4").exists()


@pytest.mark.parametrize(
    "clip_id", ["..%2Fconfig", "..%2F..%2Fconfig", "%2e%2e", "a%2Fb", "%2Fetc", "a%5C..%5Cb", ".."]
)
def test_delete_rejects_path_traversal(panel_client: SimpleNamespace, clip_id: str) -> None:
    """CT-22 (traversal): nunca 200, e nada fora de `entrada/` e `saida/` é tocado."""
    config = panel_client.settings.data_dir.parent / "config"
    antes = sorted(p.name for p in config.rglob("*"))
    sentinela = panel_client.settings.data_dir / "fora.txt"
    sentinela.write_text("fica", encoding="utf-8")
    _add_clip(panel_client, "a")

    resposta = panel_client.client.delete(
        f"/api/cortes/{clip_id}?alvo=tudo", headers={CSRF_HEADER: panel_client.csrf}
    )

    assert resposta.status_code in (400, 404)
    assert sorted(p.name for p in config.rglob("*")) == antes
    assert sentinela.read_text(encoding="utf-8") == "fica"
    assert (panel_client.settings.input_dir / "a.mp4").is_file()
    assert (panel_client.settings.output_dir / "a" / "pt.srt").is_file()


def test_delete_refuses_symlink_escaping_data_dirs(
    panel_client: SimpleNamespace, tmp_path: Path
) -> None:
    """Defesa em profundidade (RN-11): um link que sai de `entrada/` não é seguido."""
    fora = tmp_path / "fora"
    fora.mkdir()
    alvo = fora / "real.mp4"
    alvo.write_bytes(b"x" * 100)
    (panel_client.settings.input_dir / "link.mp4").symlink_to(alvo)

    resposta = _delete(panel_client, "link", "original")

    assert resposta.status_code == 400
    assert alvo.is_file()
    assert (panel_client.settings.input_dir / "link.mp4").is_symlink()


def test_delete_busy_clip_returns_409(panel_client: SimpleNamespace) -> None:
    """CT-23: com o lock do corte seguro, nada é apagado."""
    _add_clip(panel_client, "a")
    directory = panel_client.settings.output_dir / "a"

    with ClipLock(directory):
        for alvo in ("saidas", "original", "tudo"):
            resposta = _delete(panel_client, "a", alvo)
            assert resposta.status_code == 409
            assert resposta.json() == {"detail": "corte em processamento"}

    assert (panel_client.settings.input_dir / "a.mp4").is_file()
    assert (directory / "pt.srt").is_file()


def test_delete_clip_busy_in_job_queue_returns_409(
    panel_client: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add_clip(panel_client, "a")
    jobs = panel_client.client.app.state.jobs
    monkeypatch.setattr(jobs, "is_busy", lambda clip_id: clip_id == "a")

    assert _delete(panel_client, "a", "tudo").status_code == 409
    assert (panel_client.settings.input_dir / "a.mp4").is_file()


def test_delete_invalid_target_returns_400(panel_client: SimpleNamespace) -> None:
    _add_clip(panel_client, "a")

    assert _delete(panel_client, "a", "lixo").status_code == 400
    assert (panel_client.settings.input_dir / "a.mp4").is_file()


def test_delete_unknown_clip_returns_404(panel_client: SimpleNamespace) -> None:
    assert _delete(panel_client, "nao-existe", "tudo").status_code == 404


def test_delete_without_csrf_returns_403(panel_client: SimpleNamespace) -> None:
    _add_clip(panel_client, "a")

    assert _delete(panel_client, "a", "tudo", csrf=False).status_code == 403
    assert (panel_client.settings.input_dir / "a.mp4").is_file()
