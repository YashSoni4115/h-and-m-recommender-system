"""Supabase client singleton loaded from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client

# Load .env sitting next to this file, regardless of cwd.
load_dotenv(Path(__file__).resolve().parent / ".env")


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Return a cached Supabase client instance.

    Reads SUPABASE_URL and SUPABASE_KEY from the environment.
    Raises RuntimeError if either is missing.
    """
    url = os.getenv("sb_url") or os.getenv("SUPABASE_URL")
    key = (
        os.getenv("sb_secret")
        or os.getenv("sb_publishable")
        or os.getenv("SUPABASE_KEY")
    )

    if not url or not key:
        raise RuntimeError(
            "Missing Supabase credentials. Set sb_url and sb_secret "
            "(or SUPABASE_URL / SUPABASE_KEY) in your .env file."
        )

    return create_client(url, key)
