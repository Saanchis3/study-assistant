from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = "sqlite:///./study.db"

# check_same_thread=False lets background tasks use SQLite safely
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """Gives each request its own database session, then closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()