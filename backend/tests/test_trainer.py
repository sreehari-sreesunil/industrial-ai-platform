import numpy as np

from scripts.training.trainer import proximity_weights


def test_proximity_weights_negatives_get_flat_weight() -> None:
    y_train = np.array([0, 0])
    hours_to_failure = np.array([np.nan, np.nan])

    weights = proximity_weights(y_train, hours_to_failure, horizon_hours=48)

    assert np.allclose(weights, [1.0, 1.0])


def test_proximity_weights_positive_at_failure_moment_gets_full_weight() -> None:
    y_train = np.array([0, 0, 1])
    hours_to_failure = np.array([np.nan, np.nan, 0])

    weights = proximity_weights(y_train, hours_to_failure, horizon_hours=48)

    pos_weight_base = 2 / 1  # n_neg / n_pos
    assert np.isclose(weights[2], pos_weight_base)


def test_proximity_weights_decays_toward_horizon_edge() -> None:
    y_train = np.array([0, 0, 1, 1])
    hours_to_failure = np.array([np.nan, np.nan, 0, 24])

    weights = proximity_weights(y_train, hours_to_failure, horizon_hours=48)

    # Record at the failure moment should be weighted more than one
    # halfway to the horizon edge.
    assert weights[2] > weights[3]

    pos_weight_base = 2 / 2
    expected_halfway = pos_weight_base * 0.6  # see proximity_weights formula
    assert np.isclose(weights[3], expected_halfway)


def test_proximity_weights_nan_falls_back_to_full_weight() -> None:
    y_train = np.array([0, 0, 1])
    hours_to_failure = np.array([np.nan, np.nan, np.nan])

    weights = proximity_weights(y_train, hours_to_failure, horizon_hours=48)

    pos_weight_base = 2 / 1
    assert np.isclose(weights[2], pos_weight_base)


def test_proximity_weights_no_positives_returns_all_ones() -> None:
    y_train = np.array([0, 0, 0])
    hours_to_failure = np.array([np.nan, np.nan, np.nan])

    weights = proximity_weights(y_train, hours_to_failure, horizon_hours=48)

    assert np.allclose(weights, [1.0, 1.0, 1.0])