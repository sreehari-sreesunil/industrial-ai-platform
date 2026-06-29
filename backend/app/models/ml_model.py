"""
MLModel ORM model.
Defines the ML model registry entity and its relationships.
"""
from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from app.db.base_class import Base


class MLModel(Base):
    """
    ML model registry entity.
    Represents a trained or untrained ML model owned and maintained by NexusIQ.
    Models are scoped to asset_type — never to a specific customer asset.
    One model serves all customers with the same asset type and subscription tier.
    """

    __tablename__ = "ml_models"

    # Primary key
    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    # Human-readable model name
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Algorithm family this model uses
    # Values: 'isolation_forest' | 'xgboost' | 'random_forest' | 'one_class_svm' | 'lstm'
    model_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # What this model is trained to do
    # Values: 'anomaly_detection' | 'failure_prediction'
    task: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Scoped to asset type — NULL means universal model across all asset types
    asset_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("asset_types.id"),
        nullable=True,
    )

    # Subscription tier this model belongs to
    # Values: 'standard' | 'professional' | 'enterprise'
    tier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="standard",
        server_default="standard",
    )

    # Incremented each time this model is retrained
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    # Lifecycle state machine
    # Values: 'untrained' | 'training' | 'trained' | 'deployed' | 'retired'
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="untrained",
        server_default="untrained",
    )

    # Filesystem path to the serialized .joblib or .pt artifact
    artifact_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # JSON list of feature names this model was trained on
    # Example: '["temperature_value", "temperature_rolling_mean_10"]'
    # Deserialized via json.loads() in the service layer — never queried by DB
    feature_names: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Whether this model handles assets with partial sensor coverage
    supports_sparse_features: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="TRUE",
    )

    # Number of training samples used to fit this model
    training_samples: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # JSON dict of hyperparameters used during training
    # Example: '{"n_estimators": 100, "contamination": 0.05}'
    # Deserialized via json.loads() in the service layer — never queried by DB
    hyperparameters: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # JSON dict of evaluation metrics recorded after training
    # Example: '{"accuracy": 0.94, "f1": 0.91}'
    # Deserialized via json.loads() in the service layer — never queried by DB
    metrics: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Lifecycle timestamps
    trained_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deployed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="NOW()",
    )

    # Internal NexusIQ admin who registered this model
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    # --- Relationships ---------------------------------------------------

    # Asset type this model is scoped to (unidirectional — Option B)
    asset_type = relationship(
        "AssetType",
    )

    # Admin user who created this model (unidirectional — Option B)
    created_by = relationship(
        "User",
    )

    # Inference history for this model (bidirectional)
    predictions = relationship(
        "MLPrediction",
        back_populates="model",
    )

    # Anomaly events detected by this model (bidirectional)
    anomaly_events = relationship(
        "MLAnomalyEvent",
        back_populates="model",
    )