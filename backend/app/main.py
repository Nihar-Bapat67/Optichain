"""Application entry point.

Routes live in `app/api/routes/`; this module only wires the application
together: logging, middleware, artifact loading and router registration.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.router import api_router
from app.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.state import registry
from app.services import artifacts

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

    yield

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

    app.include_router(api_router)
    return app


app = create_app()
