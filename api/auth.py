"""
API key authentication for the FastAPI backend.
The Next.js frontend sends X-API-Key header on every request.
The key is a shared secret stored in env vars on both services.
"""

import os
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(_api_key_header)) -> str:
    """FastAPI dependency — raises 401 if key is missing or wrong."""
    expected = os.environ.get("DASHBOARD_API_KEY", "")
    if not expected:
        raise RuntimeError("DASHBOARD_API_KEY env var is not set")
    if not api_key or api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key
