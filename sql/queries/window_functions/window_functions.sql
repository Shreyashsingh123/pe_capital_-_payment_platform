-- ============================================================================
-- E. WINDOW FUNCTIONS / ADVANCED
-- Source: gold schema — PE Fund Capital, Payment & Reconciliation Platform
-- Queries: Q17 – Q19
-- ============================================================================


-- Q17 (E1). Latest price bar per ticker using ROW_NUMBER()
WITH ranked AS (
    SELECT  *,
            ROW_NUMBER() OVER (
                PARTITION BY ticker
                ORDER BY bar_timestamp DESC
            ) AS rn
    FROM    gold.market_price
)
SELECT  ticker,
        bar_timestamp,
        [open],
        high,
        low,
        [close],
        volume,
        company_id,
        fund_id
FROM    ranked
WHERE   rn = 1
ORDER BY ticker;


-- Q18 (E2). Rank portfolio companies within each fund by market_value descending
SELECT  fund_id,
        company_id,
        company_name,
        benchmark_ticker,
        market_value,
        RANK() OVER (
            PARTITION BY fund_id
            ORDER BY market_value DESC
        ) AS value_rank
FROM    gold.portfolio_valuation
ORDER BY fund_id, value_rank;


-- Q19 (E3). Percentage of each status out of all rows per recon_type
SELECT  recon_type,
        status,
        COUNT(*)                                          AS status_count,
        COUNT(*) OVER (PARTITION BY recon_type)           AS type_total,
        ROUND(
            100.0 * COUNT(*) /
            COUNT(*) OVER (PARTITION BY recon_type),
        2)                                                AS pct_of_type
FROM    gold.reconciliation
GROUP BY recon_type, status
ORDER BY recon_type, status;
