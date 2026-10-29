"""Testes das rotas de queima, download com Range e .zip do painel (CT-19, CT-20, CB-14)."""

from __future__ import annotations

import io
import json
import shutil
import time
import zipfile
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from translunar.core.pipeline import register_translation
from translunar.panel.auth import CSRF_HEADER

MakeVideo = Callable[..., Path]


@pytest.fixture(autouse=True)
def _fake_transcriber(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLUNAR_TRANSCRITOR", "falso")


def _headers(panel: SimpleNamespace) -> dict[str, str]:
    return {CSRF_HEADER: panel.csrf}


def _wait_for(panel: SimpleNamespace, clip_id: str, check: Callable[[dict], bool]) -> None:
    state_file = panel.settings.output_dir / clip_id / "estado.json"
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if state_file.is_file():
            data = json.loads(state_file.read_text(encoding="utf-8"))
            if check(data):
                return
        time.sleep(0.05)
    pytest.fail("o estado esperado não apareceu em 20 s")


def _prepare(panel: SimpleNamespace, make_video: MakeVideo, languages: tuple[str, ...]) -> str:
    """Corte transcrito (pt.srt) com uma tradução registrada por idioma."""
    shutil.copy(make_video("corte.mp4"), panel.settings.input_dir / "corte.mp4")
    response = panel.client.post("/api/cortes/corte/transcrever", headers=_headers(panel))
    assert response.status_code == 202
    _wait_for(panel, "corte", lambda d: d["transcription"]["state"] == "transcrito")
    folder = panel.settings.output_dir / "corte"
    for language in languages:
        shutil.copy(folder / "pt.srt", folder / f"{language}.srt")
        state, problems = register_translation(panel.settings, folder / f"{language}.srt")
        assert state is not None, problems
    return "corte"


def _fake_mp4(panel: SimpleNamespace, clip_id: str, language: str, size: int = 4096) -> Path:
    path = panel.settings.output_dir / clip_id / f"{language}.mp4"
    path.write_bytes(bytes(range(256)) * (size // 256))
    return path


@pytest.mark.ffmpeg
def test_download_supports_range(panel_client: SimpleNamespace, make_video: MakeVideo) -> None:
    """CT-19: Range devolve 206 com o trecho pedido."""
    clip_id = _prepare(panel_client, make_video, ("en",))
    mp4 = _fake_mp4(panel_client, clip_id, "en")

    response = panel_client.client.get(
        f"/api/cortes/{clip_id}/arquivos/en.mp4", headers={"Range": "bytes=0-1023"}
    )

    assert response.status_code == 206
    assert len(response.content) == 1024
    assert response.headers["content-range"] == f"bytes 0-1023/{mp4.stat().st_size}"
    assert response.headers["content-type"] == "video/mp4"


@pytest.mark.ffmpeg
def test_download_attachment_and_srt_type(
    panel_client: SimpleNamespace, make_video: MakeVideo
) -> None:
    clip_id = _prepare(panel_client, make_video, ("en",))

    inline = panel_client.client.get(f"/api/cortes/{clip_id}/arquivos/en.srt")
    attached = panel_client.client.get(f"/api/cortes/{clip_id}/arquivos/en.srt?baixar=1")

    assert inline.status_code == 200
    assert inline.headers["content-type"].startswith("application/x-subrip")
    assert "attachment" not in inline.headers.get("content-disposition", "")
    assert attached.headers["content-disposition"] == 'attachment; filename="corte-en.srt"'


@pytest.mark.ffmpeg
@pytest.mark.parametrize("name", ["..%2Festado.json", "en.txt", "estado.json", "e.srt", "EN.srt"])
def test_download_rejects_bad_names(
    panel_client: SimpleNamespace, make_video: MakeVideo, name: str
) -> None:
    clip_id = _prepare(panel_client, make_video, ("en",))

    response = panel_client.client.get(f"/api/cortes/{clip_id}/arquivos/{name}")

    assert response.status_code in (400, 404)


@pytest.mark.ffmpeg
def test_download_missing_file_and_clip(
    panel_client: SimpleNamespace, make_video: MakeVideo
) -> None:
    clip_id = _prepare(panel_client, make_video, ("en",))

    assert panel_client.client.get(f"/api/cortes/{clip_id}/arquivos/en.mp4").status_code == 404
    assert panel_client.client.get("/api/cortes/nao-existe/arquivos/en.srt").status_code == 404
    assert panel_client.client.get("/api/cortes/..x/arquivos/en.srt").status_code in (400, 404)


@pytest.mark.ffmpeg
def test_zip_has_all_languages_and_leaves_no_temp(
    panel_client: SimpleNamespace, make_video: MakeVideo
) -> None:
    """CT-20: o .zip traz srt e mp4 de cada idioma e não sobra temporário."""
    clip_id = _prepare(panel_client, make_video, ("en", "es"))
    _fake_mp4(panel_client, clip_id, "en")
    _fake_mp4(panel_client, clip_id, "es")

    response = panel_client.client.get(f"/api/cortes/{clip_id}/zip")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="corte.zip"'
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert archive.testzip() is None
        assert archive.getinfo("en.mp4").compress_type == zipfile.ZIP_STORED
        assert archive.getinfo("en.srt").compress_type == zipfile.ZIP_DEFLATED
    assert {"pt.srt", "en.srt", "en.mp4", "es.srt", "es.mp4"} <= names
    folder = panel_client.settings.output_dir / clip_id
    assert list(folder.glob(".zip-*.zip")) == []


@pytest.mark.ffmpeg
def test_zip_without_ready_video_is_404(
    panel_client: SimpleNamespace, make_video: MakeVideo
) -> None:
    clip_id = _prepare(panel_client, make_video, ("en",))

    response = panel_client.client.get(f"/api/cortes/{clip_id}/zip")

    assert response.status_code == 404
    assert list((panel_client.settings.output_dir / clip_id).glob(".zip-*.zip")) == []


@pytest.mark.ffmpeg
def test_burn_refuses_outdated_translation(
    panel_client: SimpleNamespace, make_video: MakeVideo
) -> None:
    """CB-14: pt.srt editado depois da tradução → 409 e nada enfileirado."""
    clip_id = _prepare(panel_client, make_video, ("en", "es"))
    pt_srt = panel_client.settings.output_dir / clip_id / "pt.srt"
    pt_srt.write_text("1\n00:00:00,500 --> 00:00:02,000\nTexto editado.\n", encoding="utf-8")

    response = panel_client.client.post(
        f"/api/cortes/{clip_id}/queimar",
        json={"idiomas": ["en", "es"]},
        headers=_headers(panel_client),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "tradução de en ausente ou desatualizada"
    assert not (panel_client.settings.output_dir / clip_id / "en.mp4").exists()


@pytest.mark.ffmpeg
def test_burn_refuses_missing_translation_without_queueing_any(
    panel_client: SimpleNamespace, make_video: MakeVideo
) -> None:
    clip_id = _prepare(panel_client, make_video, ("en",))

    response = panel_client.client.post(
        f"/api/cortes/{clip_id}/queimar",
        json={"idiomas": ["en", "es"]},
        headers=_headers(panel_client),
    )

    assert response.status_code == 409
    assert "es" in response.json()["detail"]
    assert not panel_client.client.app.state.jobs.is_busy(clip_id)  # type: ignore[attr-defined]


@pytest.mark.ffmpeg
@pytest.mark.parametrize(
    "body",
    [{"idiomas": []}, {"idiomas": ["EN"]}, {"idiomas": ["pt-BR"]}, {"idiomas": "en"}, {}, []],
)
def test_burn_validates_body(
    panel_client: SimpleNamespace, make_video: MakeVideo, body: object
) -> None:
    clip_id = _prepare(panel_client, make_video, ("en",))

    response = panel_client.client.post(
        f"/api/cortes/{clip_id}/queimar", json=body, headers=_headers(panel_client)
    )

    assert response.status_code == 400


def test_burn_unknown_clip_and_invalid_id(panel_client: SimpleNamespace) -> None:
    ok = {"idiomas": ["en"]}
    headers = _headers(panel_client)

    assert (
        panel_client.client.post("/api/cortes/nada/queimar", json=ok, headers=headers).status_code
        == 404
    )
    assert panel_client.client.post(
        "/api/cortes/..x/queimar", json=ok, headers=headers
    ).status_code in (400, 404)


@pytest.mark.ffmpeg
def test_burn_runs_and_creates_mp4(panel_client: SimpleNamespace, make_video: MakeVideo) -> None:
    """RF-21: a queima roda no worker, termina `pronto` e cria o en.mp4."""
    clip_id = _prepare(panel_client, make_video, ("en",))

    response = panel_client.client.post(
        f"/api/cortes/{clip_id}/queimar", json={"idiomas": ["en"]}, headers=_headers(panel_client)
    )

    assert response.status_code == 202
    _wait_for(
        panel_client, clip_id, lambda d: d.get("burns", {}).get("en", {}).get("state") == "pronto"
    )
    assert (panel_client.settings.output_dir / clip_id / "en.mp4").stat().st_size > 0


@pytest.mark.ffmpeg
def test_burn_of_several_languages_of_one_clip_all_finish(
    panel_client: SimpleNamespace, make_video: MakeVideo
) -> None:
    """Idiomas do mesmo corte queimam um de cada vez, sem esbarrar no lock do corte."""
    clip_id = _prepare(panel_client, make_video, ("en", "es", "fr"))

    response = panel_client.client.post(
        f"/api/cortes/{clip_id}/queimar",
        json={"idiomas": ["en", "es", "fr"]},
        headers=_headers(panel_client),
    )

    assert response.status_code == 202
    _wait_for(
        panel_client,
        clip_id,
        lambda d: all(
            d.get("burns", {}).get(lang, {}).get("state") == "pronto" for lang in ("en", "es", "fr")
        ),
    )
    for lang in ("en", "es", "fr"):
        assert (panel_client.settings.output_dir / clip_id / f"{lang}.mp4").stat().st_size > 0


@pytest.mark.ffmpeg
def test_languages_endpoint_reports_outdated(
    panel_client: SimpleNamespace, make_video: MakeVideo
) -> None:
    clip_id = _prepare(panel_client, make_video, ("en",))
    url = f"/api/cortes/{clip_id}/idiomas"
    assert panel_client.client.get(url).json()["en"]["traducao"] == "traduzido"

    pt_srt = panel_client.settings.output_dir / clip_id / "pt.srt"
    pt_srt.write_text("1\n00:00:00,500 --> 00:00:02,000\nOutro.\n", encoding="utf-8")

    assert panel_client.client.get(url).json()["en"]["traducao"] == "desatualizado"


def test_requires_csrf_and_session(panel_client: SimpleNamespace) -> None:
    url = "/api/cortes/corte/queimar"

    assert panel_client.client.post(url, json={"idiomas": ["en"]}).status_code == 403

    panel_client.client.cookies.clear()
    assert panel_client.client.get("/api/cortes/corte/arquivos/en.srt").status_code == 401
    assert panel_client.client.get("/api/cortes/corte/zip").status_code == 401
