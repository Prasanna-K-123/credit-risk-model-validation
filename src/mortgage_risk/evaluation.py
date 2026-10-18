"""Descriptive diagnostics on frozen probabilities; never updates a model."""
from __future__ import annotations
import math
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logit
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score
from .modelling import SEED


def paired_brier(y, logit_p, hgb_p, replicates=2000):
    delta = (hgb_p-y)**2-(logit_p-y)**2
    rng = np.random.default_rng(SEED)
    means = np.array([delta[rng.integers(0,len(delta),len(delta))].mean()
                      for _ in range(replicates)])
    return {"hgb_minus_logit": float(delta.mean()),
            "paired_percentile_95_interval": np.quantile(means,[.025,.975]).tolist(),
            "replicates": replicates, "resampling_unit": "loan", "seed": SEED}


def calibration(y, p):
    z = logit(np.clip(p,1e-8,1-1e-8))
    design = np.column_stack([np.ones(len(y)),z])
    def objective(beta):
        eta = design@beta
        return float(np.mean(np.logaddexp(0,eta)-y*eta)), design.T@(expit(eta)-y)/len(y)
    fit = minimize(objective, [0.,1.], jac=True, method="L-BFGS-B",
                   options={"maxiter":2000,"ftol":1e-15,"gtol":1e-9})
    ok = bool(fit.success and np.max(np.abs(fit.jac))<1e-5)
    result = {"converged": ok, "gradient_max": float(np.max(np.abs(fit.jac))),
              "intercept": float(fit.x[0]) if ok else None,
              "slope": float(fit.x[1]) if ok else None}
    if ok:
        weights = expit(design@fit.x)*(1-expit(design@fit.x))
        information = (design.T*weights)@design
        try:
            se = np.sqrt(np.diag(np.linalg.inv(information)))
            result["intercept_wald_95"] = (fit.x[0]+np.array([-1,1])*1.96*se[0]).tolist()
            result["slope_wald_95"] = (fit.x[1]+np.array([-1,1])*1.96*se[1]).tolist()
        except np.linalg.LinAlgError:
            result["interval_warning"] = "Singular observed information"
    return result


def metrics(y,p):
    y, p = np.asarray(y,float),np.asarray(p,float)
    clipped = np.clip(p,1e-8,1-1e-8)
    order = np.argsort(p,kind="stable")
    groups = []
    for index in np.array_split(order,10):
        if len(index) >= 30:
            groups.append({"n":len(index),"observed_rate":float(y[index].mean()),
                           "mean_probability":float(p[index].mean()),
                           "event_rate_wilson_95":wilson(int(y[index].sum()),len(index))})
    return {"n_known":len(y),"events":int(y.sum()),"event_rate":float(y.mean()),
            "brier":float(np.mean((p-y)**2)),"log_loss":float(log_loss(y,clipped,labels=[0,1])),
            "roc_auc":float(roc_auc_score(y,p)) if len(np.unique(y))==2 else None,
            "average_precision":float(average_precision_score(y,p)) if y.sum() else None,
            "expected_events":float(p.sum()),
            "observed_expected_ratio":float(y.sum()/p.sum()) if p.sum() else None,
            "calibration":calibration(y,p) if len(np.unique(y))==2 else {"converged":False},
            "equal_count_calibration":groups}


def wilson(events,n):
    z=1.959963984540054
    p=events/n
    center=(p+z*z/(2*n))/(1+z*z/n)
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [center-half,center+half]
