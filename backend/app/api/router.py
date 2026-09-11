"""Aggregates every route module into one router.

Registration order here determines the order paths appear in the OpenAPI
document; it has no effect on matching, since all paths are literal.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import analytics, catalog, forecast, risk, system

api_router = APIRouter()

api_router.include_router(system.router)
api_router.include_router(catalog.router)
api_router.include_router(analytics.router)
api_router.include_router(risk.router)
api_router.include_router(forecast.router)
