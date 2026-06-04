from sqlalchemy import select

from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_username(
    db: Session,
    username: str,
) -> User | None:
    statement = select(User).where(User.username == username)

    result = db.execute(statement)

    return result.scalar_one_or_none()


def create_user(
    db: Session,
    username: str,
    hashed_password: str,
) -> User:
    user = User(
        username=username,
        hashed_password=hashed_password,
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    return user
