from __future__ import annotations

import json
import hashlib
from typing import Any

import joblib

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

TARGET_COLS = [
    "lift_6h",
    "lift_24h",
    "lift_48h",
    "lift_72h",
    "lift_96h",
    "peak_lift_pct",
    "decay_lambda",
]

QUANTILES = (0.1, 0.5, 0.9)


def try_load_model1() -> tuple[Any | None, list[str] | None, list[str]]:
    msgs: list[str] = []
    model = None
    feats: list[str] | None = None
    mp = settings.best_model_path()
    fp = settings.feature_cols_path()

    if not mp.is_file():
        msgs.append(f"Missing MODEL1 artifact: {mp}")
        logger.warning("MODEL1 artifact missing: %s", mp)
        return None, None, msgs
    if not fp.is_file():
        msgs.append(f"Missing feature list: {fp}")
        logger.warning("MODEL1 feature list missing: %s", fp)
        return None, None, msgs

    try:
        model = joblib.load(mp)
        feats = list(joblib.load(fp))
    except ModuleNotFoundError as e:
        msgs.append(f"MODEL1 load failed — install missing lib (e.g. catboost if trained there): {e}")
        logger.error("MODEL1 load failed, missing dependency: %s", e)
        return None, None, msgs
    except Exception as e:
        msgs.append(f"Failed to load MODEL1: {e}")
        logger.exception("Failed to load MODEL1 from %s", mp)
        return None, None, msgs

    logger.info("MODEL1 loaded from %s (%d features)", mp, len(feats))
    return model, feats, msgs


def try_load_model2_bundle() -> tuple[dict[str, Any], dict[str, list[str]], list[str]]:
    """Returns (models_by_target, features_by_target, messages)."""
    msgs: list[str] = []
    models: dict[str, Any] = {}
    feat_map: dict[str, list[str]] = {}

    root = settings.root() / settings.influencer_model_dir
    if not root.is_dir():
        msgs.append(f"Missing influencer model dir: {root}")
        logger.warning("MODEL2 directory missing: %s", root)
        return models, feat_map, msgs

    for target in TARGET_COLS:
        pkl = root / f"{target}_best.pkl"
        js = root / f"{target}_features.json"
        if not pkl.is_file() or not js.is_file():
            logger.debug("MODEL2 target %s not present, skipping", target)
            continue
        try:
            models[target] = joblib.load(pkl)
            with open(js, encoding="utf-8") as f:
                feat_map[target] = json.load(f)
        except ModuleNotFoundError as e:
            msgs.append(f"MODEL2 {target}: missing dependency (e.g. pip install catboost): {e}")
            logger.error("MODEL2 %s failed, missing dependency: %s", target, e)
        except Exception as e:
            msgs.append(f"MODEL2 {target}: {e}")
            logger.exception("MODEL2 %s failed to load from %s", target, pkl)

    logger.info("MODEL2 bundle loaded: %d/%d targets", len(models), len(TARGET_COLS))
    return models, feat_map, msgs


def try_load_conti_model() -> tuple[Any | None, list[str] | None, list[str]]:
    """Loads the city-growth (conti) model and its features."""
    msgs: list[str] = []
    mp = settings.conti_model_path()
    fp = settings.conti_features_path()

    if not mp.is_file():
        msgs.append(f"Missing CONTI model artifact: {mp}")
        logger.warning("CONTI artifact missing: %s", mp)
        return None, None, msgs

    try:
        model = joblib.load(mp)
        feats = None
        if fp.is_file():
            with open(fp, encoding="utf-8") as f:
                feats = json.load(f)
        else:
            logger.warning("CONTI feature list missing: %s", fp)
        logger.info("CONTI model loaded from %s", mp)
        return model, feats, msgs
    except Exception as e:
        msgs.append(f"Failed to load CONTI model: {e}")
        logger.exception("Failed to load CONTI model from %s", mp)
        return None, None, msgs


def try_load_quantile_models() -> tuple[dict[float, Any], list[str] | None, dict[str, Any] | None, list[str]]:
    """Load a compatible P10/P50/P90 model set, or return an unavailable set."""
    msgs: list[str] = []
    root = settings.quantile_model_dir_path()
    manifest_path = settings.quantile_manifest_path()
    if not root.is_dir() or not manifest_path.is_file():
        logger.warning("Optional quantile artifacts unavailable: %s", root)
        return {}, None, None, []

    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        if manifest.get("model_type") != "lightgbm_quantile":
            raise ValueError("unexpected quantile model type")
        features = list(manifest["feature_names"])
        entries = manifest["models"]
        models: dict[float, Any] = {}
        for alpha in QUANTILES:
            entry = entries[str(alpha)]
            path = root / entry["filename"]
            if not path.is_file():
                raise FileNotFoundError(path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != entry["sha256"]:
                raise ValueError(f"checksum mismatch for alpha={alpha}")
            models[alpha] = joblib.load(path)
            expected_features = getattr(models[alpha], "n_features_in_", len(features))
            if expected_features != len(features):
                raise ValueError(f"feature count mismatch for alpha={alpha}")
        if set(models) != set(QUANTILES):
            raise ValueError("incomplete quantile model set")
        logger.info("Quantile models loaded from %s", root)
        return models, features, manifest, msgs
    except (KeyError, TypeError, ValueError, OSError, ModuleNotFoundError) as exc:
        message = f"Quantile artifacts unavailable: {exc}"
        msgs.append(message)
        logger.exception(message)
        return {}, None, None, msgs
