import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import get_settings

log = logging.getLogger("db")

settings = get_settings()

engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
log.info(
    "Database connection configured: %s pool_pre_ping=True pool_class=%s",
    engine.url.render_as_string(hide_password=True),
    type(engine.pool).__name__,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
