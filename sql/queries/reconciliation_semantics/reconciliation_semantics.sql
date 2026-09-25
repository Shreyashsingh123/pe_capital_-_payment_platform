-- ============================================================================
--  RECONCILIATION SEMANTICS
-- Source: gold schema — PE Fund Capital, Payment & Reconciliation Platform
-- Queries: Q20 – Q22
-- ============================================================================


-- Q20 . Break reason frequency by recon_type
--           Separates expected timing-difference breaks from genuine data breaks
SELECT  recon_type,
        break_reason,
        COUNT(*)  AS occurrence_count
FROM    gold.reconciliation
WHERE   break_reason IS NOT NULL
GROUP BY recon_type, break_reason
ORDER BY recon_type, occurrence_count DESC;


-- Q21 . Tolerance-based reclassification for POSITION rows
--           Rows within 1% of quantity are reclassified as TOLERANCE_MATCH
SELECT  recon_id,
        recon_type,
        business_date,
        fund_id,
        entity_id,
        source_a_numeric        AS ext_quantity,
        source_b_numeric        AS int_quantity,
        difference,
        status                  AS original_status,
        CASE
            WHEN status = 'BREAK'
             AND ABS(difference) <= ABS(source_a_numeric) * 0.01
            THEN 'TOLERANCE_MATCH'
            ELSE status
        END                     AS adjusted_status
FROM    gold.reconciliation
WHERE   recon_type = 'POSITION'
ORDER BY adjusted_status, ABS(difference) DESC;


-- Q22 . Defect / RCA log — all BREAK rows with full "steps to reproduce" fields
SELECT  recon_id,
        recon_type,
        business_date,
        fund_id,
        entity_id,
        source_a_value,
        source_b_value,
        source_a_numeric,
        source_b_numeric,
        difference,
        break_reason,
        created_at
FROM    gold.reconciliation
WHERE   status = 'BREAK'
ORDER BY recon_type, business_date, ABS(difference) DESC;
