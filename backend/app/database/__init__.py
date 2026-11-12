"""Engine/session. FK enforcement is enabled for the application engine (SQLite pragma)."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_url = get_settings().database_url
_is_sqlite = _url.startswith("sqlite")
_is_memory = _is_sqlite and (_url in ("sqlite://", "sqlite:///:memory:") or ":memory:" in _url)

engine = create_engine(_url, connect_args={"check_same_thread": False} if _is_sqlite else {})

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        if not _is_memory:
            cur.execute("PRAGMA journal_mode=WAL")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401  (register models)

    Base.metadata.create_all(bind=engine)
