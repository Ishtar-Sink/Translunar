"""Testes do acervo e do upload do painel (CT-01 a CT-04)."""

from __future__ import annotations

import dataclasses
import shutil
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from translunar.panel.auth import CSRF_HEADER

MakeVideo = Callable[..., Path]


def _upload(
    panel: SimpleNamespace, name: str, data: bytes = b"conteudo-de-video", csrf: bool = True
) -> Any:
    headers = {CSRF_HEADER: panel.csrf} if csrf else {}
    return panel.client.post(
        "/api/cortes/upload",
        files={"arquivo": (name, data, "video/mp4")},
        headers=headers,
    )


def _entries(panel: SimpleNamespace) -> list[str]:
    return sorted(p.name for p in panel.settings.input_dir.iterdir())


def test_list_returns_videos_with_metadata(
    panel_client: SimpleNamespace, make_video: MakeVideo
) -> None:
    """CT-01: acervo com duração, miniatura e estado; vídeo fora de 9:16 traz aviso."""
    entrada = panel_client.settings.input_dir
    shutil.copy(make_video("a.mp4"), entrada / "a.mp4")
    shutil.copy(make_video("b.mp4", width=640, height=360), entrada / "b.mp4")

    response = panel_client.client.get("/api/cortes")

    assert response.status_code == 200
    itens = {item["id"]: item for item in response.json()}
    assert set(itens) == {"a", "b"}
    for item in itens.values():
        assert item["duracao_s"] == pytest.approx(3.0, abs=0.5)
        assert item["miniatura"] == f"/api/cortes/{item['id']}/miniatura"
        assert item["pt_srt"] is None
        assert item["em_processamento"] is False
        assert item["erro"] is None
        assert item["estado"]["transcription"]["state"] == "aguardando"
        assert item["tamanho_bytes"] > 0
    assert itens["a"]["aviso"] is None
    assert "640x360" in itens["b"]["aviso"]

    thumb = panel_client.client.get(itens["a"]["miniatura"])
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/jpeg"
    assert (panel_client.settings.output_dir / "a" / "estado.json").exists()


def test_list_exposes_absolute_pt_srt(panel_client: SimpleNamespace, make_video: MakeVideo) -> None:
    entrada = panel_client.settings.input_dir
    shutil.copy(make_video("a.mp4"), entrada / "a.mp4")
    pasta = panel_client.settings.output_dir / "a"
    pasta.mkdir(parents=True)
    (pasta / "pt.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nOi\n", encoding="utf-8")

    item = panel_client.client.get("/api/cortes").json()[0]

    assert item["pt_srt"] == str((pasta / "pt.srt").resolve())
    assert Path(item["pt_srt"]).is_absolute()


def test_list_reports_probe_error(panel_client: SimpleNamespace) -> None:
    (panel_client.settings.input_dir / "quebrado.mp4").write_bytes(b"nao e video")

    item = panel_client.client.get("/api/cortes").json()[0]

    assert item["id"] == "quebrado"
    assert item["erro"]
    assert item["duracao_s"] is None
    assert item["miniatura"] is None


def test_list_ignores_non_video_files(panel_client: SimpleNamespace) -> None:
    (panel_client.settings.input_dir / "notas.txt").write_text("x", encoding="utf-8")
    assert panel_client.client.get("/api/cortes").json() == []


def test_thumbnail_missing_and_invalid_id(panel_client: SimpleNamespace) -> None:
    assert panel_client.client.get("/api/cortes/nao-existe/miniatura").status_code == 404
    assert panel_client.client.get("/api/cortes/..%2Fx/miniatura").status_code in (400, 404)
    assert panel_client.client.get("/api/cortes/.oculto/miniatura").status_code == 400


def test_list_requires_session(panel_client: SimpleNamespace) -> None:
    panel_client.client.post("/api/logout")
    assert panel_client.client.get("/api/cortes").status_code == 401


def test_upload_without_csrf_is_403(panel_client: SimpleNamespace) -> None:
    assert _upload(panel_client, "corte.mp4", csrf=False).status_code == 403
    assert _entries(panel_client) == []


def test_upload_duplicate_names_get_suffix(panel_client: SimpleNamespace) -> None:
    """CT-02: o mesmo nome duas vezes vira `corte.mp4` e `corte-1.mp4`, sem `.part`."""
    first = _upload(panel_client, "corte.mp4", b"primeiro")
    second = _upload(panel_client, "corte.mp4", b"segundo")

    assert first.status_code == 201
    assert first.json() == {"id": "corte", "video": "corte.mp4"}
    assert second.status_code == 201
    assert second.json() == {"id": "corte-1", "video": "corte-1.mp4"}
    assert _entries(panel_client) == ["corte-1.mp4", "corte.mp4"]
    entrada = panel_client.settings.input_dir
    assert (entrada / "corte.mp4").read_bytes() == b"primeiro"
    assert (entrada / "corte-1.mp4").read_bytes() == b"segundo"


def test_upload_same_stem_other_extension_gets_suffix(panel_client: SimpleNamespace) -> None:
    assert _upload(panel_client, "corte.mp4").status_code == 201
    response = _upload(panel_client, "corte.mov")
    assert response.json() == {"id": "corte-1", "video": "corte-1.mov"}


def test_upload_normalizes_name(panel_client: SimpleNamespace) -> None:
    response = _upload(panel_client, "Côrte final.MP4")
    assert response.status_code == 201
    assert response.json() == {"id": "Corte-final", "video": "Corte-final.mp4"}
    assert _entries(panel_client) == ["Corte-final.mp4"]


def test_upload_rejects_invalid_extension(panel_client: SimpleNamespace) -> None:
    """CT-03: formato inválido é 400 e nada é gravado."""
    response = _upload(panel_client, "notas.txt")
    assert response.status_code == 400
    assert _entries(panel_client) == []


def test_upload_rejects_over_limit(panel_client: SimpleNamespace) -> None:
    """CT-03: acima do limite é 413 e nada é gravado."""
    app = panel_client.client.app
    settings = app.state.settings  # type: ignore[attr-defined]
    app.state.settings = dataclasses.replace(  # type: ignore[attr-defined]
        settings, panel=dataclasses.replace(settings.panel, upload_limit_mb=0)
    )
    response = _upload(panel_client, "corte.mp4", b"x" * (100 * 1024))
    assert response.status_code == 413
    assert _entries(panel_client) == []


def test_upload_rejects_without_disk_space(
    panel_client: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CT-04: sem espaço livre é 507 e nada é gravado."""
    monkeypatch.setattr(
        "translunar.panel.routes_clips.shutil.disk_usage",
        lambda _path: SimpleNamespace(total=0, used=0, free=0),
    )
    response = _upload(panel_client, "corte.mp4")
    assert response.status_code == 507
    assert _entries(panel_client) == []


def test_upload_without_file_field_is_400(panel_client: SimpleNamespace) -> None:
    response = panel_client.client.post(
        "/api/cortes/upload",
        files={"outro": ("corte.mp4", b"x", "video/mp4")},
        headers={CSRF_HEADER: panel_client.csrf},
    )
    assert response.status_code == 400
    assert _entries(panel_client) == []


def test_upload_without_content_length_is_411(panel_client: SimpleNamespace) -> None:
    def corpo() -> Any:
        yield b"--x\r\n"

    response = panel_client.client.post(
        "/api/cortes/upload",
        content=corpo(),
        headers={
            CSRF_HEADER: panel_client.csrf,
            "Content-Type": "multipart/form-data; boundary=x",
        },
    )
    assert response.status_code == 411
    assert _entries(panel_client) == []
