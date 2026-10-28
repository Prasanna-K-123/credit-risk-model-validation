"""Dated bank-failure research contracts; deliberately separate from retail PD."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit

FEATURES = (
    "equity_to_assets", "loans_to_assets", "deposits_to_assets",
    "cash_to_assets", "securities_to_assets", "nonperforming_assets_fraction",
    "return_on_assets_fraction", "net_interest_margin_fraction", "log_assets",
)
FINANCIAL_FIELDS = (
    "CERT", "REPDTE", "ASSET", "EQ", "LNLSNET", "DEP", "CHBAL", "SC",
    "NPERFV", "ROA", "NIMY", "ENDEFYMD", "BKCLASS",
)
ROLES = ("development", "selection", "calibration", "policy", "test")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_date(value) -> date | None:
    """Parse only documented source encodings; zero/open-ended sentinels are not dates."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    if text in {"", "0", "00000000", "99991231", "12/31/9999"}:
        return None
    for fmt in ("%Y%m%d", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unsupported source date: {text!r}")


def certificate(value) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError("Invalid certificate")
    f = float(value)
    if not np.isfinite(f) or f <= 0 or f != int(f):
        raise ValueError("Invalid certificate")
    return int(f)


def financial_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Explicit whitelist; dates/identifiers/statuses/outcomes cannot become predictors."""
    required = set(FINANCIAL_FIELDS[:11])
    absent = required - set(frame.columns)
    if absent:
        raise ValueError(f"Missing required source fields: {sorted(absent)}")
    numeric = frame[list(required)].apply(pd.to_numeric, errors="coerce")
    assets = numeric["ASSET"]
    if (~np.isfinite(assets) | (assets <= 0)).any():
        raise ValueError("Features require finite positive assets")
    out = pd.DataFrame(index=frame.index)
    for name, field in (
        ("equity_to_assets", "EQ"), ("loans_to_assets", "LNLSNET"),
        ("deposits_to_assets", "DEP"), ("cash_to_assets", "CHBAL"),
        ("securities_to_assets", "SC"),
    ):
        out[name] = numeric[field] / assets
    # FDIC already publishes these in percent units, including annualization.
    out["nonperforming_assets_fraction"] = numeric["NPERFV"] / 100.0
    out["return_on_assets_fraction"] = numeric["ROA"] / 100.0
    out["net_interest_margin_fraction"] = numeric["NIMY"] / 100.0
    # All monetary source fields share a unit; this size proxy is nominal, not inflation-adjusted.
    out["log_assets"] = np.log(assets)
    return out[list(FEATURES)].replace([np.inf, -np.inf], np.nan)


def bank_registry(records: list[dict]) -> dict[int, dict]:
    out = {}
    for r in records:
        c = certificate(r["CERT"])
        if c in out:
            raise ValueError(f"Duplicate institution certificate {c}")
        if r["ACTIVE"] not in (0, 1, "0", "1"):
            raise ValueError("Unknown current institution status")
        active = int(r["ACTIVE"])
        out[c] = {
            "active": active,
            "end": source_date(r.get("ENDEFYMD")) if not active else None,
            "established": source_date(r.get("ESTYMD")),
            "insured": source_date(r.get("INSDATE")),
        }
    return out


def failure_registry(records: list[dict], first_prediction: date) -> dict[int, date]:
    out = {}
    for r in records:
        # Assistance is a distinct event, not silently relabelled as failure.
        if str(r.get("RESTYPE", "")).strip().upper() != "FAILURE":
            continue
        d = source_date(r.get("FAILDATE"))
        if d is None:
            raise ValueError("Failure without an event date")
        if d < first_prediction:
            continue
        c = certificate(r.get("CERT"))
        if c in out:
            raise ValueError(f"Multiple failure records for certificate {c}")
        out[c] = d
    return out


def role_for_year(year: int, protocol: dict) -> str | None:
    roles = [r for r in ROLES if year in protocol["report_years"][r]]
    if len(roles) > 1:
        raise ValueError("Overlapping report-year partitions")
    return roles[0] if roles else None


def build_panel(financials: list[dict], institutions: list[dict], failures: list[dict], protocol: dict):
    banks = bank_registry(institutions)
    events = failure_registry(failures, date(1993, 4, 1))
    cutoff = date.fromisoformat(protocol["outcome_cutoff"])
    rows, exclusions = [], Counter()
    seen = set()
    for r in financials:
        c = certificate(r["CERT"])
        reporting = source_date(r["REPDTE"])
        if reporting is None or (reporting.month, reporting.day) != (12, 31):
            raise ValueError("Annual anchor requires an actual December 31 report")
        key = (c, reporting)
        if key in seen:
            raise ValueError("Duplicate certificate/report-date source row")
        seen.add(key)
        role = role_for_year(reporting.year, protocol)
        if role is None:
            exclusions["purged_or_unused_year"] += 1
            continue
        asof = date(reporting.year + 1, 4, 1)
        horizon = date(reporting.year + 2, 4, 1)
        if horizon > cutoff:
            raise ValueError("Outcome horizon has not matured at source cutoff")
        b = banks.get(c)
        if b is None:
            exclusions["unmatched_institution"] += 1
            continue
        if not b["active"] and b["end"] is None:
            exclusions["unknown_inactive_date"] += 1
            continue
        if b["established"] is None or b["insured"] is None:
            exclusions["unknown_origin_or_insurance_date"] += 1
            continue
        if b["established"] > reporting or b["insured"] > reporting:
            exclusions["source_before_establishment_or_insurance"] += 1
            continue
        event = events.get(c)
        if event is not None and b["end"] is not None and b["end"] < event:
            exclusions["failure_after_registered_inactive_date"] += 1
            continue
        if event is not None and event <= asof:
            exclusions["failure_already_occurred"] += 1
            continue
        if b["end"] is not None and b["end"] <= asof:
            exclusions["institution_inactive_at_prediction"] += 1
            continue
        try:
            assets = float(r["ASSET"])
        except (TypeError, ValueError):
            assets = np.nan
        if not np.isfinite(assets) or assets <= 0:
            exclusions["invalid_assets"] += 1
            continue
        # Failure date is the authority for the event; closure/merger status is not a predictor.
        positive = event is not None and asof < event <= horizon
        exit_in_horizon = b["end"] is not None and asof < b["end"] <= horizon
        rows.append({
            **r, "CERT": c, "report_date": reporting.isoformat(),
            "prediction_date": asof.isoformat(), "horizon_end": horizon.isoformat(),
            "role": role, "failure": int(positive),
            "failure_date": event.isoformat() if event is not None else "",
            "nonfailure_exit": int(exit_in_horizon and not positive),
        })
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("No eligible dated observations")
    features = financial_features(frame)
    panel = pd.concat([frame[["CERT", "report_date", "prediction_date", "horizon_end", "role", "failure", "failure_date", "nonfailure_exit"]], features], axis=1)
    panel = panel.sort_values(["report_date", "CERT"]).reset_index(drop=True)
    assert_temporal_partitions(panel)
    coverage = []
    years = sorted({date.fromisoformat(d).year for d in panel["prediction_date"]})
    for y in years:
        start, end = date(y, 4, 1), date(y + 1, 4, 1)
        listed = {c for c, d in events.items() if start < d <= end}
        covered = set(panel.loc[(panel.prediction_date == start.isoformat()) & (panel.failure == 1), "CERT"])
        coverage.append({"prediction_year": y, "listed_failure_certificates": len(listed), "covered_failure_certificates": len(covered), "uncovered_certificates": sorted(listed - covered)})
    audit = {"raw_financial_rows": len(financials), "eligible_rows": len(panel), "unique_certificates": int(panel.CERT.nunique()), "exclusions": dict(exclusions), "failure_coverage": coverage,
             "target": "FDIC certificate failure before any nonfailure exit within (April 1, next April 1]; mergers/insurance exits are competing nonfailure outcomes, not borrower defaults.",
             "revisions": "Current historical snapshot; original publication availability and historical revisions are not reconstructed."}
    return panel, audit


def assert_temporal_partitions(panel: pd.DataFrame):
    if panel.duplicated(["CERT", "report_date"]).any():
        raise ValueError("Duplicate panel key")
    if set(panel.role) != set(ROLES):
        raise ValueError("All five registered partitions must be represented")
    if not panel.failure.isin([0, 1]).all():
        raise ValueError("Nonbinary event labels")
    report = pd.to_datetime(panel.report_date)
    prediction = pd.to_datetime(panel.prediction_date)
    horizon = pd.to_datetime(panel.horizon_end)
    if not ((report < prediction) & (prediction < horizon)).all():
        raise ValueError("Invalid report/prediction/horizon ordering")
    expected_prediction = pd.to_datetime((report.dt.year+1).astype(str)+'-04-01')
    expected_horizon = pd.to_datetime((report.dt.year+2).astype(str)+'-04-01')
    if not ((report.dt.month == 12) & (report.dt.day == 31) & (prediction == expected_prediction) & (horizon == expected_horizon)).all():
        raise ValueError("Dates do not implement the registered annual availability/horizon contract")
    for earlier, later in zip(ROLES, ROLES[1:]):
        if horizon[panel.role == earlier].max() >= prediction[panel.role == later].min():
            raise ValueError("Earlier outcomes overlap or are unavailable at the next partition")
    # Repeated certificates across later dates are intentional longitudinal observations.


@dataclass
class MonotoneCalibrator:
    intercept: float
    slope: float
    penalty: float = 1e-6

    @classmethod
    def fit(cls, probabilities: np.ndarray, y: np.ndarray):
        y = np.asarray(y, dtype=float)
        if set(np.unique(y)) != {0.0, 1.0}:
            raise ValueError("Calibration requires both classes")
        s = logit(np.clip(np.asarray(probabilities), 1e-8, 1-1e-8))
        ridge = 1e-6
        def objective(theta):
            a, b = theta
            z = a + b*s
            loss = np.mean(np.logaddexp(0, z) - y*z) + ridge*np.dot(theta, theta)
            residual = expit(z)-y
            grad = np.array([residual.mean(), np.mean(residual*s)]) + 2*ridge*theta
            return loss, grad
        fit = minimize(objective, [logit(y.mean()), 1.0], jac=True, method="L-BFGS-B", bounds=[(None, None), (0.0, None)], options={"ftol": 1e-12, "gtol": 1e-8, "maxiter": 1000})
        if not fit.success or not np.isfinite(fit.x).all():
            raise ValueError("Calibration optimizer did not converge")
        return cls(float(fit.x[0]), float(fit.x[1]), ridge)

    def predict(self, probabilities):
        s = logit(np.clip(np.asarray(probabilities), 1e-8, 1-1e-8))
        return np.clip(expit(self.intercept + self.slope*s), 1e-8, 1-1e-8)


def policy_threshold(y, p, fn_weight: float = 100.0):
    """Minimize an explicitly illustrative screening cost; ties prefer less reviewing."""
    y, p = np.asarray(y, int), np.asarray(p, float)
    order = np.argsort(-p, kind="stable")
    ps, ys = p[order], y[order]
    ends = np.r_[np.flatnonzero(ps[1:] != ps[:-1]), len(ps)-1]
    tp = np.cumsum(ys)[ends]
    fp = (ends+1)-tp
    costs = fn_weight*(y.sum()-tp)+fp
    thresholds = np.r_[np.nextafter(1.0, np.inf), ps[ends]]
    costs = np.r_[fn_weight*y.sum(), costs]
    idx = int(np.flatnonzero(costs == costs.min())[0])
    return float(thresholds[idx]), float(costs[idx])


class FrozenScoreMetrics:
    """Weighted, tie-correct ROC area/AP without repeatedly sorting during resampling."""
    def __init__(self, y, p, threshold, fn_weight=100.0):
        self.y = np.asarray(y, int)
        self.p = np.asarray(p, float)
        if len(self.y) == 0 or self.p.shape != self.y.shape or not np.isin(self.y, [0,1]).all():
            raise ValueError("Nonempty equal-shaped binary labels/probabilities required")
        if not np.isfinite(self.p).all() or ((self.p < 0) | (self.p > 1)).any():
            raise ValueError("Finite probabilities in [0,1] required")
        self.order = np.argsort(-self.p, kind="stable")
        ps = self.p[self.order]
        self.ends = np.r_[np.flatnonzero(ps[1:] != ps[:-1]), len(ps)-1]
        self.brier = (self.y-self.p)**2
        clipped = np.clip(self.p, 1e-8, 1-1e-8)
        self.logloss = -(self.y*np.log(clipped)+(1-self.y)*np.log1p(-clipped))
        decision = self.p >= threshold
        self.cost = fn_weight*((self.y == 1) & ~decision) + ((self.y == 0) & decision)

    def evaluate(self, weights=None):
        w = np.ones(len(self.y)) if weights is None else np.asarray(weights, float)
        total = w.sum()
        if total <= 0 or (w < 0).any():
            raise ValueError("Weights must be nonnegative with positive total")
        pos = np.dot(w, self.y)
        neg = total-pos
        out = {"brier": float(np.dot(w, self.brier)/total), "log_loss": float(np.dot(w, self.logloss)/total), "weighted_cost_per_row": float(np.dot(w, self.cost)/total)}
        if pos <= 0 or neg <= 0:
            out.update(auc=np.nan, average_precision=np.nan)
            return out
        ws, ys = w[self.order], self.y[self.order]
        tp = np.cumsum(ws*ys)[self.ends]
        fp = np.cumsum(ws*(1-ys))[self.ends]
        tpr, fpr = tp/pos, fp/neg
        precision = np.divide(tp, tp+fp, out=np.zeros_like(tp), where=(tp+fp)>0)
        out["auc"] = float(np.trapezoid(np.r_[0.0,tpr], np.r_[0.0,fpr]))
        out["average_precision"] = float(np.dot(np.diff(np.r_[0.0,tpr]), precision))
        return out


def paired_cluster_uncertainty(panel, left: FrozenScoreMetrics, right: FrozenScoreMetrics, column, replicates=500, seed=20261010):
    codes, groups = pd.factorize(panel[column], sort=True)
    rng = np.random.default_rng(seed)
    draws = {k: [] for k in left.evaluate()}
    for _ in range(replicates):
        counts = rng.multinomial(len(groups), np.full(len(groups), 1.0/len(groups)))
        w = counts[codes]
        a, b = left.evaluate(w), right.evaluate(w)
        for k in draws:
            if np.isfinite(a[k]) and np.isfinite(b[k]):
                draws[k].append(a[k]-b[k])
    a, b = left.evaluate(), right.evaluate()
    return {"resampling_unit": column, "groups": len(groups), "replicates": replicates, "direction": "challenger_minus_full_logistic", "metrics": {k: {"observed_difference": a[k]-b[k], "valid_replicates": len(v), "percentile_95": np.quantile(v, [0.025,0.975]).tolist() if v else None} for k,v in draws.items()},
            "scope": "Separate bank and annual-cohort sensitivity intervals; neither resampling scheme jointly models all dependence or proves prospective reliability."}

