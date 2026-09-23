-- ============================================================================
-- B. JOINS
-- Source: gold schema — PE Fund Capital, Payment & Reconciliation Platform
-- Queries: Q5 – Q8
-- ============================================================================


-- Q5 (B1). Fund alongside its portfolio companies and each company's market_value
SELECT  fs.fund_id,
        fs.fund_name,
        fs.vintage_year,
        pv.company_id,
        pv.company_name,
        pv.benchmark_ticker,
        pv.market_value
FROM    gold.fund_snapshot       fs
JOIN    gold.portfolio_valuation pv  ON pv.fund_id = fs.fund_id
ORDER BY fs.fund_id, pv.market_value DESC;


-- Q6 (B2). fund_name next to every BREAK reconciliation row (any recon_type)
SELECT  r.recon_id,
        r.recon_type,
        r.business_date,
        fs.fund_id,
        fs.fund_name,
        r.entity_id,
        r.difference,
        r.break_reason,
        r.status
FROM    gold.reconciliation  r
JOIN    gold.fund_snapshot   fs  ON fs.fund_id = r.fund_id
WHERE   r.status = 'BREAK'
ORDER BY r.recon_type, r.business_date;


-- Q7 (B3). Left join portfolio companies to market_price to verify benchmark price history exists
SELECT  pv.company_id,
        pv.company_name,
        pv.benchmark_ticker,
        pv.fund_id,
        COUNT(mp.market_price_id)  AS price_bar_count,
        CASE
            WHEN pv.benchmark_ticker IS NULL     THEN 'NO_BENCHMARK'
            WHEN COUNT(mp.market_price_id) = 0   THEN 'NO_PRICE_HISTORY'
            ELSE 'HAS_PRICE_HISTORY'
        END                        AS price_coverage
FROM    gold.portfolio_valuation  pv
LEFT JOIN gold.market_price       mp  ON mp.ticker = pv.benchmark_ticker
GROUP BY pv.company_id, pv.company_name, pv.benchmark_ticker, pv.fund_id
ORDER BY price_coverage, pv.company_id;


-- Q8 (B4). CAPITAL_CALL payment totals per fund by name — INTERNAL vs EXTERNAL side by side
SELECT  fs.fund_id,
        fs.fund_name,
        ps.payment_type,
        ps.source_side,
        ps.total_amount,
        ps.payment_count
FROM    gold.payment_summary  ps
JOIN    gold.fund_snapshot    fs  ON fs.fund_id = ps.fund_id
WHERE   ps.payment_type = 'CAPITAL_CALL'
ORDER BY fs.fund_name, ps.source_side;
