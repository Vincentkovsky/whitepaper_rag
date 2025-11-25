from __future__ import annotations

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..services.subscription_service import get_subscription_service
from ..logging_utils import bind_user_context
from .config import UserContext, get_settings, Settings

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> UserContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    settings = get_settings()
    if settings.supabase_url and settings.supabase_anon_key and _looks_like_jwt(token):
        context = await _resolve_supabase_user(token, settings)
    else:
        context = _mock_user_context(token)
    bind_user_context(context.id)
    return context


async def _resolve_supabase_user(token: str, settings: Settings) -> UserContext:
    base_url = str(settings.supabase_url).rstrip("/")
    user_endpoint = f"{base_url}/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": settings.supabase_anon_key or "",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(user_endpoint, headers=headers)
    except httpx.HTTPError as exc:  # pragma: no cover - network failure
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Supabase unavailable") from exc

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    payload = response.json()
    user_id = payload.get("id")
    email = payload.get("email") or ""
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Supabase user payload")

    subscription = get_subscription_service()
    plan = subscription.get_user_plan(user_id)
    is_subscriber = plan != "free"
    return UserContext(id=user_id, email=email, is_subscriber=is_subscriber, access_token=token)


def _mock_user_context(token: str) -> UserContext:
    is_subscriber = token.endswith("-pro") or token.startswith("pro-")
    return UserContext(id=token, email=f"{token}@example.com", is_subscriber=is_subscriber, access_token=token)


def _looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2

