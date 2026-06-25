"""
ML model schemas.

Defines request and response schemas for ML model registration
and retrieval operations. Model training happens offline — these
schemas represent the metadata envelope around an already-trained
artifact, not the training process itself.
"""

from datetime import datetime
from typing import Any
import json

from pydantic import BaseModel, Field, field_validator


class MLModelCreate(BaseModel):
    """
    Schema for registering a new ML model.

    Used by superuser admin endpoints only. The caller provides
    metadata about an already-trained, serialized model artifact.
    Status is always set to 'trained' by CRUD — never provided here.
    created_by_id is injected from the authenticated user by the
    route — never provided by the caller. tier is not accepted here —
    the CRUD layer always registers with tier="standard" (single-tier
    system; the column persists for forward compatibility).
    """

    # Human-readable model name
    name: str = Field(
        min_length=2,
        max_length=255,
    )

    # Algorithm class (e.g. "IsolationForest", "RandomForest")
    model_type: str = Field(
        min_length=2,
        max_length=100,
    )

    # Inference task this model performs (e.g. "anomaly_detection", "failure_prediction")
    task: str = Field(
        min_length=2,
        max_length=100,
    )

    # Asset type this model serves — scopes the model to a class of equipment
    asset_type_id: int

    # Incremental version number — starts at 1, incremented on each retrain
    version: int

    # Filesystem path to the serialized .joblib artifact
    artifact_path: str = Field(
        min_length=1,
        max_length=500,
    )

    # Ordered list of feature names the model was trained on
    feature_names: list[str]

    # Whether the model was trained to handle missing sensor inputs
    supports_sparse_features: bool

    # Number of training samples used — training provenance record
    training_samples: int

    # Hyperparameter dict — structure varies by model_type, validated by training pipeline
    hyperparameters: dict[str, Any]

    # Evaluation metrics from training (e.g. {"f1": 0.91, "auc": 0.94})
    metrics: dict[str, Any]

    # When the model was actually trained — provided by caller, not inferred from now()
    trained_at: datetime


class MLModelResponse(BaseModel):
    """
    Schema for ML model responses.

    Returned by admin listing and lookup endpoints. Includes all
    caller-provided metadata plus system-set fields: id, status,
    lifecycle timestamps, and the registering superuser's id.
    """

    # Model identifier
    id: int

    # Human-readable model name
    name: str

    # Algorithm class
    model_type: str

    # Inference task
    task: str

    # Asset type this model serves
    asset_type_id: int

    # Subscription tier
    tier: str

    # Incremental version number
    version: int

    # Lifecycle status — "untrained", "training", "trained", "deployed", "retired"
    status: str

    # Filesystem path to the serialized artifact
    artifact_path: str

    # Ordered list of feature names
    feature_names: list[str]

    # Sparse feature support flag
    supports_sparse_features: bool

    # Training sample count
    training_samples: int

    # Hyperparameters — untyped, varies by algorithm
    hyperparameters: dict

    # Evaluation metrics — untyped, varies by algorithm
    metrics: dict

    # When the model was trained (offline, before registration)
    trained_at: datetime

    # When the model was promoted to deployed status — None until deployed
    deployed_at: datetime | None

    # When this record was created in the system
    created_at: datetime

    # Superuser who registered this model
    created_by_id: int

    model_config = {"from_attributes": True}


class MLPredictionResponse(BaseModel):
    """
    Schema for ML prediction responses.

    Returned by inference endpoints. Represents a single model
    prediction for one asset and task at a point in time.

    feature_values is excluded from the response — it is a large
    internal artifact used for explainability and drift detection,
    not needed by the frontend dashboard.
    """

    id: int
    model_id: int
    asset_id: int
    timestamp: datetime
    prediction_type: str
    score: float
    confidence: float
    risk_level: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MLAnomalyEventResponse(BaseModel):
    """
    Schema for anomaly event responses.

    Returned by the open anomalies endpoint. Represents an
    unresolved anomaly alert for an asset.

    affected_metrics is stored as a JSON string in the database —
    the validator parses it automatically on serialization so the
    caller always receives a clean list.
    """

    id: int
    asset_id: int
    model_id: int
    timestamp: datetime
    anomaly_score: float
    severity: str
    affected_metrics: list[str]
    resolved_at: datetime | None
    created_at: datetime

    @field_validator("affected_metrics", mode="before")
    @classmethod
    def parse_affected_metrics(cls, v: Any) -> list[str]:
        """
        Parse affected_metrics from JSON string to list.

        The ORM stores this field as TEXT (json.dumps'd list).
        Pydantic receives the raw string — this validator converts
        it to a proper list before field assignment.

        Args:
            v: Raw field value from ORM — either a JSON string,
               an already-parsed list, or None.

        Returns:
            list[str]: Parsed metric names, empty list if None.
        """
        if isinstance(v, str):
            return json.loads(v)
        return v or []

    model_config = {"from_attributes": True}