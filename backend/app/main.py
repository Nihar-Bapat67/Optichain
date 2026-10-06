"""Application entry point.

Routes live in `app/api/routes/`; this module only wires the application
together: logging, middleware, artifact loading and router registration.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import settings
from app.core.logging import configure_logging, get_logger, request_id_var
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.state import registry
from app.db.engine import dispose_engine, get_engine
from app.db.ingest import ensure_database
from app.db.repository import DataUnavailable, store
from app.services import artifacts
from app.services.demand_agent import run_forecast_agent

logger = get_logger(__name__)

API_DESCRIPTION = """
Analytics API for the **Control Tower** supply-chain dashboard.

Three model families back the endpoints below:

* **MODEL1** — XGBoost baseline demand.
* **MODEL2** — influencer uplift bundle (lift curve, peak lift, decay λ).
* **MODEL3 / conti** — LightGBM city-level growth.

Artifacts are loaded once at startup. Any that are missing are reported by
`/api/health` rather than failing the service, so the dashboard can show a
setup screen instead of an error.
"""


def _warm_models() -> None:
    """Run one throwaway prediction through every model.

    scikit-learn and XGBoost import much of their prediction machinery lazily,
    so without this the first visitor's forecast paid ~15s of import time.
    """
    started = time.perf_counter()
    try:
        run_forecast_agent(
            product_id="WARMUP",
            city="Mumbai",
            date="2024-01-01",
            influencer={"id": "warmup", "followers": 100000, "engagement_rate": 0.03, "platform": "instagram"},
            campaign_active=True,
            models=registry.as_agent_payload(),
        )
        logger.info("Models warmed in %.2fs", time.perf_counter() - started)
    except Exception:
        logger.exception("Model warm-up failed; first forecast will be slower")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Load model artifacts once, before the first request is served."""
    configure_logging(settings.log_level)
    logger.info("Starting %s — project root: %s", settings.app_name, settings.root())

    model1, model1_feats, model1_msgs = artifacts.try_load_model1()
    registry.model1 = model1
    registry.model1_features = model1_feats

    model2, model2_feats, model2_msgs = artifacts.try_load_model2_bundle()
    registry.model2 = model2
    registry.model2_features = model2_feats

    conti, conti_feats, conti_msgs = artifacts.try_load_conti_model()
    registry.conti = conti
    registry.conti_features = conti_feats

    registry.load_messages = model1_msgs + model2_msgs + conti_msgs

    logger.info(
        "Artifacts loaded — MODEL1: %s | MODEL2 targets: %d | conti: %s",
        "ok" if registry.model1_loaded else "missing",
        registry.model2_targets_loaded,
        "ok" if registry.conti_loaded else "missing",
    )
    for message in registry.load_messages:
        logger.warning("Artifact notice: %s", message)

    _warm_models()

    # A database failure must not take the service down: /api/health reports
    # it and data endpoints answer 503, exactly as missing CSVs used to.
    try:
        store.init_status = ensure_database(get_engine())
        store.init_error = None
        store.invalidate()
        if store.has_demand():
            store.warm()
        logger.info("Database: %s", store.init_status)
    except Exception as e:
        store.init_error = f"{type(e).__name__}: {e}"
        logger.exception("Database initialisation failed")

    yield

    dispose_engine()
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        description=API_DESCRIPTION,
        version=settings.app_version,
        lifespan=lifespan,
    )

    origins = settings.cors_list()
    allow_all_origins = "*" in origins

    # Middleware runs bottom-up, so security headers are applied to the final
    # response and request context wraps everything (including CORS failures).
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.enable_hsts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        # Browsers reject wildcard origins on credentialed requests, so pairing
        # the two silently breaks CORS while looking permissive. Credentials are
        # only enabled when an explicit origin allowlist is configured.
        allow_credentials=not allow_all_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=3600,
    )
    app.add_middleware(RequestContextMiddleware)

    if allow_all_origins:
        logger.warning(
            "CORS_ORIGINS is '*' — credentialed cross-origin requests are disabled. "
            "Set an explicit origin list for production."
        )

    @app.exception_handler(DataUnavailable)
    async def _data_unavailable(_: Request, exc: DataUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": f"Data unavailable: {exc}"})

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Traceback is logged by RequestContextMiddleware; clients get JSON, not text.
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id_var.get()},
        )

    app.include_router(api_router)
    return app


app = create_app()
