from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.api.routes import router
from app.core.config import load_settings


def create_app() -> FastAPI:
    settings = load_settings()
    conn = db.connect(settings.db_path)
    db.init_database(conn)
    if settings.demo_mode:
        db.seed_demo_data(conn)

    app = FastAPI(title="Plex Media Manager", version="0.1.0")
    app.state.settings = settings
    app.state.db = conn
    app.include_router(router)

    static_dir = Path("frontend/dist")
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa_fallback(path: str) -> FileResponse:
            index = static_dir / "index.html"
            if path and (static_dir / path).is_file():
                return FileResponse(static_dir / path)
            return FileResponse(index)

    return app


app = create_app()
