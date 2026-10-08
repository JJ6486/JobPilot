"""SQLite engine, sessions, and migrate-on-startup."""

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from alembic import command
from alembic.config import Config
from fastapi import Depends
from sqlalchemy import Engine, event
from sqlmodel import Session, create_engine

from app.config import Settings, get_settings

BACKEND_DIR = Path(__file__).resolve().parents[2]


@lru_cache
def _engine_for(db_url: str) -> Engine:
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragmas(conn, _record) -> None:  # type: ignore[no-untyped-def]
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")  # API reads while a background task writes
        cur.close()

    return engine


def db_url(settings: Settings) -> str:
    return f"sqlite:///{settings.db_path.as_posix()}"


def get_engine(settings: Settings) -> Engine:
    return _engine_for(db_url(settings))


def init_db(settings: Settings) -> None:
    """Create data/ if needed and apply any pending Alembic migrations."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "app" / "db" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url(settings))
    command.upgrade(cfg, "head")


def get_session(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[Session]:
    with Session(get_engine(settings)) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
