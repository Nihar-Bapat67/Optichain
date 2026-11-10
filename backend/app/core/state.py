"""In-process registry for loaded ML artifacts.

Replaces the previous untyped `_state: dict[str, Any]` global with a typed
container. The artifacts themselves and the way they are loaded are unchanged;
this only gives them names and types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelRegistry:
    """Holds every artifact loaded once at application startup."""

    # MODEL1 — baseline demand.
    model1: Any | None = None
    model1_features: list[str] | None = None

    # MODEL2 — influencer uplift bundle, keyed by target name.
    model2: dict[str, Any] = field(default_factory=dict)
    model2_features: dict[str, list[str]] = field(default_factory=dict)

    # MODEL3 / "conti" — city growth.
    conti: Any | None = None
    conti_features: list[str] | None = None

    # Optional probabilistic daily-demand models, keyed by quantile.
    quantile_models: dict[float, Any] = field(default_factory=dict)
    quantile_features: list[str] | None = None
    quantile_manifest: dict[str, Any] | None = None

    # Human-readable notes gathered while loading, surfaced by /api/health.
    load_messages: list[str] = field(default_factory=list)

    @property
    def model1_loaded(self) -> bool:
        return self.model1 is not None and self.model1_features is not None

    @property
    def conti_loaded(self) -> bool:
        return self.conti is not None

    @property
    def model2_targets_loaded(self) -> int:
        return len(self.model2)

    def as_agent_payload(self) -> dict[str, Any]:
        """Build the dict shape `run_forecast_agent` expects.

        The keys must stay exactly as-is — the forecast agent reads them by name.
        """
        return {
            "model1": self.model1,
            "model1_feats": self.model1_features,
            "model2_bundle": self.model2,
            "model2_feats": self.model2_features,
            "conti": self.conti,
            "conti_feats": self.conti_features,
        }

    @property
    def quantiles_loaded(self) -> bool:
        return set(self.quantile_models) == {0.1, 0.5, 0.9} and self.quantile_features is not None


# Single instance shared by the app; populated during the lifespan startup hook.
registry = ModelRegistry()
