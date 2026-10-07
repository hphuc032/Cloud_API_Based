from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings


# ── Engine ────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,          # Verify connections before use
    pool_size=10,
    max_overflow=20,
    pool_timeout=3,
    connect_args={"connect_timeout": 3},
    echo=settings.DEBUG,         # Log SQL only in debug mode
)

# ── Session factory ───────────────────────────────────────────
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ── Base class for all models ─────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── FastAPI dependency ────────────────────────────────────────
def get_db():
    """Yield a DB session and ensure it's closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
