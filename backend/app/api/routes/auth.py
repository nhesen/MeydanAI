from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import parse_bearer_token, require_user
from app.models.domain import User
from app.schemas.auth import AuthCredentials, AuthSessionResponse, UserResponse
from app.schemas.common import ApiResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(require_user)]


@router.post(
    "/register",
    response_model=ApiResponse[AuthSessionResponse],
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: AuthCredentials,
    session: DatabaseSession,
) -> ApiResponse[AuthSessionResponse]:
    return ApiResponse(data=AuthService(session).register(payload))


@router.post("/login", response_model=ApiResponse[AuthSessionResponse])
def login(
    payload: AuthCredentials,
    session: DatabaseSession,
) -> ApiResponse[AuthSessionResponse]:
    return ApiResponse(data=AuthService(session).login(payload))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    session: DatabaseSession,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> None:
    token = parse_bearer_token(authorization)
    if token is not None:
        AuthService(session).logout(token)


@router.get("/me", response_model=ApiResponse[UserResponse])
def me(user: CurrentUser) -> ApiResponse[UserResponse]:
    return ApiResponse(data=UserResponse.model_validate(user))
