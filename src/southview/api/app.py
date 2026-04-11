"""FastAPI application factory."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from southview.auth import get_authenticated_user
from southview.config import get_config
from southview.db.engine import init_db

# Resolve frontend dist directory (relative to project root)
_FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend" / "dist"
_DEFAULT_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def _resolve_frontend_file(path: str) -> Path | None:
    """Return a safe frontend file path, or None if it escapes the dist dir."""
    frontend_root = _FRONTEND_DIR.resolve()
    candidate = (frontend_root / path).resolve(strict=False)
    try:
        candidate.relative_to(frontend_root)
    except ValueError:
        return None
    return candidate


def _cors_origins() -> list[str]:
    configured = os.getenv("SOUTHVIEW_CORS_ORIGINS")
    if not configured:
        return list(_DEFAULT_CORS_ORIGINS)
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return origins or list(_DEFAULT_CORS_ORIGINS)


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
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def require_auth(request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS":
            return await call_next(request)
        if path.startswith("/api") and not path.startswith("/api/auth"):
            try:
                get_authenticated_user(request)
            except Exception as exc:
                if hasattr(exc, "status_code"):
                    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
                raise
        return await call_next(request)

    @app.on_event("startup")
    def startup():
        init_db(config["database"]["path"])

    # Mount static frames directory BEFORE any catch-all route
    frames_dir = Path(config["storage"]["frames_dir"])
    frames_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static/frames", StaticFiles(directory=str(frames_dir)), name="frames")

    # Import and include routers
    from southview.api.routes import auth, backup, cards, export, jobs, videos, stats, settings
    app.include_router(auth.router, prefix="/api")
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
            file = _resolve_frontend_file(path)
            if file and file.is_file():
                return FileResponse(file)
            return FileResponse(_FRONTEND_DIR / "index.html")

    return app
