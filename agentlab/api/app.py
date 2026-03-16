"""FastAPI application for AgentLab."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from agentlab.api.playground import router as playground_router
from agentlab.api.playground import set_conv_store
from agentlab.api.routes import router, set_store
from agentlab.storage.conversation_store import ConversationStore
from agentlab.storage.store import Store


def create_app(
    store: Store | None = None,
    conv_store: ConversationStore | None = None,
) -> FastAPI:
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

    if conv_store:
        set_conv_store(conv_store)

    # Register API routes first so they take precedence over the SPA catch‑all
    app.include_router(router)
    app.include_router(playground_router)

    dist_dir = Path(__file__).resolve().parent.parent.parent / "ui" / "dist"
    if dist_dir.exists():
        # Serve built SPA assets
        app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="ui-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_catch_all(full_path: str) -> FileResponse:  # type: ignore[valid-type]
            # Let API routes and docs handle their own paths
            if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("openapi"):
                raise HTTPException(status_code=404, detail="Not Found")
            index_file = dist_dir / "index.html"
            if not index_file.exists():
                raise HTTPException(status_code=404, detail="UI not built")
            return FileResponse(index_file)

    return app
