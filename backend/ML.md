# NexusIQ — ML Engineering

> Last updated: Single-tier cleanup + sparse-sensor robustness session

---

## ML Model Ownership and Lifecycle

NexusIQ trains and deploys all models. Customers receive inference results; they do not own, train, or configure ML models.

**Lifecycle states:**
| State | Meaning |
|-------|---------|
| `untrained` | Record created, no artifact yet |
| `training` | Pipeline running |
| `trained` | Artifact available, not yet serving traffic |
| `deployed` | Actively serving inference requests |
| `retired` | Superseded; kept for audit trail |

Customer-level adaptation happens through `ml_asset_baselines` — per-asset statistical envelopes — **at inference time only**. The training pipeline (`scripts/training/`) trains one global model per asset_type + task combination; it does not read baselines or compute z-score features. See "Cross-Facility Variability Handling" below for the honest state of this gap.

---

## Single-Tier Model Selection

NexusIQ previously planned a three-tier subscription model (`standard` / `professional` / `enterprise`), each tier mapped to a different algorithm. That system was removed to focus engineering effort on one model pair per task, validated properly, rather than three shallow variants.

**Current model selection** (`scripts/training/config.py`, `TASK_MODEL_MAP`):

| Task | Algorithm |
|------|-----------|
| `anomaly_detection` | Isolation Forest |
| `failure_prediction` | Random Forest |

The `tier` column still exists on `organizations` and `ml_models` (DB schema unchanged, no migration) — every model is now registered with `tier="standard"`. The column is read but never branched on; it's kept only because removing a NOT NULL column would require a migration that buys nothing right now.

One-Class SVM and XGBoost were deleted (not deprecated) along with the tier system. XGBoost had been used once as a diagnostic — it performed almost identically to Random Forest on this dataset, which is itself a useful data point: tree ensembles aren't meaningfully differentiated from each other on this feature set, so the choice between them isn't where the model's real limitations live (see "Known Limitations" below).

---

## Sparse-Safe Feature Engineering

### The problem

Industrial sensors fail, and not every facility installs every sensor in the first place — vibration accelerometers in particular are more expensive and specialized than pressure/rotation sensors, and are often the first thing a budget-conscious facility skips. A naive ML pipeline treats missing data as zero or imputes a mean — both options corrupt signal at exactly the moments that matter most, or silently produce a confident, wrong prediction with no indication anything is off.

### The design

Every metric that supports sparse-sensor handling generates two extra features alongside its existing raw/rolling features:

| Feature name | Type | Description |
|--------------|------|--------------|
| `{metric}_available` | float | `1.0` if the sensor is present, `0.0` if simulated/actually missing |
| `{metric}_zscore` | float | Deviation from the asset's learned baseline mean, in standard deviations. `0.0` when no mature baseline exists yet. |

The `_available` flag is what lets the model distinguish "this sensor genuinely read zero" from "this sensor isn't reporting at all." Without it, a missing sensor's zeroed value is indistinguishable from a real low reading, and the model will silently misinterpret it.

**Important: these two feature types are implemented in two different places, with different levels of completeness — this used to be a real, undocumented gap:**

- **`{metric}_zscore`** is implemented in `app/ml/feature_engineering.py` and used at **inference time only**, reading from `ml_asset_baselines`. It is **not** computed by the training pipeline (`scripts/training/data_loader.py`) — the model currently in production has never seen a z-score feature during training. This is a real architectural inconsistency, not yet resolved. See "Known Limitations."

- **`{metric}_available`** is implemented and validated on **both** sides as of this session, but currently scoped narrowly to two sensors: `rotation` and `vibration` (`FeatureConfig.MASKABLE_SENSORS` in `scripts/training/config.py`). Voltage and pressure do not yet have `_available` flags or masking-aware training.

### Why mean imputation was rejected

Mean imputation fills missing values with the historical average, making the input look statistically normal. Anomalies often coincide with sensor failures — a failing compressor may cause a vibration sensor to drop out at exactly the moment its readings would otherwise be most informative. Imputing the mean at that moment hides the anomaly signature at the worst possible time.

### Training data augmentation — validated, not just designed

