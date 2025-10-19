from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal # SessionLocal is now async


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an asynchronous database session.
    
    Yields:
        AsyncSession: A SQLAlchemy asynchronous database session
    """
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            # The async context manager handles the close automatically,
            # but we ensure it by awaiting close if needed.
            # In most cases, this explicit close might be redundant due to `async with`.
            pass # `async with` handles closing 