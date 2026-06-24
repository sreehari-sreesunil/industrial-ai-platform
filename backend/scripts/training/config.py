# scripts/training/config.py
"""
Training pipeline configuration.

Single source of truth for all training parameters.
No magic numbers exist anywhere else in the pipeline —
every constant is defined and documented here.

Structure:
    DataConfig      → synthetic data generation parameters
    FeatureConfig   → feature names and engineering settings
    CVConfig        → cross-validation fold configuration
    ModelConfig     → hyperparameters per algorithm
    EvalConfig      → evaluation benchmarks and pass/fail gates
    ArtifactConfig  → output paths and serialization settings
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OperatingEnvelope:
    """
    Normal operating range for a single sensor on a single asset type.

    Values represent the healthy population — 2σ band around the mean
    under normal load and environmental conditions.

    Attributes:
        mean:       Centre of the normal operating range.
        std:        Standard deviation under normal conditions.
        failure_threshold: Value at or beyond which the asset is in the
                    failure zone. Used to generate labeled failure data
                    and to set anomaly detection upper bounds.
    """
    mean: float
    std: float
    failure_threshold: float


@dataclass(frozen=True)
class AssetDataConfig:
    """
    Synthetic data generation parameters for one asset type.

    Attributes:
        total_records:      Total telemetry records to generate.
        normal_fraction:    Proportion of records in normal operation.
        degradation_fraction: Proportion in the degradation phase.
                            Failure fraction = 1 - normal - degradation.
        degradation_rate:   Per-record drift multiplier applied to sensor
                            means during the degradation phase.
        envelopes:          Normal operating envelope per sensor.
        random_seed:        Fixed seed for reproducibility.
    """
    total_records: int
    normal_fraction: float
    degradation_fraction: float
    degradation_rate: float
    envelopes: dict[str, OperatingEnvelope]
    random_seed: int = 42

    @property
    def failure_fraction(self) -> float:
        return 1.0 - self.normal_fraction - self.degradation_fraction

    @property
    def normal_records(self) -> int:
        return int(self.total_records * self.normal_fraction)

    @property
    def degradation_records(self) -> int:
        return int(self.total_records * self.degradation_fraction)

    @property
    def failure_records(self) -> int:
        return self.total_records - self.normal_records - self.degradation_records


# SYNTHETIC DATA ONLY — these envelopes generate training data before
# real telemetry exists. In production, replace with a query to
# ml_asset_baselines once baselines are mature (is_mature=True).
#
# Envelope values derived from Azure Predictive Maintenance dataset
# statistics (Kaggle, 100 machines, 876,099 hourly records, 2015).
# Failure thresholds set at mean + 3σ of the degradation phase,
# validated against labeled failure records in the dataset.
ASSET_DATA_CONFIGS: dict[str, AssetDataConfig] = {
    "compressor": AssetDataConfig(
        total_records=5000,
        normal_fraction=0.80,
        degradation_fraction=0.15,
        degradation_rate=0.04,
        envelopes={
            "voltage":   OperatingEnvelope(mean=175.0, std=14.0, failure_threshold=225.0),
            "rotation":  OperatingEnvelope(mean=490.0, std=28.0, failure_threshold=580.0),
            "pressure":  OperatingEnvelope(mean=105.0, std=8.5,  failure_threshold=138.0),
            "vibration": OperatingEnvelope(mean=42.0,  std=5.5,  failure_threshold=68.0),
        },
    ),
    "pump": AssetDataConfig(
        total_records=4000,
        normal_fraction=0.80,
        degradation_fraction=0.15,
        degradation_rate=0.035,
        envelopes={
            "voltage":   OperatingEnvelope(mean=160.0, std=13.0, failure_threshold=210.0),
            "rotation":  OperatingEnvelope(mean=440.0, std=25.0, failure_threshold=520.0),
            "pressure":  OperatingEnvelope(mean=95.0,  std=7.5,  failure_threshold=125.0),
            "vibration": OperatingEnvelope(mean=38.0,  std=5.0,  failure_threshold=62.0),
        },
    ),
    "motor": AssetDataConfig(
        total_records=4500,
        normal_fraction=0.80,
        degradation_fraction=0.15,
        degradation_rate=0.03,
        envelopes={
            "voltage":   OperatingEnvelope(mean=168.0, std=12.0, failure_threshold=215.0),
            "rotation":  OperatingEnvelope(mean=470.0, std=22.0, failure_threshold=545.0),
            "pressure":  OperatingEnvelope(mean=100.0, std=7.0,  failure_threshold=128.0),
            "vibration": OperatingEnvelope(mean=40.0,  std=4.8,  failure_threshold=60.0),
        },
    ),
}


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeatureConfig:
    """
    Feature engineering configuration.

    Defines which raw sensors are used and what derived features
    are built from them.

    The full feature vector per sensor is:
        {sensor}               → raw reading
        {sensor}_roll_mean_24  → 24-hour rolling mean (smoothed baseline)
        {sensor}_roll_std_24   → 24-hour rolling std (volatility —
                                 critical degradation signal; vibration
                                 becoming erratic precedes failure)
        {sensor}_rate_change   → difference from previous reading
                                 (instantaneous trend direction)

    Rolling and rate-of-change features are what give the model
    lead time — raw instantaneous values look identical whether
    a sensor has been stable for months or degrading for days.

    Attributes:
        sensors:          Raw sensor names matching telemetry payload keys.
        rolling_window:   Window size in records for rolling statistics.
                          24 records = 24 hours at hourly sample rate.
        use_rolling_mean: Include rolling mean feature.
        use_rolling_std:  Include rolling std feature.
        use_rate_change:  Include rate-of-change feature.
    """
    sensors: list[str]
    rolling_window: int = 24
    use_rolling_mean: bool = True
    use_rolling_std: bool = True
    use_rate_change: bool = True

    @property
    def feature_names(self) -> list[str]:
        """
        Return the ordered feature name list the model expects.

        Order must be stable — sklearn models are position-sensitive.
        """
        names = []
        for sensor in self.sensors:
            names.append(sensor)
            if self.use_rolling_mean:
                names.append(f"{sensor}_roll_mean_{self.rolling_window}")
            if self.use_rolling_std:
                names.append(f"{sensor}_roll_std_{self.rolling_window}")
            if self.use_rate_change:
                names.append(f"{sensor}_rate_change")
        return names


FEATURE_CONFIG = FeatureConfig(
    sensors=["voltage", "rotation", "pressure", "vibration"],
    rolling_window=24,
    use_rolling_mean=True,
    use_rolling_std=True,
    use_rate_change=True,
)

# Feature vector length: 4 sensors × 4 features = 16 features
# voltage,   voltage_roll_mean_24,   voltage_roll_std_24,   voltage_rate_change
# rotation,  rotation_roll_mean_24,  rotation_roll_std_24,  rotation_rate_change
# pressure,  pressure_roll_mean_24,  pressure_roll_std_24,  pressure_rate_change
# vibration, vibration_roll_mean_24, vibration_roll_std_24, vibration_rate_change


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CrossValidationConfig:
    """
    Time series cross-validation configuration.

    Uses sklearn TimeSeriesSplit — each fold's training set is
    strictly earlier in time than its validation set. This mirrors
    production deployment where the model always predicts the future.

    Attributes:
        n_splits:       Number of CV folds. 5 gives reliable estimates
                        without excessive compute on large datasets.
        gap:            Records to skip between train and val in each fold.
                        Prevents leakage when using lag features or
                        rolling windows. Set to FAILURE_HORIZON_HOURS
                        so no failure window straddles the split boundary.
        max_train_size: Maximum training records per fold. None = use all
                        available. Set if training data is very large and
                        recent data is more relevant than old data.
        test_size:      Validation records per fold. None = auto-computed
                        as total_records / (n_splits + 1).
    """
    n_splits: int = 5
    gap: int = 48           # matches FAILURE_HORIZON_HOURS in data_loader
    max_train_size: int | None = None
    test_size: int | None = None


CV_CONFIG = CrossValidationConfig()


# ---------------------------------------------------------------------------
# Model hyperparameters
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IsolationForestConfig:
    """
    IsolationForest hyperparameters.

    n_estimators:   Number of base estimators (trees).
                    100 is the standard starting point.
    contamination:  Expected proportion of anomalies in training data.
                    MUST match the actual positive rate in the dataset —
                    this is not a tunable knob, it's a statistical fact
                    about the data. Azure PM dataset has ~2% positive rate
                    (FAILURE_HORIZON_HOURS=24 window). Setting this too
                    high (e.g. 0.175) causes the model to flag far more
                    points as anomalous than actually exist, destroying
                    precision.
    max_samples:    Samples per tree. "auto" = min(256, n_samples).
    random_state:   Fixed for reproducibility.
    """
    n_estimators: int = 100
    contamination: float = 0.02   # matches actual ~2% positive rate in data
    max_samples: str = "auto"
    random_state: int = 42


@dataclass(frozen=True)
class RandomForestConfig:
    """
    RandomForest hyperparameters for failure prediction.

    n_estimators:   150 — slightly more than IsolationForest because
                    failure prediction is a harder supervised task.
    max_depth:      6 — prevents overfitting on small synthetic dataset.
    random_state:   Fixed for reproducibility.

    Class imbalance is handled by per-sample weights (trainer.py's
    proximity_weights), not class_weight — the weighting mirrors
    "balanced" while additionally down-weighting records far from the
    failure window. See trainer.py for the formula.
    """
    n_estimators: int = 150
    max_depth: int = 6
    random_state: int = 42


MODEL_CONFIGS: dict[str, object] = {
    "IsolationForest": IsolationForestConfig(),
    "RandomForest":    RandomForestConfig(),
}


# ---------------------------------------------------------------------------
# Evaluation benchmarks — pass/fail gates
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AnomalyDetectionBenchmarks:
    """
    Minimum acceptable performance for anomaly detection models.

    These are hard gates — training is considered failed if any
    metric falls below its benchmark. The artifact is not written
    and no model is registered.

    Attributes:
        precision:          Minimum precision on the anomaly class.
                            Low precision = too many false alarms,
                            operators stop trusting the system.
        recall:             Minimum recall on the anomaly class.
                            Low recall = real anomalies are missed —
                            more dangerous than false alarms.
        false_positive_rate: Maximum acceptable FPR.
                            Operators act on alerts — FPR > 0.15
                            causes alert fatigue.
        lead_time_records:  Minimum records before failure at which
                            the model must start flagging anomalies.
                            Gives operators time to act.
    """
    precision: float = 0.72
    recall: float = 0.68
    false_positive_rate: float = 0.15
    lead_time_records: int = 10


@dataclass(frozen=True)
class FailurePredictionBenchmarks:
    """
    Minimum acceptable performance for failure prediction models.

    Attributes:
        auc_roc:    Area under ROC curve. Primary metric for
                    imbalanced binary classification.
                    0.80 = strong discrimination ability.
        f1:         Harmonic mean of precision and recall.
        precision:  Minimum precision on failure class.
        recall:     Minimum recall on failure class.
                    Missing failures is more costly than false alarms.
        brier_score: Calibration metric — measures probability
                    estimate quality, not just ranking.
                    Lower is better; 0.25 = random baseline.
    """
    auc_roc: float = 0.80
    f1: float = 0.68
    precision: float = 0.70
    recall: float = 0.65
    brier_score: float = 0.15   # maximum acceptable (lower = better)


ANOMALY_BENCHMARKS = AnomalyDetectionBenchmarks()
FAILURE_BENCHMARKS = FailurePredictionBenchmarks()


# ---------------------------------------------------------------------------
# Artifact output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ArtifactConfig:
    """
    Artifact serialization and storage configuration.

    Attributes:
        output_dir:     Directory where .joblib files are written.
                        Relative to the backend root.
                        PRODUCTION NOTE: Replace with S3 URI prefix
                        (s3://nexusiq-models/) when moving to
                        multi-worker deployment.
        uri_scheme:     URI prefix prepended to artifact filenames.
                        Signals to model_loader.py which storage
                        backend to use for resolution.
        compress_level: joblib compression level 0–9.
                        3 is a good balance — reduces artifact size
                        without meaningful serialization overhead.
    """
    output_dir: str = "artifacts"
    uri_scheme: str = "local://"
    compress_level: int = 3

    def build_artifact_path(
        self,
        asset_type: str,
        model_type: str,
        task: str,
        version: int,
    ) -> str:
        """
        Build a URI-style artifact path for a trained model.

        Format: local://artifacts/{asset_type}_{model_type}_{task}_v{version}.joblib

        Args:
            asset_type: Asset type name (e.g. "compressor").
            model_type: Algorithm name (e.g. "IsolationForest").
            task:       Inference task (e.g. "anomaly_detection").
            version:    Model version integer.

        Returns:
            str: Full URI-style artifact path.
        """
        filename = (
            f"{asset_type}_{model_type}_{task}_v{version}.joblib"
        )
        return f"{self.uri_scheme}{self.output_dir}/{filename}"


ARTIFACT_CONFIG = ArtifactConfig()


# ---------------------------------------------------------------------------
# Task → model type mapping
# ---------------------------------------------------------------------------

# Maps task → model_type. One model per task — there is a single service
# level, so the algorithm is determined by the inference task alone.

TASK_MODEL_MAP: dict[str, str] = {
    "anomaly_detection":  "IsolationForest",
    "failure_prediction": "RandomForest",
}