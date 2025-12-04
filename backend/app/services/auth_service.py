from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import Settings, get_settings
from ..repositories.user_repository import UserRepository
from ..models.user import User

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Authentication service"""

    def __init__(self, session: AsyncSession, settings: Optional[Settings] = None):
        self.session = session
        self.user_repo = UserRepository(session)
        self.settings = settings or get_settings()

    def hash_password(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password"""
        return pwd_context.verify(plain_password, hashed_password)

    def create_access_token(self, user_id: str, email: str) -> str:
        """Create JWT access token"""
        expire = datetime.utcnow() + timedelta(minutes=self.settings.access_token_expire_minutes)
        to_encode = {
            "sub": user_id,
            "email": email,
            "exp": expire,
        }
        encoded_jwt = jwt.encode(
            to_encode,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm
        )
        return encoded_jwt

    def decode_token(self, token: str) -> dict:
        """Decode and validate JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm]
            )
            return payload
        except JWTError:
            raise ValueError("Invalid token")

    async def register_user(self, email: str, password: str, name: Optional[str] = None) -> User:
        """Register a new user with email and password"""
        # Check if user already exists
        existing_user = await self.user_repo.get_by_email(email)
        if existing_user:
            raise ValueError("User with this email already exists")

        #Hash password
        hashed_password = self.hash_password(password)

        # Create user
        user = await self.user_repo.create(
            email=email,
            hashed_password=hashed_password,
            name=name,
        )
        await self.session.commit()
        return user

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = await self.user_repo.get_by_email(email)
        if not user or not user.hashed_password:
            return None

        if not self.verify_password(password, user.hashed_password):
            return None

        return user

    async def get_or_create_google_user(self, google_id: str, email: str, name: Optional[str] = None, avatar_url: Optional[str] = None) -> User:
        """Get or create user from Google OAuth"""
        # Try to find by Google ID first
        user = await self.user_repo.get_by_google_id(google_id)
        if user:
            # Update avatar if missing
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
                user = await self.user_repo.update(user)
                await self.session.commit()
            return user

        # Try to find by email
        user = await self.user_repo.get_by_email(email)
        if user:
            # Link Google ID to existing user
            user.google_id = google_id
            if name and not user.name:
                user.name = name
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
            user = await self.user_repo.update(user)
            await self.session.commit()
            return user

        # Create new user
        user = await self.user_repo.create(
            email=email,
            google_id=google_id,
            name=name,
            avatar_url=avatar_url,
        )
        await self.session.commit()
        return user

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID"""
        return await self.user_repo.get_by_id(user_id)
