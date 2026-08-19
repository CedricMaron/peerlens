"""PeerLens application entry point.

One FastAPI process serves both the JSON API (under ``/api``) and the compiled
React application, so the whole product is a single container on a single port.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from . import config
from .db import init_db
from .llm.base import ErrorCode, LLMError
from .routers import (
    checklist,
    literature_router,
    manuscript_router,
    research,
    settings_router,
    usage_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("peerlens")

VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    config.ensure_directories()
    init_db()
    logger.info("PeerLens %s — data directory: %s", VERSION, config.DATA_DIR)
    logger.info("Prompts loaded from: %s", config.PROMPTS_DIR)
    yield


app = FastAPI(
    title="PeerLens",
    description="AI-assisted scientific research quality control.",
    version=VERSION,
    lifespan=lifespan,
)

# The Vite dev server runs on a different port during native development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        # Browsers resolve any *.localhost name to loopback, and PeerLens
        # advertises this one so it stands out among other local tools.
        "http://peerlens.localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LLMError)
async def handle_llm_error(_: Request, exc: LLMError) -> JSONResponse:
    """Provider misconfiguration is a user-fixable problem, not a server fault.

    ``detail`` stays a plain sentence for the UI; ``code`` is the normalized
    classification. Provider stderr stays in the server log.
    """
    status = 499 if exc.code == ErrorCode.REQUEST_CANCELLED.value else 400
    if exc.detail:
        logger.warning("Provider error [%s]: %s", exc.code, exc.detail[:2000])
    return JSONResponse(status_code=status, content={"detail": str(exc), "code": exc.code})


for router in (
    research.router,
    checklist.router,
    literature_router.router,
    manuscript_router.router,
    settings_router.router,
    usage_router.router,
):
    app.include_router(router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": VERSION,
        "data_dir": str(config.DATA_DIR),
        "database": str(config.DB_PATH),
    }


# --------------------------------------------------------------------------
# Static frontend
# --------------------------------------------------------------------------

def mount_frontend(application: FastAPI) -> None:
    dist = config.STATIC_DIR
    index = dist / "index.html"
    if not index.is_file():
        logger.warning(
            "No compiled frontend at %s — API only. Run `npm run build` in frontend/, "
            "or use the Vite dev server on :5173.",
            dist,
        )

        @application.get("/")
        def missing_frontend() -> dict:  # pragma: no cover - developer convenience
            return {
                "message": "PeerLens API is running, but the frontend has not been built.",
                "api_docs": "/docs",
            }

        return

    assets = dist / "assets"
    if assets.is_dir():
        application.mount("/assets", StaticFiles(directory=assets), name="assets")

    @application.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        """Serve real files where they exist, otherwise the SPA entry point."""
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


mount_frontend(app)


def run() -> None:  # pragma: no cover - console entry point
    import os

    import uvicorn

    uvicorn.run(
        "peerlens.main:app",
        host=os.environ.get("PEERLENS_HOST", "0.0.0.0"),  # noqa: S104 - local-first app
        port=int(os.environ.get("PEERLENS_PORT", 8000)),
        reload=False,
    )
