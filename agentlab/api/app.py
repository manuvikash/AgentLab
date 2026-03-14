"""FastAPI application for AgentLab."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from agentlab.api.routes import router, set_store
from agentlab.storage.store import Store


def create_app(store: Store | None = None) -> FastAPI:
    app = FastAPI(title="AgentLab", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if store:
        set_store(store)

    app.include_router(router)

    dist_dir = Path(__file__).resolve().parent.parent.parent / "ui" / "dist"
    if dist_dir.exists():
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="ui")

    return app
