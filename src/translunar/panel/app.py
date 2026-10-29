"""Aplicação FastAPI do painel: sessão, arquivos estáticos e pontos de extensão."""

from __future__ import annotations

import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from translunar.core.config import Settings, load_env_file, load_settings
from translunar.panel import (
    auth,
    events,
    routes_clips,
    routes_files,
    routes_review,
    routes_storage,
)
from translunar.panel.auth import MUTATING, PROTECTED, LoginLimiter
from translunar.panel.events import EventBus
from translunar.panel.jobs import JobRunner, recover_interrupted

STATIC_DIR = Path(__file__).resolve().parent / "static"
SECRET_ENV = "TRANSLUNAR_PAINEL_SEGREDO"
SECRET_FILENAME = ".segredo-sessao"


def _session_secret(settings: Settings) -> str:
    """Segredo da variável de ambiente ou de um arquivo na pasta de dados (criado com 600)."""
    from_env = os.environ.get(SECRET_ENV, "").strip()
    if from_env:
        return from_env
    path = settings.data_dir / SECRET_FILENAME
    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_urlsafe(32)
    path.write_text(secret, encoding="utf-8")
    path.chmod(0o600)
    return secret


def create_app(settings: Settings | None = None) -> FastAPI:
    load_env_file()
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        bus = EventBus()
        bus.bind_loop()
        app.state.bus = bus
        app.state.jobs = JobRunner(bus, settings.burn.jobs)
        recover_interrupted(settings.output_dir)
        yield

    app = FastAPI(
        title="Translunar",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.limiter = LoginLimiter(settings.panel.login_attempts, settings.panel.login_block_min)
    app.add_middleware(
        SessionMiddleware,
        secret_key=_session_secret(settings),
        session_cookie="translunar_sessao",
        same_site="strict",
        https_only=False,  # o TLS termina no Caddy
        max_age=7 * 24 * 3600,
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/ping", dependencies=PROTECTED)
    def ping_get() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/ping", dependencies=MUTATING)
    def ping_post() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(auth.router)
    # Rotas das funcionalidades: cada tarefa acrescenta o include_router da sua rota abaixo desta linha.  # noqa: E501
    app.include_router(routes_clips.router)
    app.include_router(routes_storage.router)
    app.include_router(routes_review.router)
    app.include_router(routes_files.router)
    app.include_router(events.router)

    return app
