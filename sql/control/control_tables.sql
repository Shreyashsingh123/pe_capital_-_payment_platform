CREATE SCHEMA control;

CREATE TABLE control.etl_metadata (
    source_id INT IDENTITY PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    landing_path VARCHAR(500) NOT NULL,
    load_type VARCHAR(20) NOT NULL,
    watermark_column VARCHAR(100) NULL,
    last_watermark_value DATETIME2 NULL,
    is_active BIT NOT NULL DEFAULT 1,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

-- Pipeline run audit — one row per run, updated as it progresses
CREATE TABLE control.pipeline_audit (
    audit_id BIGINT IDENTITY PRIMARY KEY,
    run_id UNIQUEIDENTIFIER NOT NULL,
    pipeline_name VARCHAR(200) NOT NULL,
    source_name VARCHAR(100) NULL,
    start_time DATETIME2 NOT NULL,
    end_time DATETIME2 NULL,
    status VARCHAR(20) NOT NULL,
    records_read INT NULL,
    records_written INT NULL,
    error_message VARCHAR(MAX) NULL
);

-- Seed data: one row per source
INSERT INTO control.etl_metadata (source_name, source_type, landing_path, load_type, watermark_column, is_active)
VALUES
    ('market_price', 'FILE', 'market_price/', 'INCREMENTAL', 'bar_timestamp', 1),
    ('investor', 'FILE', 'investor/', 'FULL', NULL, 1),
    ('fund', 'FILE', 'fund/', 'FULL', NULL, 1),
    ('commitment', 'FILE', 'commitment/', 'FULL', NULL, 1),
    ('portfolio_company', 'FILE', 'portfolio_company/', 'FULL', NULL, 1),
    ('payment', 'FILE', 'payment/', 'INCREMENTAL', 'event_date', 1),
    ('external_position', 'FILE', 'external_dat/position/', 'FULL', NULL, 1),
    ('external_cash', 'FILE', 'external_dat/cash/', 'FULL', NULL, 1),
    ('external_reference', 'FILE', 'external_dat/reference/', 'FULL', NULL, 1),
    ('external_payment', 'FILE', 'external_dat/payment/', 'FULL', NULL, 1);
