from datetime import (
    datetime,
    timedelta,
    timezone,
)

from jose import jwt, JWTError

from passlib.context import (
    CryptContext,
)
from app.core.config import settings

from fastapi import (
    Depends,
    HTTPException,
)

from fastapi.security import (
    OAuth2PasswordBearer,
)


SECRET_KEY = settings.secret_key

ALGORITHM = settings.algorithm

ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes


pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(
    password: str,
) -> str:
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(
    data: dict,
) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return encoded_jwt


def get_current_username(
    token: str = Depends(oauth2_scheme),
) -> str:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Invalid authentication credentials",
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        username = payload.get("sub")

        if username is None:
            raise credentials_exception

        return username

    except JWTError:
        raise credentials_exception
