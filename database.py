import os
import threading

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# For now this points at the hospital site's database. This backend only ever
# touches its own table (see models.py), so changing DATABASE_URL later is the
# whole migration.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Fail fast when the database is down, so a patient gets the "contact the
    # clinic directly" fallback instead of a long hang.
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 10})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

_tables_ready = False
_tables_lock = threading.Lock()


def ensure_tables() -> None:
    """Creates this backend's table on first use rather than only at startup,
    so the service recovers by itself if the database was down when it booted.
    Base only knows this backend's models, so no hospital table is affected."""
    global _tables_ready
    if _tables_ready:
        return
    with _tables_lock:
        if not _tables_ready:
            import models  # noqa: F401  (registers the table on Base)

            Base.metadata.create_all(bind=engine)
            _tables_ready = True


def get_db():
    ensure_tables()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def database_is_up() -> bool:
    try:
        ensure_tables()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
