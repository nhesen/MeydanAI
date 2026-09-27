import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import DomainError

logger = logging.getLogger(__name__)

HTTP_TITLES = {
    400: ("Bad request", "BAD_REQUEST"),
    401: ("Authentication required", "AUTHENTICATION_REQUIRED"),
    403: ("Access denied", "ACCESS_DENIED"),
    404: ("Resource not found", "RESOURCE_NOT_FOUND"),
    409: ("Conflict", "CONFLICT"),
    422: ("Validation failed", "VALIDATION_ERROR"),
    429: ("Too many requests", "RATE_LIMITED"),
    500: ("Internal server error", "INTERNAL_ERROR"),
}


def safe_request_path(path: str) -> str:
    if path.startswith("/api/v1/join/"):
        return "/api/v1/join/[token]"
    return path


def problem_response(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str,
    error_code: str,
    errors: dict[str, str] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": safe_request_path(request.url.path),
        "errorCode": error_code,
        "timestamp": datetime.now(UTC),
    }
    if errors:
        content["errors"] = errors
    return JSONResponse(
        status_code=status,
        content=jsonable_encoder(content),
        media_type="application/problem+json",
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exception: DomainError) -> JSONResponse:
        return problem_response(
            request,
            status=exception.status,
            title=exception.title,
            detail=exception.detail,
            error_code=exception.error_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exception: RequestValidationError,
    ) -> JSONResponse:
        errors = {
            ".".join(str(part) for part in error["loc"]): str(error["msg"])
            for error in exception.errors()
        }
        return problem_response(
            request,
            status=422,
            title="Validation failed",
            detail="One or more fields are invalid.",
            error_code="VALIDATION_ERROR",
            errors=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request,
        exception: StarletteHTTPException,
    ) -> JSONResponse:
        title, error_code = HTTP_TITLES.get(
            exception.status_code,
            ("Request failed", "HTTP_ERROR"),
        )
        return problem_response(
            request,
            status=exception.status_code,
            title=title,
            detail=str(exception.detail),
            error_code=error_code,
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exception: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled request failure for %s",
            safe_request_path(request.url.path),
            exc_info=exception,
        )
        return problem_response(
            request,
            status=500,
            title="Internal server error",
            detail="An unexpected error occurred.",
            error_code="INTERNAL_ERROR",
        )
