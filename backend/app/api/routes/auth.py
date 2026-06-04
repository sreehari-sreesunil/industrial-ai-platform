from fastapi import (
    APIRouter,
    Depends,
)

from sqlalchemy.orm import Session

from app.db.session import get_db


from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
)

from app.services.auth import (
    register_user_service,
    login_user_service,
)
from fastapi.security import (
    OAuth2PasswordRequestForm,
)

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post(
    "/register",
)
def register_user_endpoint(
    user_data: UserRegister,
    db: Session = Depends(get_db),
) -> dict:
    user = register_user_service(
        db=db,
        user_data=user_data,
    )

    return {
        "id": user.id,
        "username": user.username,
    }


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login_user_endpoint(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user_login = UserLogin(
        username=form_data.username,
        password=form_data.password,
    )

    return login_user_service(
        db=db,
        user_data=user_login,
    )
