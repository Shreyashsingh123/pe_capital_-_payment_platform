-- ============================================================================
--  FILTERING & BASIC SELECTS
-- Source: gold schema — PE Fund Capital, Payment & Reconciliation Platform
-- Queries: Q1 – Q4
-- ============================================================================


-- Q1 . All funds ordered by vintage_year descending
SELECT  fund_id,
        fund_name,
        vintage_year,
        fund_size_usd
FROM    gold.fund_snapshot
ORDER BY vintage_year DESC;


-- Q2 . CASH reconciliation rows that are BREAKs
SELECT  *
FROM    gold.reconciliation
WHERE   recon_type = 'CASH'
  AND   status     = 'BREAK';


-- Q3 . Partial-match companies: has_benchmark=1 but no position, OR has_position=1 but no benchmark
SELECT  company_id,
        company_name,
        fund_id,
        benchmark_ticker,
        has_benchmark,
        has_position
FROM    gold.portfolio_valuation
WHERE   (has_benchmark = 1 AND has_position = 0)
   OR   (has_position  = 1 AND has_benchmark = 0);


-- Q4 . DQ rows with a failure reason and failure_rate > 0
--          business_date and created_at are ISO-8601 text — cast before sorting by date
SELECT  source_name,
        CAST(business_date AS DATE)      AS business_date,
        rule_name,
        reason_code,
        records_checked,
        records_failed,
        failure_rate,
        CAST(created_at AS DATETIME2)    AS created_at
FROM    gold.data_quality
WHERE   reason_code IS NOT NULL
  AND   failure_rate > 0
ORDER BY CAST(business_date AS DATE) DESC;
