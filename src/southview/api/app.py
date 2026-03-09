"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from southview.config import get_config
from southview.db.engine import init_db

# Resolve frontend dist directory (relative to project root)
_FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend" / "dist"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = get_config()

    app = FastAPI(
        title="Southview OCR",
        description="Historical index card digitization pipeline",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def startup():
        init_db(config["database"]["path"])

    # Mount static frames directory BEFORE any catch-all route
    frames_dir = Path(config["storage"]["frames_dir"])
    frames_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static/frames", StaticFiles(directory=str(frames_dir)), name="frames")

    # Import and include routers
    from southview.api.routes import backup, cards, export, jobs, videos, stats, settings
    app.include_router(videos.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(cards.router, prefix="/api")
    app.include_router(export.router, prefix="/api")
    app.include_router(backup.router, prefix="/api")
    app.include_router(stats.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")

    # Serve frontend SPA (must be last — catches all non-API routes)
    if _FRONTEND_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIR / "assets")), name="frontend-assets")

        @app.get("/{path:path}")
        async def spa_fallback(path: str):
            """Serve frontend files, fall back to index.html for SPA routing."""
            file = _FRONTEND_DIR / path
            if file.is_file():
                return FileResponse(file)
            return FileResponse(_FRONTEND_DIR / "index.html")

    return app
