
CREATE SCHEMA gold;

-- ============================================================================
-- 1. gold.fund_snapshot
-- ============================================================================
CREATE TABLE gold.fund_snapshot (
    fund_id                     NVARCHAR(50)    NOT NULL,
    fund_name                   NVARCHAR(200)   NULL,
    vintage_year                INT             NULL,
    fund_size_usd               DECIMAL(18,4)   NULL,   
    total_commitments           DECIMAL(18,4)   NULL,
    contributions               DECIMAL(18,4)   NULL,
    uncalled_capital            DECIMAL(18,4)   NULL,
    invested_capital            DECIMAL(18,4)   NULL,
    portfolio_value             DECIMAL(18,4)   NULL,
    available_cash_internal     DECIMAL(18,4)   NULL,
    available_cash_external     DECIMAL(18,4)   NULL,
    estimated_nav               DECIMAL(18,4)   NULL,
    calculated_at               DATETIME2       NULL,
    snapshot_generated_at       DATETIME2       NULL,
    CONSTRAINT PK_fund_snapshot PRIMARY KEY (fund_id)
);



-- ============================================================================
-- 2. gold.fund_financials
-- ============================================================================
CREATE TABLE gold.fund_financials (
    fund_id                     NVARCHAR(50)    NOT NULL,
    total_commitments           DECIMAL(18,4)   NULL,
    contributions               DECIMAL(18,4)   NULL,
    uncalled_capital            DECIMAL(18,4)   NULL,
    invested_capital            DECIMAL(18,4)   NULL,
    portfolio_value             DECIMAL(18,4)   NULL,
    available_cash_internal     DECIMAL(18,4)   NULL,
    available_cash_external     DECIMAL(18,4)   NULL,
    estimated_nav               DECIMAL(18,4)   NULL,
    calculated_at               DATETIME2       NULL,
    gold_loaded_at              DATETIME2       NULL,
    CONSTRAINT PK_fund_financials PRIMARY KEY (fund_id)
);



-- ============================================================================
-- 3. gold.portfolio_valuation
-- ============================================================================
CREATE TABLE gold.portfolio_valuation (
    company_id                  NVARCHAR(50)    NOT NULL,
    company_name                NVARCHAR(200)   NULL,
    fund_id                     NVARCHAR(50)    NULL,
    benchmark_ticker            NVARCHAR(20)    NULL,
    latest_close                DECIMAL(18,4)   NULL,   
    quantity                    DECIMAL(18,4)   NULL,
    market_value                DECIMAL(18,4)   NULL,
    has_benchmark               BIT             NULL,
    has_position                BIT             NULL,
    gold_loaded_at              DATETIME2       NULL,
    CONSTRAINT PK_portfolio_valuation PRIMARY KEY (company_id)
);



-- ============================================================================
-- 4. gold.reconciliation
-- ============================================================================
CREATE TABLE gold.reconciliation (
    recon_id                    NVARCHAR(64)    NOT NULL,
    recon_type                  NVARCHAR(20)    NULL,   
    business_date               DATE            NULL,
    fund_id                     NVARCHAR(50)    NULL,
    entity_id                   NVARCHAR(50)    NULL,   
    source_a_value              NVARCHAR(100)   NULL,
    source_b_value              NVARCHAR(100)   NULL,
    source_a_numeric            DECIMAL(18,4)   NULL,
    source_b_numeric            DECIMAL(18,4)   NULL,
    difference                  DECIMAL(18,4)   NULL,
    status                      NVARCHAR(20)    NULL,   
    break_reason                NVARCHAR(100)   NULL,
    created_at                  DATETIME2       NULL,
    gold_loaded_at              DATETIME2       NULL,
    CONSTRAINT PK_reconciliation PRIMARY KEY (recon_id)
);
GO


-- ============================================================================
-- 5. gold.payment_summary
-- ============================================================================
CREATE TABLE gold.payment_summary (
    fund_id                     NVARCHAR(50)    NOT NULL,
    payment_type                NVARCHAR(30)    NOT NULL,   -- CAPITAL_CALL | CONTRIBUTION | INVESTMENT | EXPENSE | DISTRIBUTION
    source_side                 NVARCHAR(10)    NOT NULL,   -- INTERNAL | EXTERNAL
    total_amount                DECIMAL(18,4)   NULL,
    payment_count               INT             NULL,
    gold_loaded_at              DATETIME2       NULL,
    CONSTRAINT PK_payment_summary PRIMARY KEY (fund_id, payment_type, source_side)
);



-- ============================================================================
-- 6. gold.data_quality
-- ============================================================================
CREATE TABLE gold.data_quality (
    dq_log_id                   INT IDENTITY(1,1) NOT NULL,   
    source_name                 NVARCHAR(50)    NULL,
    business_date               NVARCHAR(10)    NULL,   
    rule_name                   NVARCHAR(50)    NULL,
    records_checked             INT             NULL,
    records_failed              INT             NULL,
    reason_code                 NVARCHAR(50)    NULL,
    failure_rate                DECIMAL(9,6)    NULL,
    created_at                  NVARCHAR(40)    NULL, 
    gold_loaded_at              DATETIME2       NULL,
    CONSTRAINT PK_data_quality PRIMARY KEY (dq_log_id)
);
GO


-- ============================================================================
-- 7. gold.market_price
-- ============================================================================
CREATE TABLE gold.market_price (
    market_price_id             INT IDENTITY(1,1) NOT NULL,   
    ticker                      NVARCHAR(20)    NOT NULL,
    bar_timestamp               DATETIME2       NOT NULL,
    [open]                      DECIMAL(18,4)   NULL,   L
    high                        DECIMAL(18,4)   NULL,
    low                         DECIMAL(18,4)   NULL,
    [close]                     DECIMAL(18,4)   NULL,   
    volume                      BIGINT          NULL,
    company_id                  NVARCHAR(50)    NULL,   
    company_name                NVARCHAR(200)   NULL,
    fund_id                     NVARCHAR(50)    NULL,
    gold_loaded_at              DATETIME2       NULL,
    CONSTRAINT PK_market_price PRIMARY KEY (market_price_id)
);

-- ============================================================================
-- Indexes for Power BI query performance
-- ============================================================================
CREATE INDEX IX_market_price_ticker_ts ON gold.market_price (ticker, bar_timestamp);
CREATE INDEX IX_reconciliation_fund_type_status ON gold.reconciliation (fund_id, recon_type, status);
CREATE INDEX IX_portfolio_valuation_fund        ON gold.portfolio_valuation (fund_id);
CREATE INDEX IX_payment_summary_fund            ON gold.payment_summary (fund_id);
CREATE INDEX IX_market_price_fund               ON gold.market_price (fund_id) WHERE fund_id IS NOT NULL;
CREATE INDEX IX_data_quality_source_date        ON gold.data_quality (source_name, business_date);

