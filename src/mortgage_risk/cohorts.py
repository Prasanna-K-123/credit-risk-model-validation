"""Historical feature snapshots and explicitly censored 12-month labels."""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import sqlite3

from .schema import add_months, month_index

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Outcome:
    value: int | None
    reason: str
    observed_months: int


def outcome_12m(records, as_of: int) -> Outcome:
    """Any reported 90+ day/REO/foreclosure event in the next twelve months.

    A voluntary payoff is a competing exit. A sale, RPL transfer or defect
    without a preceding distress event is unresolved, never a healthy label.
    Unknown or missing observations cannot establish a negative outcome.
    A documented positive remains known even if earlier follow-up was incomplete.
    """
    horizon = add_months(as_of, 12)
    ordered = sorted((int(p), str(dq), str(z)) for p, dq, z in records if as_of < int(p) <= horizon)
    if len({r[0] for r in ordered}) != len(ordered):
        raise ValueError("Duplicate month in label window")
    expected = add_months(as_of, 1)
    uncertain = False
    seen = 0
    for period, dq, exit_code in ordered:
        month_index(period)
        if period != expected:
            uncertain = True
        expected = add_months(period, 1)
        seen += 1
        numeric = len(dq) == 2 and dq.isdigit()
        if dq == "RA" or (numeric and int(dq) >= 3) or exit_code in {"02", "03", "09"}:
            return Outcome(1, "reported_credit_distress", seen)
        if not numeric:
            uncertain = True
        if exit_code == "01":
            return Outcome(None if uncertain else 0,
                           "unresolved_before_payoff" if uncertain else "voluntary_payoff_competing", seen)
        if exit_code in {"15", "16", "96"}:
            return Outcome(None, "transfer_or_defect_censored", seen)
        if exit_code:
            raise ValueError("Unrecognized exit code")
    if seen == 12 and not uncertain and ordered[-1][0] == horizon:
        return Outcome(0, "observed_event_free_12m", seen)
    return Outcome(None, "incomplete_or_unknown_followup", seen)


def snapshot_rows(conn: sqlite3.Connection, as_of: int) -> list[dict]:
    query = (ROOT / "sql" / "snapshot.sql").read_text()
    cursor = conn.execute(query, {"as_of": as_of, "lookback_start": add_months(as_of, -5)})
    names = [d[0] for d in cursor.description]
    rows = []
    sentinels = {"fico": "9999", "dti": "999", "ltv": "999", "cltv": "999", "mi_pct": "999"}
    string_fields = {"loan_id", "purpose", "occupancy", "property_type", "relief_refinance"}
    for raw in cursor:
        item = dict(zip(names, raw))
        item["calendar_age"] = month_index(as_of) - month_index(item.pop("first_payment_date")) + 1
        for key in list(item):
            if key in string_fields:
                if key != "loan_id" and item[key] in {"", "9", "99"}:
                    item[key] = "MISSING"
                continue
            if item[key] in {None, ""} or (key in sentinels and item[key] == sentinels[key]):
                item[key] = None
            else:
                item[key] = float(item[key])
                if not math.isfinite(item[key]):
                    raise ValueError("Non-finite snapshot feature")
        item["log_current_upb"] = math.log1p(item.pop("current_upb"))
        item["log_original_upb"] = math.log1p(item.pop("original_upb"))
        rows.append(item)
    return rows
