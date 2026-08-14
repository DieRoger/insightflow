"""Centralized exception → HTTP response mapping.

Converts typed InsightFlowError subclasses into the standard error envelope.
Unknown exceptions become a generic 500 INTERNAL error (never a stack trace).
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    AIError,
    BusinessError,
    ExternalServiceError,
    InfrastructureError,
    InsightFlowError,
    MLError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.schemas.common import ErrorDetail, ErrorResponse

logger = get_logger(__name__)

ERROR_STATUS_MAP = {
    ValidationError: 422,
    BusinessError: 409,
    NotFoundError: 404,
    MLError: 500,
    AIError: 500,
    InfrastructureError: 503,
    ExternalServiceError: 502,
    InsightFlowError: 500,
}


def register_error_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI application."""

    @app.exception_handler(InsightFlowError)
    async def handle_insightflow_error(request: Request, exc: InsightFlowError) -> Response:
        status = ERROR_STATUS_MAP.get(type(exc), 500)
        request_id = getattr(request.state, "request_id", None)
        logger.error(
            "insightflow_error",
            code=exc.code,
            category=exc.category,
            status_code=status,
            error=str(exc),
        )
        return JSONResponse(
            status_code=status,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=exc.code,
                    message=exc.message,
                    details=exc.details,
                    category=exc.category,
                ),
                request_id=request_id or "",
            ).model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> Response:
        """Normalize FastAPI's built-in HTTP errors into the standard envelope."""
        request_id = getattr(request.state, "request_id", None)
        if exc.status_code == 404:
            code, category, message = "NF_099", "NOT_FOUND", "Endpoint not found"
        elif exc.status_code == 405:
            code, category, message = "VAL_005", "VALIDATION", "Method not allowed"
        elif exc.status_code == 401:
            code, category, message = "AUTH_001", "AUTHENTICATION", "Authentication required"
        else:
            code, category, message = "INT_099", "INTERNAL", str(exc.detail or "Request error")
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(code=code, message=message, category=category),
                request_id=request_id or "",
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> Response:
        request_id = getattr(request.state, "request_id", None)
        logger.exception(
            "unexpected_error",
            request_id=request_id,
            exc_type=type(exc).__name__,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INT_001",
                    message="Internal server error",
                    category="INTERNAL",
                ),
                request_id=request_id or "",
            ).model_dump(),
        )