Unlike the z-score gap above, this part is now real and tested, not aspirational. During training, for each record, each maskable sensor (`rotation`, `vibration`) is independently masked with probability `mask_probability` (default `0.15`, see `FeatureConfig` in `config.py`): the raw value, both rolling features, and the rate-of-change feature for that sensor are zeroed, and `{sensor}_available` is set to `0.0`. The label is never altered — only what the model is allowed to see changes, not the ground truth. Masking is applied per-CV-fold with a deterministic, fold-derived seed (`FeatureConfig.mask_seed + fold_index`), so the whole training run remains fully reproducible. Masking is applied to the **training** split only — validation and hold-out sets are never masked, since they need to reflect either ground truth or a deliberately constructed missing-sensor scenario, never random training-style noise.

**Offline validation results** (RandomForest, `failure_prediction`, real Azure Predictive Maintenance dataset, holdout evaluation):

| Scenario | AUC-ROC | Notes |
|---|---|---|
| Baseline model, all sensors present | 0.928 | |
| Masking-trained model, all sensors present | 0.926 | Essentially unchanged — masking does not hurt normal-case performance |
| Baseline model, **vibration** forced missing | 0.851 | |
| Masking-trained model, **vibration** forced missing | 0.851 | No measurable benefit — consistent with vibration's near-zero feature importance even when present |
| Baseline model, **rotation** forced missing | **0.522** | Near-random — the model had no fallback for losing its most important feature |
| Masking-trained model, **rotation** forced missing | **0.795** | Large, genuine recovery — masking-training specifically protects against losing high-importance sensors |

This is an honest two-part result, not a uniform win: masking-training provides large, real protection for sensors the model actually relies on (rotation), and provides no measurable benefit for sensors that were already unimportant (vibration) — which makes sense, since there's little signal to protect in the latter case. The real end-to-end training run (with masking wired into `scripts/training/data_loader.py`) confirmed this is neutral on overall holdout precision/F1/AUC when all sensors are present, as expected.

**Not yet built:** masking is applied identically to both `failure_prediction` and `anomaly_detection` training, for implementation consistency, but the offline validation above was only run for `failure_prediction` (RandomForest). The `anomaly_detection` (Isolation Forest) extension is a reasoned extrapolation of the same mechanism, not separately tested.

---

## Baseline Learning System

Each asset builds its own statistical envelope per metric. Baselines are the mechanism for local adaptation, currently used at inference time only (see the z-score gap above).

**Schema: `ml_asset_baselines`**

| Field | Description |
|-------|-------------|
| `asset_id` | Asset this baseline belongs to |
| `metric_name` | Sensor/metric identifier |
| `baseline_mean` | Historical average |
| `baseline_std` | Standard deviation |
| `baseline_min` / `baseline_max` | Observed range |
| `percentile_95` | Upper 95th percentile (anomaly threshold input) |
| `samples_count` | Number of readings used to compute this baseline |
| `is_mature` | `true` once enough data has been collected |
| `learning_period_start` / `learning_period_end` | Time window the baseline was learned over |
| `updated_at` | When the baseline was last recalculated |

**Maturity flag:** Until `is_mature = true`, `feature_engineering.py` returns `0.0` for that metric's z-score rather than a real value — this is the cold-start handling: a newly onboarded asset's predictions aren't corrupted by a noisy, undertrained baseline, they simply don't get a z-score contribution yet.

---

## ML Directory Structure
`app/ml/rul/weibull.py` (professional-tier RUL estimator) was deleted along with the tier system — it had no importers and was never wired into anything.

---

## Inference Pipeline

**Trigger:** Synchronous, called via `app/api/routes/ml_inference.py`.

**Steps** (`app/services/ml_inference.py::_run_inference_for_task`):

