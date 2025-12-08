from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User


class UserRepository:
    """Repository for user database operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, email: str, hashed_password: Optional[str] = None, name: Optional[str] = None, google_id: Optional[str] = None, avatar_url: Optional[str] = None) -> User:
        """Create a new user"""
        user = User(
            email=email,
            hashed_password=hashed_password,
            name=name,
            google_id=google_id,
            avatar_url=avatar_url,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_google_id(self, google_id: str) -> Optional[User]:
        """Get user by Google ID"""
        result = await self.session.execute(
            select(User).where(User.google_id == google_id)
        )
        return result.scalar_one_or_none()

    async def update(self, user: User) -> User:
        """Update user"""
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def list_all(self) -> list[User]:
        """List all users ordered by creation date"""
        result = await self.session.execute(
            select(User).order_by(User.created_at.desc())
        )
        return list(result.scalars().all())
