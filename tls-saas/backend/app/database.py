"""
Database setup — async SQLAlchemy engine + session factory.
Supports both SQLite (dev) and PostgreSQL (prod).
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    # SQLite needs check_same_thread=False
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """Dependency that yields an async DB session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables():
    """Create all tables (dev only — use Alembic in prod)."""
    async with engine.begin() as conn:
        from app.models import Base  # noqa: F811
        await conn.run_sync(Base.metadata.create_all)
