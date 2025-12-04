from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, String, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import func

from ..core.database import Base


class User(Base):
    """User model for PostgreSQL"""
    __tablename__ = "users"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # Null for OAuth-only users
    name = Column(String(255), nullable=True)
    avatar_url = Column(Text, nullable=True)
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    is_active = Column(Boolean, server_default='true', nullable=True)
    is_superuser = Column(Boolean, server_default='false', nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=True)

    def to_dict(self):
        return {
            "id": str(self.id),
            "email": self.email,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "google_id": self.google_id,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

