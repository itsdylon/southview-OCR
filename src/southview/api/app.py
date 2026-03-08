"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from southview.config import get_config
from southview.db.engine import init_db


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Southview OCR",
        description="Historical index card digitization pipeline",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def startup():
        init_db()
        # Mount static files for serving card images
        config = get_config()
        frames_dir = Path(config["storage"]["frames_dir"])
        frames_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/static/frames", StaticFiles(directory=str(frames_dir)), name="frames")

    # Import and include routers
    from southview.api.routes import backup, cards, export, jobs, videos
    app.include_router(videos.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(cards.router, prefix="/api")
    app.include_router(export.router, prefix="/api")
    app.include_router(backup.router, prefix="/api")

    return app
