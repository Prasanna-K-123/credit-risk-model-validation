"""Ordered Release 47 fields, checked against Freddie Mac's July 2026 headers.

Names below are project identifiers, not a copy of the provider's prose guide.
Never apply these positions to earlier releases without a separate parser.
"""

ORIGINATION = [
    "fico", "first_payment_date", "first_time_buyer", "maturity_date", "msa",
    "mi_pct", "units", "occupancy", "cltv", "dti", "original_upb", "ltv",
    "original_rate", "channel", "prepayment_penalty", "amortization", "state",
    "property_type", "postal_prefix", "loan_id", "purpose", "original_term",
    "borrowers", "seller", "super_conforming", "pre_harp_loan_id", "program",
    "relief_refinance", "valuation_method", "interest_only", "vantage_score",
]
PERFORMANCE = [
    "loan_id", "period", "current_upb", "delinquency", "loan_age", "remaining_term",
    "defect_settlement_date", "modification", "zero_balance_code",
    "zero_balance_date", "current_rate", "non_interest_upb", "last_paid_date",
    "mi_recoveries", "net_sale_proceeds", "non_mi_recoveries", "total_expenses",
    "legal_costs", "maintenance_costs", "taxes_insurance", "misc_expenses",
    "actual_loss", "cumulative_modification_cost", "rate_step", "payment_deferral",
    "estimated_ltv", "removal_upb", "delinquent_interest", "disaster_flag",
    "assistance_plan", "current_modification_cost", "interest_bearing_upb",
    "mi_cancellation", "servicer", "bankruptcy_cramdown",
]

# Data for historical snapshots and prospective label windows. Loss and future
# settlement fields are deliberately absent from the modelling database.
PERFORMANCE_STORED = [
    "loan_id", "period", "current_upb", "delinquency", "loan_age",
    "remaining_term", "modification", "zero_balance_code", "zero_balance_date",
    "current_rate", "non_interest_upb", "payment_deferral", "assistance_plan",
]
PERFORMANCE_POSITIONS = [PERFORMANCE.index(name) for name in PERFORMANCE_STORED]

def month_index(value: str | int) -> int:
    """A calendar index, independent of the provider's resettable loan age."""
    s = str(value)
    if len(s) != 6 or not s.isdigit():
        raise ValueError("Month must have six YYYYMM digits")
    year, month = int(s[:4]), int(s[4:])
    if not 1900 <= year <= 2100 or not 1 <= month <= 12:
        raise ValueError("Invalid calendar month")
    return year * 12 + month - 1

def add_months(value: str | int, months: int) -> int:
    year, month = divmod(month_index(value) + months, 12)
    return year * 100 + month + 1
