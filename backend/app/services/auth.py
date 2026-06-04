from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
)

from app.crud.user import (
    get_user_by_username,
    create_user,
)

from app.models.user import User

from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
)


def register_user_service(
    db: Session,
    user_data: UserRegister,
) -> User:
    existing_user = get_user_by_username(
        db=db,
        username=user_data.username,
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=400,
            detail="Username already exists",
        )

    hashed_password = hash_password(user_data.password)

    return create_user(
        db=db,
        username=user_data.username,
        hashed_password=hashed_password,
    )


def login_user_service(
    db: Session,
    user_data: UserLogin,
) -> TokenResponse:
    user = get_user_by_username(
        db=db,
        username=user_data.username,
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    valid_password = verify_password(
        user_data.password,
        user.hashed_password,
    )

    if not valid_password:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    access_token = create_access_token(data={"sub": user.username})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )
