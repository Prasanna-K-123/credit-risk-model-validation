-- Both dates are bound parameters. No future performance row enters a feature.
WITH history AS (
    SELECT loan_id, COUNT(*) AS history_months,
           SUM(CASE WHEN delinquency IN ('RA','XX') THEN 1 ELSE 0 END) AS unknown_history,
           MAX(CASE WHEN delinquency NOT IN ('RA','XX') THEN CAST(delinquency AS INTEGER) END) AS max_dq_6m,
           SUM(CASE WHEN delinquency NOT IN ('RA','XX') AND CAST(delinquency AS INTEGER)>=1 THEN 1 ELSE 0 END) AS dq_months_6m,
           MAX(CASE WHEN period=:lookback_start THEN current_upb END) AS start_upb,
           MAX(CASE WHEN modification IN ('Y','P') THEN 1 ELSE 0 END) AS modified_by_snapshot,
           SUM(CASE WHEN zero_balance_code<>'' THEN 1 ELSE 0 END) AS past_exits
    FROM performance
    WHERE period BETWEEN :lookback_start AND :as_of
    GROUP BY loan_id
)
SELECT o.loan_id, o.fico, o.dti, o.ltv, o.cltv, o.mi_pct, o.original_term,
       o.original_rate, o.original_upb, o.first_payment_date,
       o.purpose, o.occupancy, o.property_type, o.relief_refinance,
       p.current_rate, p.current_upb, CAST(p.delinquency AS INTEGER) AS current_dq,
       h.max_dq_6m, h.dq_months_6m,
       p.current_upb / h.start_upb AS balance_ratio_6m,
       h.modified_by_snapshot
FROM origination o
JOIN performance p ON o.loan_id=p.loan_id AND p.period=:as_of
JOIN history h ON o.loan_id=h.loan_id
WHERE p.delinquency IN ('00','01','02') AND p.current_upb>0
  AND p.zero_balance_code='' AND h.past_exits=0
  AND h.history_months=6 AND h.unknown_history=0 AND h.start_upb>0
  AND CAST(o.first_payment_date AS INTEGER)<=:as_of
ORDER BY o.loan_id;
