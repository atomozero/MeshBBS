"""
MeshCore BBS Web Administration Interface - Main Application.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError

from web import __version__
from web.config import get_web_config
from web.api.v1.router import api_router
from web.auth.routes import router as auth_router
from web.websocket.routes import router as websocket_router

# Path to the built frontend files
FRONTEND_DIR = Path(__file__).parent.parent.parent.parent / "web" / "dist"


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    config = get_web_config()
    logger.info(f"Starting MeshBBS Web Interface v{__version__}")
    logger.info(f"Server: {config.host}:{config.port}")
    logger.info(f"Debug mode: {config.debug}")

    yield

    logger.info("Shutting down MeshBBS Web Interface")


def create_app(config: Optional["WebConfig"] = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        config: Optional WebConfig instance. If not provided, loads from environment.

    Returns:
        Configured FastAPI application.
    """
    if config is None:
        config = get_web_config()

    app = FastAPI(
        title="MeshBBS Admin API",
        description="REST API for MeshCore BBS Administration",
        version=__version__,
        docs_url="/api/docs" if config.debug else None,
        redoc_url="/api/redoc" if config.debug else None,
        openapi_url="/api/openapi.json" if config.debug else None,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count", "X-Page", "X-Per-Page", "X-Pages"],
    )

    # Include routers
    app.include_router(auth_router)
    app.include_router(api_router)
    app.include_router(websocket_router)

    # Exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle validation errors with Italian messages."""
        errors = []
        for error in exc.errors():
            field = ".".join(str(x) for x in error["loc"][1:]) if len(error["loc"]) > 1 else error["loc"][0]
            errors.append({
                "field": field,
                "message": error["msg"],
                "type": error["type"],
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Errore di validazione",
                "details": errors,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected errors."""
        logger.exception(f"Unexpected error: {exc}")

        if config.debug:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Errore interno del server",
                    "detail": str(exc),
                },
            )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Errore interno del server"},
        )

    # Health check (no auth required)
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        from datetime import datetime
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": __version__,
        }

    # Serve frontend static files if available
    if FRONTEND_DIR.exists():
        # Mount static assets
        assets_dir = FRONTEND_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # Serve index.html for SPA routes
        @app.get("/")
        async def serve_spa_root():
            """Serve the frontend SPA."""
            index_file = FRONTEND_DIR / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return JSONResponse(
                content={
                    "name": "MeshBBS Admin API",
                    "version": __version__,
                    "status": "online",
                    "frontend": "not built",
                }
            )

        # Catch-all for SPA client-side routing
        @app.get("/{full_path:path}")
        async def serve_spa_fallback(full_path: str):
            """Serve index.html for all non-API routes (SPA routing)."""
            # Don't serve index.html for API or WebSocket routes
            if full_path.startswith(("api/", "auth/", "ws", "health")):
                return JSONResponse(
                    status_code=404,
                    content={"error": "Endpoint non trovato"}
                )

            # Check if it's a static file request
            static_file = FRONTEND_DIR / full_path
            if static_file.exists() and static_file.is_file():
                return FileResponse(static_file)

            # Otherwise serve index.html for SPA routing
            index_file = FRONTEND_DIR / "index.html"
            if index_file.exists():
                return FileResponse(index_file)

            return JSONResponse(
                status_code=404,
                content={"error": "Risorsa non trovata"}
            )
    else:
        # Root endpoint when frontend is not built
        @app.get("/")
        async def root():
            """Root endpoint with API info."""
            return {
                "name": "MeshBBS Admin API",
                "version": __version__,
                "status": "online",
                "docs": "/api/docs" if config.debug else None,
                "frontend": "not built - run 'npm run build' in web/ directory",
            }

    return app


# Create default app instance
app = create_app()


def run_server(host: str = None, port: int = None, reload: bool = False):
    """
    Run the web server.

    Args:
        host: Server host (default from config)
        port: Server port (default from config)
        reload: Enable auto-reload for development
    """
    import uvicorn

    config = get_web_config()

    uvicorn.run(
        "web.main:app",
        host=host or config.host,
        port=port or config.port,
        reload=reload,
        log_level="info" if config.debug else "warning",
    )


if __name__ == "__main__":
    run_server(reload=True)
