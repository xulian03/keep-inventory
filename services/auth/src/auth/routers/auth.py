from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import db as db_module
from auth import security
from auth.models import User
from auth.rbac import create_access_token, get_current_user
from auth.schemas import LoginRequest, LoginResponse, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


def get_session() -> Iterator[Session]:
    engine = db_module.get_engine()
    session_factory = db_module.get_session_factory(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    session: Session = Depends(get_session),
) -> LoginResponse:
    user = session.query(User).filter(User.email == payload.email).first()
    if user is None or not security.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = create_access_token(user.id, user.role, user.name)
    return LoginResponse(
        token=token,
        user=UserPublic(id=user.id, name=user.name, email=user.email, role=user.role),
    )


@router.get("/me", response_model=UserPublic)
def me(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserPublic:
    user = session.get(User, current_user["id"])
    if user is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return UserPublic(id=user.id, name=user.name, email=user.email, role=user.role)
