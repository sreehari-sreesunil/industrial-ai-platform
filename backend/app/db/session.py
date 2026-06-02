from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    echo=True,
)

SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
