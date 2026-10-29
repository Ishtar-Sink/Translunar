"""Testes das rotas de transcrição e revisão do painel (CT-08 a CT-11)."""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from translunar.panel.auth import CSRF_HEADER

MakeVideo = Callable[..., Path]

SRT_VALIDO = "1\n00:00:00,500 --> 00:00:02,000\nTexto revisado.\n"


@pytest.fixture(autouse=True)
def _fake_transcriber(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLUNAR_TRANSCRITOR", "falso")


def _headers(panel: SimpleNamespace) -> dict[str, str]:
    return {CSRF_HEADER: panel.csrf}


def _add_video(panel: SimpleNamespace, make_video: MakeVideo, name: str = "corte.mp4") -> str:
    shutil.copy(make_video(name), panel.settings.input_dir / name)
    return Path(name).stem


def _transcribe(panel: SimpleNamespace, clip_id: str) -> None:
    response = panel.client.post(f"/api/cortes/{clip_id}/transcrever", headers=_headers(panel))
    assert response.status_code == 202
    _wait_state(panel, clip_id, "transcrito")


def _wait_state(panel: SimpleNamespace, clip_id: str, expected: str) -> None:
    state_file = panel.settings.output_dir / clip_id / "estado.json"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if state_file.is_file():
            data = json.loads(state_file.read_text(encoding="utf-8"))
            if data["transcription"]["state"] == expected:
                return
        time.sleep(0.05)
    pytest.fail(f"o estado não chegou a {expected} em 5 s")


def test_transcribe_creates_pt_srt_and_second_post_conflicts(
    panel_client: SimpleNamespace, make_video: MakeVideo
) -> None:
    clip_id = _add_video(panel_client, make_video)
    url = f"/api/cortes/{clip_id}/transcrever"

    first = panel_client.client.post(url, headers=_headers(panel_client))
    second = panel_client.client.post(url, headers=_headers(panel_client))

    assert first.status_code == 202
    assert first.json() == {"ok": True}
    assert second.status_code == 409
    _wait_state(panel_client, clip_id, "transcrito")
    assert (panel_client.settings.output_dir / clip_id / "pt.srt").is_file()


def test_transcribe_force_overwrites_edit(
    panel_client: SimpleNamespace, make_video: MakeVideo
) -> None:
    clip_id = _add_video(panel_client, make_video)
    _transcribe(panel_client, clip_id)
    pt_srt = panel_client.settings.output_dir / clip_id / "pt.srt"
    panel_client.client.put(
        f"/api/cortes/{clip_id}/pt-srt",
        content=SRT_VALIDO,
        headers={**_headers(panel_client), "Content-Type": "text/plain"},
    )
    assert "Texto revisado." in pt_srt.read_text(encoding="utf-8")

    response = panel_client.client.post(
        f"/api/cortes/{clip_id}/transcrever",
        json={"forcar": True},
        headers=_headers(panel_client),
    )

    assert response.status_code == 202
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and "Texto revisado." in pt_srt.read_text(encoding="utf-8"):
        time.sleep(0.05)
    assert "Texto revisado." not in pt_srt.read_text(encoding="utf-8")


def test_unknown_or_invalid_clip(panel_client: SimpleNamespace) -> None:
    headers = _headers(panel_client)
    assert (
        panel_client.client.post("/api/cortes/nada/transcrever", headers=headers).status_code == 404
    )
    assert panel_client.client.get("/api/cortes/nada/video").status_code == 404
    assert panel_client.client.get("/api/cortes/nada/contexto").status_code == 404
    assert panel_client.client.get("/api/cortes/.x/pt-srt").status_code == 400


def test_webvtt_preview(panel_client: SimpleNamespace, make_video: MakeVideo) -> None:
    """CT-08: WebVTT com a posição da queima; idioma inválido 400; sem arquivo 404."""
    clip_id = _add_video(panel_client, make_video)
    _transcribe(panel_client, clip_id)
    client = panel_client.client

    response = client.get(f"/api/cortes/{clip_id}/legendas/pt.vtt")

    assert response.status_code == 200
    assert response.text.startswith("WEBVTT")
    assert "line:80%,end" in response.text
    assert response.headers["content-type"].startswith("text/vtt")
    assert response.headers["cache-control"] == "no-store"
    assert client.get(f"/api/cortes/{clip_id}/legendas/PT.vtt").status_code == 400
    assert client.get(f"/api/cortes/{clip_id}/legendas/..%2Fx.vtt").status_code in (400, 404)
    assert client.get(f"/api/cortes/{clip_id}/legendas/e.vtt").status_code == 400
    assert client.get(f"/api/cortes/{clip_id}/legendas/en.vtt").status_code == 404


def test_edit_pt_srt(panel_client: SimpleNamespace, make_video: MakeVideo) -> None:
    """CT-09: SRT válido grava; inválido dá 422 com a linha e não muda o arquivo."""
    clip_id = _add_video(panel_client, make_video)
    _transcribe(panel_client, clip_id)
    pt_srt = panel_client.settings.output_dir / clip_id / "pt.srt"
    url = f"/api/cortes/{clip_id}/pt-srt"
    headers = {**_headers(panel_client), "Content-Type": "text/plain"}

    assert "Olá" in panel_client.client.get(url).text

    ok = panel_client.client.put(url, content=SRT_VALIDO.encode(), headers=headers)
    assert ok.status_code == 200
    assert ok.json()["transcription"]["state"] == "transcrito"
    assert "Texto revisado." in pt_srt.read_text(encoding="utf-8")

    before = pt_srt.read_bytes()
    bad = panel_client.client.put(url, content=b"1\nisto nao e tempo\nx\n", headers=headers)
    assert bad.status_code == 422
    assert isinstance(bad.json()["linha"], int)
    assert bad.json()["detail"]
    assert pt_srt.read_bytes() == before


def test_get_pt_srt_missing_is_404(panel_client: SimpleNamespace, make_video: MakeVideo) -> None:
    clip_id = _add_video(panel_client, make_video)
    assert panel_client.client.get(f"/api/cortes/{clip_id}/pt-srt").status_code == 404


def test_context_roundtrip(panel_client: SimpleNamespace, make_video: MakeVideo) -> None:
    """CT-10: o contexto volta igual e fica em entrada/<nome>.contexto.md."""
    clip_id = _add_video(panel_client, make_video)
    url = f"/api/cortes/{clip_id}/contexto"
    headers = {**_headers(panel_client), "Content-Type": "text/plain"}

    empty = panel_client.client.get(url)
    assert empty.status_code == 200
    assert empty.text == ""

    texto = "Vídeo sobre astronomia.\nTom leve."
    assert panel_client.client.put(url, content=texto.encode(), headers=headers).status_code == 200

    assert panel_client.client.get(url).text == texto
    arquivo = panel_client.settings.input_dir / f"{clip_id}.contexto.md"
    assert arquivo.read_text(encoding="utf-8") == texto


def test_listing_has_absolute_pt_srt(panel_client: SimpleNamespace, make_video: MakeVideo) -> None:
    """CT-11: depois da transcrição, a listagem traz o caminho absoluto do pt.srt."""
    clip_id = _add_video(panel_client, make_video)
    _transcribe(panel_client, clip_id)

    itens: list[dict[str, Any]] = panel_client.client.get("/api/cortes").json()

    caminho = Path(itens[0]["pt_srt"])
    assert caminho.is_absolute()
    assert caminho.is_relative_to(panel_client.settings.data_dir.resolve())
    assert str(caminho).endswith(f"/{clip_id}/pt.srt")


def test_video_supports_range(panel_client: SimpleNamespace, make_video: MakeVideo) -> None:
    clip_id = _add_video(panel_client, make_video)

    response = panel_client.client.get(
        f"/api/cortes/{clip_id}/video", headers={"Range": "bytes=0-99"}
    )

    assert response.status_code == 206
    assert len(response.content) == 100


def test_mutating_routes_require_csrf(panel_client: SimpleNamespace, make_video: MakeVideo) -> None:
    clip_id = _add_video(panel_client, make_video)
    client = panel_client.client
    base = f"/api/cortes/{clip_id}"

    assert client.post(f"{base}/transcrever").status_code == 403
    assert client.put(f"{base}/pt-srt", content=SRT_VALIDO).status_code == 403
    assert client.put(f"{base}/contexto", content="x").status_code == 403
