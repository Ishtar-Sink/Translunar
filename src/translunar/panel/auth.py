"""Autenticação do painel: login por senha única, sessão por cookie, CSRF e limite de tentativas."""

from __future__ import annotations

import hmac
import math
import os
import secrets
import time
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

PASSWORD_ENV = "TRANSLUNAR_PAINEL_SENHA"
CSRF_HEADER = "X-CSRF-Token"
LOOPBACK = "127.0.0.1"


class LoginLimiter:
    """Conta falhas de login por IP e bloqueia o IP depois de `max_attempts` falhas seguidas."""

    def __init__(
        self,
        max_attempts: int,
        block_minutes: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_attempts = max_attempts
        self._block_seconds = block_minutes * 60
        self._clock = clock
        self._failures: dict[str, int] = {}
        self._blocked_until: dict[str, float] = {}

    def is_blocked(self, ip: str) -> float:
        """Segundos restantes de bloqueio; 0 se o IP está livre."""
        until = self._blocked_until.get(ip)
        if until is None:
            return 0.0
        remaining = until - self._clock()
        if remaining <= 0:
            self.reset(ip)
            return 0.0
        return remaining

    def register_failure(self, ip: str) -> None:
        count = self._failures.get(ip, 0) + 1
        if count >= self._max_attempts:
            self._blocked_until[ip] = self._clock() + self._block_seconds
            self._failures.pop(ip, None)
        else:
            self._failures[ip] = count

    def reset(self, ip: str) -> None:
        self._failures.pop(ip, None)
        self._blocked_until.pop(ip, None)


def client_ip(request: Request) -> str:
    """IP do cliente. Atrás do Caddy local (peer 127.0.0.1) vale o `X-Forwarded-For`."""
    peer = request.client.host if request.client else "desconhecido"
    if peer == LOOPBACK:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return peer


def require_session(request: Request) -> None:
    if not request.session.get("auth"):
        raise HTTPException(status_code=401, detail="autenticação necessária")


def require_csrf(request: Request) -> None:
    expected = request.session.get("csrf")
    received = request.headers.get(CSRF_HEADER, "")
    if not expected or not hmac.compare_digest(str(expected), received):
        raise HTTPException(status_code=403, detail="token CSRF inválido")


# Contrato para as próximas tarefas: PROTECTED em rotas de leitura, MUTATING nas que alteram.
PROTECTED: list[Any] = [Depends(require_session)]
MUTATING: list[Any] = [Depends(require_session), Depends(require_csrf)]

router = APIRouter(prefix="/api")


@router.post("/login")
async def login(request: Request) -> dict[str, str]:
    password = os.environ.get(PASSWORD_ENV, "")
    if not password:
        raise HTTPException(status_code=503, detail="senha do painel não configurada")
    limiter: LoginLimiter = request.app.state.limiter
    ip = client_ip(request)
    remaining = limiter.is_blocked(ip)
    if remaining > 0:
        raise HTTPException(
            status_code=429,
            detail="muitas tentativas",
            headers={"Retry-After": str(math.ceil(remaining))},
        )
    try:
        body = await request.json()
    except ValueError:
        body = {}
    sent = body.get("senha", "") if isinstance(body, dict) else ""
    if not isinstance(sent, str) or not hmac.compare_digest(
        sent.encode("utf-8"), password.encode("utf-8")
    ):
        limiter.register_failure(ip)
        raise HTTPException(status_code=401, detail="senha incorreta")
    limiter.reset(ip)
    token = secrets.token_urlsafe(32)
    request.session["auth"] = True
    request.session["csrf"] = token
    return {"csrf": token}


@router.post("/logout", status_code=204)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=204)


@router.get("/sessao")
def session_state(request: Request) -> dict[str, Any]:
    authenticated = bool(request.session.get("auth"))
    return {
        "autenticado": authenticated,
        "csrf": request.session.get("csrf") if authenticated else None,
    }
