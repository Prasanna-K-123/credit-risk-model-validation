"""Fixed feature pipelines and bounded probability updates; no data access."""
from __future__ import annotations

import hashlib
import numpy as np
from scipy.optimize import brentq
from scipy.special import expit, logit
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC = ["fico", "dti", "ltv", "cltv", "mi_pct", "original_term",
           "original_rate", "current_rate", "log_original_upb", "log_current_upb",
           "calendar_age", "current_dq", "max_dq_6m", "dq_months_6m",
           "balance_ratio_6m", "modified_by_snapshot"]
CATEGORICAL = ["purpose", "occupancy", "property_type", "relief_refinance"]
FEATURES = NUMERIC + CATEGORICAL
SEED = 20261016
VARIANTS = ["unchanged", "recalibrated", "retrained"]


def pipeline(family):
    numeric = [("impute", SimpleImputer(strategy="median", add_indicator=True,
                                       keep_empty_features=True))]
    if family == "logit":
        numeric.append(("scale", StandardScaler()))
        model = LogisticRegression(C=1.0, max_iter=2000, random_state=SEED,
                                   solver="lbfgs", tol=1e-4)
    elif family == "hgb":
        model = HistGradientBoostingClassifier(
            learning_rate=.05, max_iter=200, max_leaf_nodes=7,
            min_samples_leaf=200, l2_regularization=10.,
            early_stopping=False, random_state=SEED, categorical_features=None)
    else:
        raise ValueError("Unknown fixed family")
    pre = ColumnTransformer([
        ("numeric", Pipeline(numeric), NUMERIC),
        ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False),
         CATEGORICAL)], remainder="drop", sparse_threshold=0)
    return Pipeline([("preprocess", pre), ("model", model)])


def raw_logits(model, frame):
    # Both fixed estimators expose public decision_function: no probability
    # clipping is required when fitting the one-parameter calibration update.
    z = np.asarray(model.decision_function(frame[FEATURES]), dtype=float)
    if not np.isfinite(z).all():
        raise ValueError("Nonfinite model log odds")
    return z


def intercept_update(z, y):
    z, y = np.asarray(z), np.asarray(y)
    if not (0 < y.sum() < len(y)):
        raise ValueError("Recalibration requires both outcome classes")
    delta = brentq(lambda d: np.mean(expit(z+d)-y), -40., 40., xtol=1e-13)
    return {"delta": float(delta),
            "mean_score_residual": float(np.mean(expit(z+delta)-y))}


def choose_variant(scores):
    best = min(scores.values())
    return next(v for v in VARIANTS if scores[v] <= best+1e-8)


def choose_family(logit_brier, hgb_brier):
    return "logit" if logit_brier <= hgb_brier+.0001 else "hgb"


def review_order(probabilities, identifiers):
    tie = np.array([hashlib.sha256(str(x).encode()).hexdigest() for x in identifiers])
    return np.lexsort((tie, -np.asarray(probabilities)))


def capacity_bounds(labels, selected):
    """Sharp capture/precision bounds with unresolved labels, fixed selection."""
    y = np.asarray(labels, float)
    selected = np.asarray(selected, bool)
    positives = int(np.nansum(y))
    captured = int(np.nansum(y[selected]))
    unknown_in = int(np.isnan(y[selected]).sum())
    unknown_out = int(np.isnan(y[~selected]).sum())
    k = int(selected.sum())
    return {"reviewed": k, "known_positive_captured": captured,
            "known_outcome_recall": captured/positives if positives else None,
            "unresolved_reviewed": unknown_in,
            "capture_bounds": [captured/(positives+unknown_out)
                               if positives+unknown_out else None,
                               (captured+unknown_in)/(positives+unknown_in)
                               if positives+unknown_in else None],
            "precision_bounds": [captured/k, (captured+unknown_in)/k] if k else [None, None]}
