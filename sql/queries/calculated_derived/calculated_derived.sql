-- ============================================================================
-- D. CALCULATED / DERIVED LOGIC
-- Source: gold schema — PE Fund Capital, Payment & Reconciliation Platform
-- Queries: Q14 – Q16
-- ============================================================================


-- Q14 (D1). Percent-called ratio per fund (uncalled_capital / total_commitments)
SELECT  fund_id,
        fund_name,
        total_commitments,
        uncalled_capital,
        contributions,
        CASE
            WHEN total_commitments = 0 OR total_commitments IS NULL THEN NULL
            ELSE ROUND(
                    (1.0 - uncalled_capital / total_commitments) * 100,
                 2)
        END  AS pct_called
FROM    gold.fund_snapshot
ORDER BY pct_called DESC;


-- Q15 (D2). Integrity check: estimated_nav should equal portfolio_value + available_cash_internal
--           Returns any rows where the equation doesn't hold (should be empty if pipeline is clean)
SELECT  fund_id,
        portfolio_value,
        available_cash_internal,
        estimated_nav,
        (portfolio_value + available_cash_internal)                        AS expected_nav,
        (estimated_nav - (portfolio_value + available_cash_internal))      AS nav_discrepancy
FROM    gold.fund_financials
WHERE   ABS(estimated_nav - (portfolio_value + available_cash_internal)) > 0.01
   OR   estimated_nav IS NULL;


-- Q16 (D3). Flag rows where source values differ but status = MATCH
--           Should return zero rows if the pipeline is consistent
SELECT  recon_id,
        recon_type,
        fund_id,
        entity_id,
        source_a_numeric,
        source_b_numeric,
        difference,
        status
FROM    gold.reconciliation
WHERE   status = 'MATCH'
  AND   source_a_numeric IS NOT NULL
  AND   source_b_numeric IS NOT NULL
  AND   ABS(difference) > 0;