1. Load asset, resolve `asset_type_id`
2. Fetch the deployed model for `asset_type_id + task` (tier is always `"standard"`, hardcoded)
3. Load model artifact from disk (cached in memory after first load)
4. Fetch latest telemetry record for the asset
5. Fetch baselines for the asset (`ml_asset_baselines`)
6. Build feature vector (`feature_engineering.py` — includes z-score; **does not match training's feature set, see Known Limitations**)
7. Score with model
8. Normalize score to 0–1 (`scoring.normalize_score`)
9. Classify risk level (`scoring.classify_risk`)
10. Compute confidence
11. Persist `MLPrediction` record
12. Conditionally create `MLAnomalyEvent`

---

## Known Limitations (honest, current state)

These are real, currently-unresolved gaps, documented here so they're found by reading this file rather than rediscovered by debugging a confusing production issue later.

1. **Training/inference feature mismatch.** `feature_engineering.py` (inference) includes `{metric}_zscore` features that `data_loader.py` (training) does not compute. If `feature_names` ever gets out of sync between what a registered model expects and what `build_feature_vector` produces, inference would either crash on a shape mismatch or — worse — silently misalign feature columns. Currently safe only because `build_feature_vector` is driven by the model's stored `feature_names` list, which doesn't include z-score columns, but this is a fragile correctness boundary, not a designed safeguard.

2. **No model has passed its benchmark gate yet.** `failure_prediction` (RandomForest) consistently fails on precision (~0.25 holdout vs. 0.70 required) and F1 (~0.37 vs. 0.68 required), despite strong AUC-ROC (~0.93). Three independent hypotheses have been tested and ruled out, not assumed:
   - **Not a threshold-placement problem** — the full precision-recall curve was inspected directly; no threshold on it reaches 0.70 precision at any recall level.
   - **Not primarily a feature-richness or hyperparameter problem** — feature importance is concentrated in rolling-mean features (operating level); a dual-window (6h+24h) test showed no rescue of the unused rolling-std/rate-of-change features.
   - **Not a missing per-machine-baseline problem** — tested twice, independently: a static pool-level z-score (early session) and a proper time-respecting expanding-window z-score with no information leakage (`scripts/training/experiments/inspect_per_machine_baseline.py`). Both showed the same result: precision/F1 move by less than normal fold-to-fold noise (e.g. 0.2018 → 0.2064), and per-machine z-score features never rank in the model's top 5 by importance. Likely explanation: this dataset's 100 machines are simulated/benchmark units, not real machines with genuinely different operating cultures — the premise behind per-machine baselines may be valid in general but isn't strongly represented in this specific dataset.

   The likely real cause, after ruling out the above: many records near the edge of the 48h failure-labeling window are statistically close to indistinguishable from healthy records, capping achievable precision regardless of model choice or available features. This is treated as a documented, investigated limitation of this dataset/labeling scheme, not an unsolved bug.

3. **`anomaly_detection` (Isolation Forest) fails structurally on lead time.** `lead_time_records` benchmark requires ≥10, actual is 0.0 — confirmed architectural limitation, not a bug: an unsupervised anomaly detector has no learned concept of "time until failure," so by the time a reading is anomalous enough to flag, there's no guaranteed advance warning.

4. **`pump` and `motor` asset types don't exist in the database yet.** Only `compressor` has a real `asset_types` row and real (if minimal) telemetry. `run_training.py --asset-type pump` or `--asset-type motor` would fail at the same asset-type lookup step that `compressor` originally failed at, for the same reason — no matching row.

5. **Sparse-sensor masking covers only `rotation` and `vibration`.** Voltage and pressure are untested for this mechanism; extending to them would need the same offline validation process described above before being trusted.

6. **RUL estimation: the simplest approach wins, tested three ways.** Compared three RUL approaches on the same holdout machines, using MAE, a CMAPSS-style asymmetric score (penalizes predicting too MUCH remaining time more heavily than too little, since that's the dangerous direction — maintenance gets scheduled too late), and accuracy specifically within the decision-relevant zone (true RUL <= 48h, matching `FAILURE_HORIZON_HOURS`):

   | Approach | Decision-zone MAE | Asymmetric score | Coverage |
   |---|---|---|---|
   | RandomForest regressor (direct hours-to-failure target, capped at 300h) | 189h | 4.50 | 100% |
   | Naive: `(1 - failure_probability) * 300` from the existing failure_prediction classifier, no smoothing | **68h** | **3.61** | 100% |
   | EWMA-smoothed version of the same classifier output (`app/ml/rul/ewma.py`) | 106h | 7.57 | 41% |

   The naive, unsmoothed conversion of the classifier's own output won on every decision-relevant metric. The regressor performed worst exactly where it matters most — likely because its training target (hours-to-failure, capped at 300h) is dominated by examples far from failure (only 5.8% of holdout records fall within the 48h decision zone), so the model optimizes mostly for a range that isn't actionable. EWMA's smoothing, counter to the original design intent, made predictions *less* accurate than the raw classifier output it was smoothing — and produced no estimate at all for 59% of records (insufficient history, or `MIN_HISTORY_RECORDS`/stable-trend filtering). Reproducible in `scripts/training/experiments/inspect_rul_comparison.py`.

   This was the first time `compute_ewma_rul()` and `create_asset_health()`/`get_health_history_by_asset()` were ever exercised end-to-end — both existed, fully implemented, with zero callers anywhere in the codebase before this investigation (see the health-pipeline wiring change). A real bug was found and fixed during this comparison: `compute_ewma_rul`'s internal `MAX_RUL_DAYS` cap (365 days) is on a completely different scale than this dataset's natural decision horizon; left uncapped, EWMA's "year-plus, can't estimate precisely" outputs (8760 hours) corrupted every aggregate metric until rescaled to match the other two approaches' 300h cap.

7. **Dormant synthetic data-generation system in `scripts/training/config.py`.** `OperatingEnvelope` and `AssetDataConfig` (lines ~29-94) define a complete synthetic telemetry generator for all three asset types — `total_records`, `normal_fraction`/`degradation_fraction`/`failure_fraction` phases, per-sensor operating envelopes (mean/std/failure_threshold) for compressor, pump, and motor — with zero callers anywhere in the codebase (`grep -rn "AssetDataConfig|ASSET_DATA_CONFIGS|OperatingEnvelope"` outside this file's own definition returns nothing). This is almost certainly leftover scaffolding from before the project adopted the real Azure Predictive Maintenance dataset (see the original project handoff's documented "scope change" — synthetic data was explicitly rejected in favor of real data). Notably, this is the only place in the codebase where `pump` and `motor` have any associated numeric parameters at all — but they're synthetic generation envelopes, not real telemetry, so they do not resolve item 4 (no `pump`/`motor` `asset_types` row or real data exists). Investigated while scoping drift detection (hypothesized this might be a drift-simulation tool, since `degradation_rate` sounded relevant — confirmed it is not; it's a training-data generator unrelated to drift, which requires comparing two real distributions, not simulating one).
---

## Drift Detection Plan (not started)

Models trained on historical data degrade as equipment ages and operating conditions shift. Drift monitoring would detect when a deployed model's input distribution has moved away from its training distribution. Planned approach: PSI (Population Stability Index) and statistical (KS-test) drift detection on rolling windows, with EvidentlyAI integration considered for automated reporting. None of this has been implemented — flagged here as a real gap, not a near-term plan.

---

## Cross-Facility Variability Handling (partially built)

Industrial equipment varies across customer sites — different operating conditions, load profiles, and maintenance histories. The intended design has two layers:

**Layer 1 — Global base model (built, trained, evaluated).** One model per asset_type + task, trained on aggregated data. Captures dataset-wide failure signatures.

**Layer 2 — Local adaptation via `ml_asset_baselines` (built for inference, not training).** Each asset accumulates its own statistical baseline; `feature_engineering.py` uses it to compute z-scores at inference time, with cold-start handling via `is_mature`. The training pipeline does not currently use this layer at all — see Known Limitations, item 1.

---

## Changelog

| Session | What changed |
|--------|-------------|
| Initial sprints | Schema, telemetry ingestion, auth, ML tables, ORM models, original CRUD layer |
| Single-tier cleanup | Removed three-tier model selection (`TIER_MODEL_MAP` → `TASK_MODEL_MAP`), deleted OneClassSVM/XGBoost/weibull.py, fixed a pre-existing bug where `app/crud/ml_model.py` was a byte-identical copy of `ml_anomaly_event.py` (real CRUD functions had never existed), fixed a pre-existing data bug where no `asset_types` row was named `compressor` |
| Sparse-sensor robustness | Added `{sensor}_available` features and training-time masking for `rotation`/`vibration`; validated offline (precision-recall curve inspection, feature importance analysis, forced-missing-sensor AUC comparison) before implementing in the real pipeline |

