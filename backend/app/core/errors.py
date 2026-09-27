import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


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
        "instance": request.url.path,
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
        title = "Resource not found" if exception.status_code == 404 else "Request failed"
        error_code = "RESOURCE_NOT_FOUND" if exception.status_code == 404 else "HTTP_ERROR"
        return problem_response(
            request,
            status=exception.status_code,
            title=title,
            detail=str(exception.detail),
            error_code=error_code,
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exception: Exception) -> JSONResponse:
        logger.exception("Unhandled request failure for %s", request.url.path, exc_info=exception)
        return problem_response(
            request,
            status=500,
            title="Internal server error",
            detail="An unexpected error occurred.",
            error_code="INTERNAL_ERROR",
        )
