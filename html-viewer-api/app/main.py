"""FastAPI application.

Run locally with `uvicorn app.main:app`. In Azure it is hosted by the Function
App through the ASGI wrapper in function_app.py.

Authorization in front of these routes is enforced by Static Web Apps (see
staticwebapp.config.json in html-viewer-web): /api/public/* is anonymous, the
rest of /api/* requires a signed-in user. Endpoints check the user again.
"""

from __future__ import annotations

from fastapi import FastAPI, Request

from .core.error_handlers import NO_STORE, register_error_handlers
from .files.router import router as files_router
from .labels.router import router as labels_router
from .shares.router import router as shares_router

API_PREFIX = "/api"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Visor HTML API",
        version="1.0.0",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    register_error_handlers(app)

    @app.middleware("http")
    async def no_store(request: Request, call_next):
        response = await call_next(request)
        response.headers.update(NO_STORE)
        return response

    app.include_router(files_router, prefix=API_PREFIX)
    app.include_router(shares_router, prefix=API_PREFIX)
    app.include_router(labels_router, prefix=API_PREFIX)

    @app.get(f"{API_PREFIX}/public/health", tags=["health"], summary="Liveness check")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
