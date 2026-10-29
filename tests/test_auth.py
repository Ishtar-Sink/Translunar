"""Testes de autenticação do painel (CT-24)."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from translunar.core.config import load_settings
from translunar.panel.app import create_app
from translunar.panel.auth import CSRF_HEADER, LoginLimiter, client_ip


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("TRANSLUNAR_PAINEL_SENHA", "certa")
    monkeypatch.setenv("TRANSLUNAR_PAINEL_SEGREDO", "segredo-fixo-de-teste")
    settings = dataclasses.replace(load_settings(), data_dir=tmp_path)
    return TestClient(create_app(settings))


def _login(client: TestClient, senha: str = "certa") -> Any:
    return client.post("/api/login", json={"senha": senha})


def test_index_serves_html(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Translunar" in response.text


def test_ping_without_session_is_401(client: TestClient) -> None:
    assert client.get("/api/ping").status_code == 401


def test_session_endpoint_when_anonymous(client: TestClient) -> None:
    assert client.get("/api/sessao").json() == {"autenticado": False, "csrf": None}


def test_wrong_password_returns_401(client: TestClient) -> None:
    assert _login(client, "errada").status_code == 401


def test_login_blocks_after_five_failures(client: TestClient) -> None:
    for _ in range(5):
        assert _login(client, "errada").status_code == 401
    blocked = _login(client, "certa")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


def test_limiter_releases_after_block_period() -> None:
    now = [0.0]
    limiter = LoginLimiter(5, 15, clock=lambda: now[0])
    for _ in range(5):
        limiter.register_failure("1.2.3.4")
    assert limiter.is_blocked("1.2.3.4") == pytest.approx(15 * 60)
    assert limiter.is_blocked("5.6.7.8") == 0
    now[0] = 15 * 60 - 1
    assert limiter.is_blocked("1.2.3.4") > 0
    now[0] = 15 * 60 + 1
    assert limiter.is_blocked("1.2.3.4") == 0
    limiter.register_failure("1.2.3.4")
    assert limiter.is_blocked("1.2.3.4") == 0


def test_missing_password_env_is_503(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRANSLUNAR_PAINEL_SENHA", raising=False)
    monkeypatch.setenv("TRANSLUNAR_PAINEL_SEGREDO", "segredo-fixo-de-teste")
    # Impede que um .env real do projeto reponha a variável.
    monkeypatch.setattr("translunar.panel.app.load_env_file", lambda: None)
    settings = dataclasses.replace(load_settings(), data_dir=tmp_path)
    response = _login(TestClient(create_app(settings)), "qualquer")
    assert response.status_code == 503
    assert response.json() == {"detail": "senha do painel não configurada"}


def test_login_ok_then_ping(client: TestClient) -> None:
    response = _login(client)
    assert response.status_code == 200
    token = response.json()["csrf"]
    assert token
    assert client.get("/api/ping").status_code == 200
    assert client.get("/api/sessao").json() == {"autenticado": True, "csrf": token}


def test_post_without_csrf_is_403_and_with_csrf_is_200(client: TestClient) -> None:
    token = _login(client).json()["csrf"]
    assert client.post("/api/ping").status_code == 403
    assert client.post("/api/ping", headers={CSRF_HEADER: "outro"}).status_code == 403
    assert client.post("/api/ping", headers={CSRF_HEADER: token}).json() == {"ok": True}


def test_post_without_session_is_401(client: TestClient) -> None:
    assert client.post("/api/ping").status_code == 401


def test_logout_clears_session(client: TestClient) -> None:
    _login(client)
    assert client.post("/api/logout").status_code == 204
    assert client.get("/api/ping").status_code == 401


def test_session_secret_file_is_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLUNAR_PAINEL_SEGREDO", "")
    settings = dataclasses.replace(load_settings(), data_dir=tmp_path)
    create_app(settings)
    secret = tmp_path / ".segredo-sessao"
    assert secret.read_text(encoding="utf-8").strip()
    assert secret.stat().st_mode & 0o777 == 0o600


def _request(peer: str, forwarded: str | None) -> Request:
    headers = {"x-forwarded-for": forwarded} if forwarded else {}
    fake = SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)
    return cast(Request, fake)


def test_client_ip_trusts_forwarded_only_from_loopback() -> None:
    assert client_ip(_request("127.0.0.1", "10.0.0.5, 127.0.0.1")) == "10.0.0.5"
    assert client_ip(_request("127.0.0.1", None)) == "127.0.0.1"
    assert client_ip(_request("192.168.2.9", "10.0.0.5")) == "192.168.2.9"
