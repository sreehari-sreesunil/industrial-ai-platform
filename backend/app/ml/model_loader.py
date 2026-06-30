"""
ML model loader.

Handles loading serialized model artifacts from disk and caching
them in memory for the lifetime of the process. Prevents repeated
disk reads on hot inference paths.

Cache is process-local — each worker process maintains its own
in-memory registry. When a new model is deployed, call
invalidate_model() to evict the stale entry so the new artifact
is loaded on the next inference call without a process restart.
"""

import logging
from pathlib import Path
from typing import Any

import joblib

logger = logging.getLogger(__name__)

# Process-local model registry — keyed by model_id
# Populated lazily on first inference call per model
_model_cache: dict[int, Any] = {}


def load_model(model_id: int, artifact_path: str) -> Any:
    """
    Load a serialized model artifact and return the deserialized object.

    On first call for a given model_id the artifact is read from disk
    and stored in the process-local cache. Subsequent calls return the
    cached object directly without touching disk.

    Args:
        model_id: ML model identifier — used as the cache key.
        artifact_path: URI-style path to the serialized .joblib file
            (e.g. local://artifacts/model.joblib). Resolved via
            _resolve_local_path() before any filesystem access.

    Returns:
        Any: Deserialized sklearn, XGBoost, or compatible model object.

    Raises:
        FileNotFoundError: If the artifact file does not exist at the path.
        RuntimeError: If the artifact cannot be deserialized.
    """

    # Return cached object if already loaded for this model
    if model_id in _model_cache:
        logger.debug("Model %d served from cache", model_id)
        return _model_cache[model_id]

    # Resolve the local:// URI to a real filesystem path
    path = _resolve_local_path(artifact_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Model artifact not found at path: {artifact_path}. "
            f"Ensure the artifact was deployed to the expected location."
        )

    # Load artifact from disk and populate cache
    try:
        logger.info("Loading model %d from disk: %s", model_id, artifact_path)
        model = joblib.load(path)
        _model_cache[model_id] = model
        logger.info("Model %d loaded and cached successfully", model_id)
        return model

    except Exception as exc:
        raise RuntimeError(
            f"Failed to deserialize model artifact at {artifact_path}: {exc}"
        ) from exc


def invalidate_model(model_id: int) -> None:
    """
    Evict a model from the in-memory cache.

    Called by deploy_model_service when a new model version is deployed,
    ensuring the next inference call loads the fresh artifact from disk
    rather than serving predictions from the stale cached object.

    Safe to call even if the model is not currently cached — no error
    is raised when the key is absent.

    Args:
        model_id: ML model identifier to evict from cache.
    """

    if model_id in _model_cache:
        del _model_cache[model_id]
        logger.info("Model %d evicted from cache", model_id)
    else:
        logger.debug("Model %d was not in cache — nothing to invalidate", model_id)


def get_cached_model_ids() -> list[int]:
    """
    Return the IDs of all models currently held in the cache.

    Used for observability — admin endpoints or health checks can
    surface which models are warm in this process without exposing
    the cache dict directly.

    Returns:
        list[int]: Model IDs currently cached in this process.
    """

    return list(_model_cache.keys())

def _resolve_local_path(artifact_path: str) -> Path:
    """
    Resolve a local:// URI-style artifact path to a real filesystem Path.

    Mirrors scripts/training/registrar.py's _resolve_local_path() —
    the two functions must stay in agreement, since registrar.py writes
    these paths and this function reads them. Previously, load_model()
    had no URI-scheme handling at all (its own docstring said
    "artifact_path: Filesystem path", contradicting registrar.py's
    documented local:// scheme) — every real attempt to load a deployed
    model failed with FileNotFoundError, undiscovered until the first
    time a model was ever actually registered and inference attempted
    against it.

    Args:
        artifact_path: URI-style path (e.g. local://artifacts/model.joblib).

    Returns:
        Path: Resolved filesystem path.

    Raises:
        ValueError: If the URI scheme is not local://.
    """
    if not artifact_path.startswith("local://"):
        raise ValueError(
            f"Unsupported URI scheme in artifact_path: '{artifact_path}'. "
            f"Only local:// is supported."
        )
    relative_path = artifact_path.removeprefix("local://")
    backend_root = Path(__file__).parent.parent.parent
    return backend_root / relative_path