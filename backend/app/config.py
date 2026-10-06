"""Application settings.

Every path the API reads is derived here, so relocating data or model
directories is a configuration change rather than a code change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _default_project_root() -> Path:
    """Repository root, resolved relative to this file (backend/app/config.py)."""
    return Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Service identity ──────────────────────────────────────────────────
    app_name: str = "Supply Chain Analytics API"
    app_version: str = "1.0.0"
    log_level: LogLevel = "INFO"
    # Only enable behind TLS; sending HSTS over plain HTTP can lock a browser
    # out of localhost for a year.
    enable_hsts: bool = False

    # ── Filesystem layout ─────────────────────────────────────────────────
    project_root: Path | None = None
    data_dir: str = "ws_demand_dataset"
    ws_model_dir: str = "ws_model"
    ml_ready_file: str = "ml_ready_data.csv"
    influencer_model_dir: str = "models"
    features_engineered_file: str = "features_engineered.csv"
    analytics_dir: str = "analytics"
    case_study_data_dir: str = "data"
    conti_model_dir: str = "models"

    # ── Database ──────────────────────────────────────────────────────────
    # Any SQLAlchemy URL. Empty → SQLite file at <root>/backend/var/optichain.sqlite3.
    database_url: str = ""
    # Build the database from the CSV sources at startup when it is empty, and
    # re-ingest when a source file's checksum no longer matches the last load.
    db_auto_init: bool = True
    db_auto_refresh: bool = True
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_backup_keep: int = 5
    db_backup_dir: str = ""
    # How often (seconds) the in-process cache re-checks the data version.
    cache_version_ttl_s: float = 5.0

    # ── HTTP ──────────────────────────────────────────────────────────────
    cors_origins: str = "*"

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalise_log_level(cls, value: object) -> object:
        """Accept lower-case values such as `debug` from the environment."""
        return value.upper() if isinstance(value, str) else value

    @field_validator("cors_origins")
    @classmethod
    def _validate_cors_origins(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "CORS_ORIGINS must not be empty — use '*' or a comma-separated origin list."
            )
        return value

    # ── Derived paths ─────────────────────────────────────────────────────
    def root(self) -> Path:
        if self.project_root is not None:
            return Path(self.project_root).resolve()
        return _default_project_root()

    def ml_ready_path(self) -> Path:
        return self.root() / self.data_dir / self.ml_ready_file

    def demand_predictions_path(self) -> Path:
        return self.root() / self.analytics_dir / "demand_with_predictions.csv"

    def sales_timeseries_path(self) -> Path:
        return self.root() / self.analytics_dir / "sales_timeseries.csv"

    def inventory_path(self) -> Path:
        return self.root() / self.case_study_data_dir / "inventory.csv"

    def signals_path(self) -> Path:
        return self.root() / self.case_study_data_dir / "signals.csv"

    def best_model_path(self) -> Path:
        return self.root() / self.ws_model_dir / "best_model.pkl"

    def feature_cols_path(self) -> Path:
        return self.root() / self.ws_model_dir / "feature_cols.pkl"

    def features_engineered_path(self) -> Path:
        return self.root() / self.features_engineered_file

    def influencer_metrics_path(self) -> Path:
        return self.root() / self.analytics_dir / "influencer_metrics.json"

    def influencer_sample_path(self) -> Path:
        return self.root() / self.analytics_dir / "influencer_sample.csv"

    def conti_model_path(self) -> Path:
        return self.root() / self.conti_model_dir / "conti_model.pkl"

    def conti_features_path(self) -> Path:
        return self.root() / self.conti_model_dir / "conti_features.json"

    def var_dir(self) -> Path:
        return self.root() / "backend" / "var"

    def sqlite_path(self) -> Path:
        return self.var_dir() / "optichain.sqlite3"

    def resolved_database_url(self) -> str:
        if self.database_url.strip():
            return self.database_url.strip()
        return f"sqlite:///{self.sqlite_path().as_posix()}"

    def backup_dir(self) -> Path:
        if self.db_backup_dir.strip():
            return Path(self.db_backup_dir.strip())
        return self.var_dir() / "backups"

    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
