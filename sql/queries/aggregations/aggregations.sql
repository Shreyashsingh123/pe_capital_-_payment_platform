-- ============================================================================
-- AGGREGATIONS
-- Source: gold schema — PE Fund Capital, Payment & Reconciliation Platform
-- Queries: Q9 – Q13
-- ============================================================================


-- Q9 . Total estimated_nav across all funds
SELECT  SUM(estimated_nav)  AS total_estimated_nav
FROM    gold.fund_financials;


-- Q10 . Total amount by payment_type and source_side
--           (surfaces that EXPENSE and DISTRIBUTION only have EXTERNAL rows)
SELECT  payment_type,
        source_side,
        SUM(total_amount)   AS sum_total_amount,
        SUM(payment_count)  AS sum_payment_count
FROM    gold.payment_summary
GROUP BY payment_type, source_side
ORDER BY payment_type, source_side;


-- Q11 . Reconciliation row counts grouped by recon_type and status
--           Expected: CASH 3 BREAK/2 MISSING_EXTERNAL; POSITION 2 BREAK/1 MATCH/29 MISSING_EXTERNAL;
--                     REFERENCE 1 BREAK/17 MISSING_EXTERNAL
SELECT  recon_type,
        status,
        COUNT(*)  AS row_count
FROM    gold.reconciliation
GROUP BY recon_type, status
ORDER BY recon_type, status;


-- Q12 . Average failure_rate per source_name (NULLs excluded automatically by AVG)
SELECT  source_name,
        COUNT(*)              AS dq_checks,
        AVG(failure_rate)     AS avg_failure_rate,
        MAX(failure_rate)     AS max_failure_rate
FROM    gold.data_quality
WHERE   failure_rate IS NOT NULL
GROUP BY source_name
ORDER BY avg_failure_rate DESC;


-- Q13 . Price bar count per ticker — identifies tickers shared by multiple companies (fan-out)
SELECT  ticker,
        COUNT(*)                        AS total_rows,         -- includes fan-out duplicates
        COUNT(DISTINCT bar_timestamp)   AS distinct_bars,
        COUNT(DISTINCT company_id)      AS company_count
FROM    gold.market_price
GROUP BY ticker
ORDER BY total_rows DESC;   -- GOOGL will rank highest
