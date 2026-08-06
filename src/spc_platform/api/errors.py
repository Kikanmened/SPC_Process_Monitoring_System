"""Map platform errors to HTTP responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from spc_platform.common.errors import (
    AuditWriteError,
    InsufficientDataError,
    NoActiveBaselineError,
    SPCPlatformError,
    UnauthorisedActionError,
    UnstableProcessError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers for the typed platform errors use cases raise."""

    @app.exception_handler(UnauthorisedActionError)
    async def _unauthorised(_request: Request, exc: UnauthorisedActionError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"error": type(exc).__name__, "message": str(exc), "context": exc.context},
        )

    @app.exception_handler(UnstableProcessError)
    async def _unstable(_request: Request, exc: UnstableProcessError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": type(exc).__name__, "message": str(exc), "context": exc.context},
        )

    @app.exception_handler(NoActiveBaselineError)
    async def _no_baseline(_request: Request, exc: NoActiveBaselineError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": type(exc).__name__, "message": str(exc), "context": exc.context},
        )

    @app.exception_handler(InsufficientDataError)
    async def _insufficient(_request: Request, exc: InsufficientDataError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": type(exc).__name__, "message": str(exc), "context": exc.context},
        )

    @app.exception_handler(AuditWriteError)
    async def _audit(_request: Request, exc: AuditWriteError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"error": type(exc).__name__, "message": str(exc), "context": exc.context},
        )

    @app.exception_handler(SPCPlatformError)
    async def _platform(_request: Request, exc: SPCPlatformError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": type(exc).__name__, "message": str(exc), "context": exc.context},
        )

    @app.exception_handler(ValueError)
    async def _value(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": "ValueError", "message": str(exc)},
        )

    @app.exception_handler(KeyError)
    async def _key(_request: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": "KeyError", "message": str(exc)},
        )
