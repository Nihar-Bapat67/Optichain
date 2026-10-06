"""Shared helpers for route modules."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.db.repository import store


def parse_date_param(value: str | None, name: str) -> pd.Timestamp | None:
    """Parse an optional date query parameter; malformed input is a 422, not a 500."""
    if not value:
        return None
    try:
        return pd.to_datetime(value)
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(422, f"Invalid '{name}' date: {value!r}. Use YYYY-MM-DD.") from None


def cached_json(request: Request, build: Callable[[], Any]) -> Response:
    """Serve a GET whose body depends only on the loaded data.

    The payload is rendered once per (path, query, data version). Rendering via
    JSONResponse directly skips FastAPI's per-value jsonable_encoder pass; the
    payloads are already native Python types, so the bytes are identical.
    Exceptions raised by `build` (404/422/503) propagate and are never cached.
    """
    key = repr((request.url.path, sorted(request.query_params.multi_items())))
    body = store.response_bytes(key, lambda: JSONResponse(build()).body)
    return Response(content=body, media_type="application/json")
