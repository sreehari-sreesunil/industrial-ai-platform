"""add_ml_tables

Revision ID: f1g2h3i4j5k6
Revises: d2e3f4a5b6c7
Create Date: 2026-06-06

What this migration does:
    1. Extends existing tables (users, organizations) with ML-related fields
    2. Creates the ML model registry (ml_models)
    3. Creates inference history log (ml_predictions)
    4. Creates anomaly event store (ml_anomaly_events)
    5. Creates health score time-series (ml_asset_health)
    6. Creates asset baseline profiles (ml_asset_baselines)
    7. Adds performance indexes on telemetry_records and all new ML tables

Dependency order (upgrade):
    users → organizations → ml_models → ml_predictions
                                      → ml_anomaly_events
                                      → ml_asset_health
                                      → ml_asset_baselines

Dependency order (downgrade — exact reverse):
    ml_asset_baselines → ml_asset_health → ml_anomaly_events
    → ml_predictions → ml_models → organizations → users
"""

from alembic import op
import sqlalchemy as sa


# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "f1g2h3i4j5k6"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:

    # ------------------------------------------------------------------
    # Step 1 — Extend users table
    #
    # Why is_superuser here:
    #   Model management (training, deployment, retirement) is an internal
    #   NexusIQ operation. Customers never train or deploy models — they
    #   only call inference endpoints. We gate admin routes on this flag.
    #   Full RBAC replaces this in a later sprint.
    # ------------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )

    # ------------------------------------------------------------------
    # Step 2 — Extend organizations table
    #
    # Why ml_tier here:
    #   Each organization subscribes to a model tier that determines
    #   which model is loaded during inference:
    #     standard     → Isolation Forest / lightweight classifiers
    #     professional → XGBoost / Random Forest
    #     enterprise   → LSTM / Deep Learning models
    #   Billing integration will enforce this in a later sprint.
    #   Default is 'standard' so existing organizations are unaffected.
    # ------------------------------------------------------------------
    op.add_column(
        "organizations",
        sa.Column(
            "ml_tier",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'standard'"),
        ),
    )

    # ------------------------------------------------------------------
    # Step 3 — Create ml_models (model registry)
    #
    # Why asset_type_id and NOT asset_id:
    #   NexusIQ trains one model per asset_type per task per tier.
    #   A Compressor anomaly detection model serves ALL customer
    #   compressors — it is not specific to any single customer's asset.
    #   Customer-level adaptation happens in the baseline layer
    #   (ml_asset_baselines), not by training separate models per asset.
    #
    # Why TEXT for feature_names, hyperparameters, metrics:
    #   These fields are opaque blobs to the database. No SQL query will
    #   ever filter inside them. Python deserializes them via json.loads()
    #   in the service layer. JSONB would add complexity with no benefit.
    #
    # Why VARCHAR for status and not a PostgreSQL ENUM:
    #   PostgreSQL ENUMs require ALTER TYPE to add new values, which can
    #   lock the table. VARCHAR + application-level validation via Pydantic
    #   gives identical safety with zero migration risk.
    #   Valid values: 'untrained' | 'training' | 'trained' | 'deployed' | 'retired'
    #
    # Why tier on ml_models:
    #   A single asset_type may have multiple deployed models — one per
    #   tier. The inference layer resolves: asset_type + task + tier → model.
    # ------------------------------------------------------------------
    op.create_table(
        "ml_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),

        # What kind of algorithm this model uses
        # Values: 'isolation_forest' | 'xgboost' | 'random_forest' | 'one_class_svm' | 'lstm'
        sa.Column("model_type", sa.String(100), nullable=False),

        # What the model is trained to do
        # Values: 'anomaly_detection' | 'failure_prediction'
        sa.Column("task", sa.String(100), nullable=False),

        # Scoped to asset type — never to a specific customer asset
        sa.Column(
            "asset_type_id",
            sa.Integer(),
            sa.ForeignKey("asset_types.id"),
            nullable=True,   # NULL = universal model across all asset types
        ),

        # Which subscription tier this model belongs to
        # Values: 'standard' | 'professional' | 'enterprise'
        sa.Column("tier", sa.String(50), nullable=False, server_default=sa.text("'standard'")),

        # Incremented each time this model is retrained
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),

        # Lifecycle state machine
        sa.Column("status", sa.String(50), server_default=sa.text("'untrained'")),

        # Filesystem path to the serialized .joblib or .pt file
        sa.Column("artifact_path", sa.String(500), nullable=True),

        # JSON list of feature names this model was trained on
        # Example: '["temperature_value", "temperature_rolling_mean_10", ...]'
        sa.Column("feature_names", sa.Text(), nullable=True),

        # Whether this model was trained with missingness indicator features
        # TRUE means it gracefully handles assets with partial sensor coverage
        sa.Column(
            "supports_sparse_features",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),

        sa.Column("training_samples", sa.Integer(), nullable=True),

        # JSON dict of model hyperparameters
        # Example: '{"n_estimators": 100, "contamination": 0.05}'
        sa.Column("hyperparameters", sa.Text(), nullable=True),

        # JSON dict of evaluation metrics
        # Example: '{"accuracy": 0.94, "f1": 0.91}'
        sa.Column("metrics", sa.Text(), nullable=True),

        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),

        # Internal NexusIQ admin who registered/trained this model
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )

    # ------------------------------------------------------------------
    # Step 4 — Create ml_predictions (inference history)
    #
    # Why store every prediction:
    #   Without a prediction log you cannot detect model drift. Drift
    #   detection (PSI, EvidentlyAI) compares the distribution of recent
    #   predictions against historical predictions. No log = no drift.
    #
    # Why feature_values and explanation as TEXT:
    #   These are forensic fields — never queried by the database,
    #   only read whole for post-incident analysis. TEXT is correct.
    #
    # Why confidence is nullable:
    #   Not all algorithms produce calibrated confidence scores.
    #   Isolation Forest returns a decision function score, not a
    #   probability. We store NULL rather than a misleading number.
    # ------------------------------------------------------------------
    op.create_table(
        "ml_predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "model_id",
            sa.Integer(),
            sa.ForeignKey("ml_models.id"),
            nullable=True,   # NULL for rule-based predictions (no model involved)
        ),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),

        # What kind of prediction this row represents
        # Values: 'failure_probability' | 'anomaly_score' | 'health_score'
        sa.Column("prediction_type", sa.String(100), nullable=False),

        # The primary output value
        # Range: 0-1 for probabilities, 0-100 for health scores
        sa.Column("score", sa.Float(), nullable=False),

        # How confident the model is in this prediction (nullable — see note above)
        sa.Column("confidence", sa.Float(), nullable=True),

        # Human-readable risk classification derived from score
        # Values: 'low' | 'medium' | 'high' | 'critical'
        sa.Column("risk_level", sa.String(50), nullable=True),

        # JSON snapshot of the feature vector used for this prediction
        # Critical for reproducing and explaining predictions post-incident
        sa.Column("feature_values", sa.Text(), nullable=True),

        # JSON dict of feature importances at inference time
        # Example: '{"temperature_zscore": 0.34, "vibration_rolling_std": 0.28}'
        sa.Column("explanation", sa.Text(), nullable=True),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "ix_ml_predictions_asset_timestamp",
        "ml_predictions",
        ["asset_id", sa.text("timestamp DESC")],
    )

    # ------------------------------------------------------------------
    # Step 5 — Create ml_anomaly_events (anomaly event store)
    #
    # Why a separate table from ml_predictions:
    #   ml_predictions is a log of every inference call — including normal
    #   results. ml_anomaly_events only stores records where an anomaly
    #   was actually detected (score above threshold). This table is
    #   operationally significant — it has a resolution workflow, notes,
    #   and is the source for alert generation and dashboards.
    #
    # Why payload_snapshot:
    #   Stores the raw telemetry values at the exact moment of detection.
    #   Without this, post-incident investigation cannot reconstruct what
    #   the sensors were reading when the anomaly fired.
    #
    # Why resolved_at / resolved_by_id:
    #   Anomaly events have a lifecycle: detected → investigated → resolved.
    #   Unresolved events = WHERE resolved_at IS NULL. This is the standard
    #   pattern for operational event tracking systems.
    # ------------------------------------------------------------------
    op.create_table(
        "ml_anomaly_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id"),
            nullable=False,
        ),
        sa.Column(
            "model_id",
            sa.Integer(),
            sa.ForeignKey("ml_models.id"),
            nullable=True,   # NULL if detected by rule-based health scoring
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anomaly_score", sa.Float(), nullable=False),

        # Values: 'low' | 'medium' | 'high' | 'critical'
        sa.Column("severity", sa.String(50), nullable=False),

        # JSON list of which metrics triggered the anomaly
        # Example: '["temperature", "vibration"]'
        sa.Column("affected_metrics", sa.Text(), nullable=True),

        # Raw telemetry payload at detection time — forensic record
        sa.Column("payload_snapshot", sa.Text(), nullable=True),

        # Free-text field for operator investigation notes
        sa.Column("notes", sa.Text(), nullable=True),

        # Resolution tracking — NULL means event is still open
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "ix_ml_anomaly_events_asset_timestamp",
        "ml_anomaly_events",
        ["asset_id", sa.text("timestamp DESC")],
    )

    # ------------------------------------------------------------------
    # Step 6 — Create ml_asset_health (health score time-series)
    #
    # Why append-only:
    #   Health scores are never updated — a new row is inserted each time
    #   health is computed. This gives you a complete historical trend for
    #   charts and deterioration analysis. Consequence: this table grows
    #   without bound. Partitioning or TTL policy added in a later sprint.
    #
    # Why store health_category alongside health_score:
    #   health_category is derivable from health_score, but storing it
    #   makes queries cleaner: WHERE health_category = 'critical' rather
    #   than WHERE health_score < 20. Category logic lives in one place
    #   (service layer) and is not re-derived at query time.
    #
    # Why rul_days is nullable:
    #   Remaining Useful Life is only computable when there is a measurable
    #   deterioration trend. A stable healthy asset has no meaningful RUL.
    # ------------------------------------------------------------------
    op.create_table(
        "ml_asset_health",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),

        # 0 = failed, 100 = perfect health
        sa.Column("health_score", sa.Float(), nullable=False),

        # Values: 'excellent' | 'good' | 'fair' | 'poor' | 'critical'
        sa.Column("health_category", sa.String(50), nullable=False),

        # Rule-based failure probability proxy (0-1)
        sa.Column("failure_probability", sa.Float(), nullable=True),

        # Estimated days until failure — NULL if trend is stable or improving
        sa.Column("rul_days", sa.Integer(), nullable=True),

        # JSON list of human-readable factor descriptions
        # Example: '["Temperature at 91% of max", "Vibration trending up 15%"]'
        sa.Column("contributing_factors", sa.Text(), nullable=True),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "ix_ml_asset_health_asset_timestamp",
        "ml_asset_health",
        ["asset_id", sa.text("timestamp DESC")],
    )

    # ------------------------------------------------------------------
    # Step 7 — Create ml_asset_baselines (per-asset learned behavior)
    #
    # Why this table exists:
    #   The same asset type (e.g. Compressor) can operate at completely
    #   different conditions across facilities. A global model cannot know
    #   that Facility A's compressor normally runs at 60°C while Facility
    #   B's runs at 95°C. This table stores the learned "normal envelope"
    #   per asset per metric so inference can be locally calibrated.
    #
    # Why one row per asset per metric (not one row per asset):
    #   Each metric has independent statistical properties. Storing them
    #   separately allows partial updates (update temperature baseline
    #   without touching vibration baseline) and clean per-metric queries.
    #
    # Why is_mature:
    #   A baseline computed from 10 readings is unreliable. is_mature = TRUE
    #   only after sufficient samples (configurable threshold, e.g. 100+
    #   readings over 7+ days). While immature, predictions are returned
    #   with a low_confidence flag. Baseline learning logic implemented
    #   in Week 3.
    # ------------------------------------------------------------------
    op.create_table(
        "ml_asset_baselines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id"),
            nullable=False,
        ),

        # Matches the metric name in telemetry_records.values JSONB
        # Example: 'temperature', 'vibration', 'rpm'
        sa.Column("metric_name", sa.String(100), nullable=False),

        # Statistical summary of normal operating behavior
        sa.Column("baseline_mean", sa.Float(), nullable=True),
        sa.Column("baseline_std", sa.Float(), nullable=True),
        sa.Column("baseline_min", sa.Float(), nullable=True),
        sa.Column("baseline_max", sa.Float(), nullable=True),
        sa.Column("percentile_95", sa.Float(), nullable=True),

        # How many telemetry records contributed to this baseline
        sa.Column("samples_count", sa.Integer(), server_default=sa.text("0")),

        # The time window used to build this baseline
        sa.Column("learning_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("learning_period_end", sa.DateTime(timezone=True), nullable=True),

        # FALSE until enough samples collected for reliable statistics
        sa.Column(
            "is_mature",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "ix_ml_asset_baselines_asset_metric",
        "ml_asset_baselines",
        ["asset_id", "metric_name"],
        unique=True,   # One baseline row per asset per metric
    )

    # ------------------------------------------------------------------
    # Step 8 — Telemetry performance indexes
    #
    # Why these indexes matter:
    #   Feature engineering fetches the last N telemetry records for an
    #   asset ordered by timestamp. Without an index on (asset_id, timestamp),
    #   every ML inference call is a full table scan. As telemetry_records
    #   grows (millions of rows), this becomes the single biggest
    #   performance bottleneck in the entire ML system.
    #
    # Why DESC on timestamp:
    #   Feature engineering always fetches the MOST RECENT N records.
    #   DESC ordering means PostgreSQL reads from the newest end of the
    #   index — the most efficient access pattern for this query.
    # ------------------------------------------------------------------
    op.create_index(
        "ix_telemetry_asset_timestamp",
        "telemetry_records",
        ["asset_id", sa.text("timestamp DESC")],
    )

    op.create_index(
        "ix_telemetry_timestamp",
        "telemetry_records",
        [sa.text("timestamp DESC")],
    )


# ---------------------------------------------------------------------------
# downgrade — exact inverse of upgrade, in reverse order
# ---------------------------------------------------------------------------

def downgrade() -> None:

    # Telemetry indexes
    op.drop_index("ix_telemetry_timestamp", table_name="telemetry_records")
    op.drop_index("ix_telemetry_asset_timestamp", table_name="telemetry_records")

    # ml_asset_baselines
    op.drop_index("ix_ml_asset_baselines_asset_metric", table_name="ml_asset_baselines")
    op.drop_table("ml_asset_baselines")

    # ml_asset_health
    op.drop_index("ix_ml_asset_health_asset_timestamp", table_name="ml_asset_health")
    op.drop_table("ml_asset_health")

    # ml_anomaly_events
    op.drop_index("ix_ml_anomaly_events_asset_timestamp", table_name="ml_anomaly_events")
    op.drop_table("ml_anomaly_events")

    # ml_predictions
    op.drop_index("ix_ml_predictions_asset_timestamp", table_name="ml_predictions")
    op.drop_table("ml_predictions")

    # ml_models
    op.drop_table("ml_models")

    # Organization and user extensions
    op.drop_column("organizations", "ml_tier")
    op.drop_column("users", "is_superuser")