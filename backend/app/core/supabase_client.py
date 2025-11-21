from __future__ import annotations

from functools import lru_cache

from typing import Any

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover
    Client = Any  # type: ignore
    create_client = None

from .config import get_settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise RuntimeError("Supabase configuration missing. Set SUPABASE_URL and SUPABASE_ANON_KEY.")
    if create_client is None:  # pragma: no cover
        raise RuntimeError("Supabase SDK is not installed. Install supabase==2.24.0 to enable this feature.")
    return create_client(str(settings.supabase_url), settings.supabase_anon_key)

