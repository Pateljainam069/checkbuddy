"""Supabase client construction.

The service role key is used because this MVP has no auth layer and RLS is
disabled (see schema.sql). It must never reach the frontend — the browser gets
the anon key or, as built here, talks only to this backend.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

LABEL_BUCKET = "label-photos"

# Placeholder values shipped in .env.example must not be mistaken for real ones.
_PLACEHOLDERS = {
    "your-project-url",
    "your-service-role-key",
    "https://your-project.supabase.co",
}


def is_configured() -> bool:
    """True only when both credentials are present and not still placeholders."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False
    if SUPABASE_URL in _PLACEHOLDERS or SUPABASE_SERVICE_ROLE_KEY in _PLACEHOLDERS:
        return False
    return SUPABASE_URL.startswith("http")


def get_client():
    """A configured Supabase client. Raises if credentials are absent."""
    if not is_configured():
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY in backend/.env"
        )
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
