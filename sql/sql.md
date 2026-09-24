# SQL — PE Fund Capital, Payment & Reconciliation Platform

All SQL targets **Azure SQL** and is organised into five folders: `control`,
`ddl`, `queries`, `reference`, and `stored_procedure`. The `gold` schema is the
serving layer populated by Databricks Gold notebooks and consumed by Power BI.

---

## Folder structure

```
sql/
├── control/
│   ├── control_tables.sql          # control schema DDL + seed data
│   └── adf_grant_access.sql        # ADF & user permission grants
├── ddl/
│   └── ddl_gold_schema.sql         # CREATE TABLE for all 7 gold tables + indexes
├── queries/
│   ├── filtering_basic_selects/
│   │   └── filtering_basic_selects.sql   # Q1 – Q4
│   ├── joins/
│   │   └── joins.sql                     # Q5 – Q8
│   ├── aggregations/
│   │   └── aggregations.sql              # Q9 – Q13
│   ├── calculated_derived/
│   │   └── calculated_derived.sql        # Q14 – Q16
│   ├── window_functions/
│   │   └── window_functions.sql          # Q17 – Q19
│   └── reconciliation_semantics/
│       └── reconciliation_semantics.sql  # Q20 – Q22
├── reference/
│   └── crosswalk_tables.sql        # staging schema + fund/asset ID crosswalk tables
└── stored_procedure/
    └── audit_procedure.sql         # usp_AuditStart / usp_AuditComplete
```

---

## control/control_tables.sql

Creates the `control` schema with two tables and seeds `etl_metadata`.

### `control.etl_metadata`

Stores one row per data source — used by ADF to discover what to load and how.

| Column | Type | Description |
|---|---|---|
| `source_id` | BIGINT (PK) | Surrogate key |
| `source_name` | VARCHAR(100) | Source identifier (e.g. `fund`, `market_price`) |
| `source_type` | VARCHAR(50) | Always `FILE` in this project |
| `landing_path` | VARCHAR(500) | ADLS path under the bronze container |
| `load_type` | VARCHAR(20) | `FULL` or `INCREMENTAL` |
| `watermark_column` | VARCHAR(100) | Column used for incremental loads (`bar_timestamp`, `event_date`); NULL for FULL loads |
| `last_watermark_value` | DATETIME2 | Updated after each successful incremental run |
| `is_active` | BIT | Set to 0 to disable a source without deleting it |

Seeded sources:

| source_name | load_type | watermark_column |
|---|---|---|
| `market_price` | INCREMENTAL | `bar_timestamp` |
| `payment` | INCREMENTAL | `event_date` |
| `investor` | FULL | — |
| `fund` | FULL | — |
| `commitment` | FULL | — |
| `portfolio_company` | FULL | — |
| `external_position` | FULL | — |
| `external_cash` | FULL | — |
| `external_reference` | FULL | — |
| `external_payment` | FULL | — |

### `control.pipeline_audit`

One row per ADF pipeline run — written by the audit stored procedures.

| Column | Type | Description |
|---|---|---|
| `audit_id` | BIGINT (PK) | Surrogate key |
| `run_id` | UNIQUEIDENTIFIER | ADF run ID passed in as a parameter |
| `pipeline_name` | VARCHAR(200) | ADF pipeline name |
| `source_name` | VARCHAR(100) | Source being processed (nullable) |
| `start_time` | DATETIME2 | Set by `usp_AuditStart` |
| `end_time` | DATETIME2 | Set by `usp_AuditComplete` |
| `status` | VARCHAR(20) | `RUNNING` → `SUCCESS` or `FAILED` |
| `records_read` | INT | Row count from source |
| `records_written` | INT | Row count written to destination |
| `error_message` | VARCHAR(MAX) | Populated only on failure |

---

## control/adf_grant_access.sql

Grants the ADF managed identity and a named user the roles required to
read/write/create objects in Azure SQL. Replace the placeholders before
running.

```sql
-- ADF managed identity
CREATE USER [your-adf-resource-name] FROM EXTERNAL PROVIDER;
ALTER ROLE db_ddladmin  ADD MEMBER [your-adf-resource-name];
ALTER ROLE db_datawriter ADD MEMBER [your-adf-resource-name];
ALTER ROLE db_datareader ADD MEMBER [your-adf-resource-name];

-- Developer / analyst user
CREATE USER [your-email-address] FROM EXTERNAL PROVIDER;
ALTER ROLE db_ddladmin  ADD MEMBER [your-email-address];
ALTER ROLE db_datawriter ADD MEMBER [your-email-address];
ALTER ROLE db_datareader ADD MEMBER [your-email-address];
```

> Requires Azure AD authentication on the SQL server and the caller must have
> `ALTER ANY USER` permission.

---

## ddl/ddl_gold_schema.sql

Creates the `gold` schema and all 7 serving-layer tables, plus 6 indexes
tuned for Power BI query patterns.

### Tables

| Table | Grain | Primary Key | Notes |
|---|---|---|---|
| `gold.fund_snapshot` | Fund | `fund_id` | Denormalised: fund metadata + financial metrics in one row |
| `gold.fund_financials` | Fund | `fund_id` | Financial metrics only: commitments, contributions, uncalled capital, NAV |
| `gold.portfolio_valuation` | Portfolio company | `company_id` | `market_value = latest_close × quantity`; flags `has_benchmark`, `has_position` |
| `gold.reconciliation` | Recon check | `recon_id` | Types: CASH / POSITION / REFERENCE. Status: MATCH / BREAK / MISSING_EXTERNAL |
| `gold.payment_summary` | Fund × payment type × source side | `(fund_id, payment_type, source_side)` | Aggregated totals; `source_side` = INTERNAL or EXTERNAL |
| `gold.data_quality` | DQ log entry | `dq_log_id` (IDENTITY) | Every `log_dq()` call from Databricks notebooks 01–14; includes `failure_rate` |
| `gold.market_price` | Price bar | `market_price_id` (IDENTITY) | 271 rows; enriched with `company_id`/`fund_id`; `(ticker, bar_timestamp)` NOT unique due to ticker fan-out |

### Indexes

| Index | Table | Columns | Purpose |
|---|---|---|---|
| `IX_market_price_ticker_ts` | `market_price` | `ticker, bar_timestamp` | Time-series filtering per ticker |
| `IX_reconciliation_fund_type_status` | `reconciliation` | `fund_id, recon_type, status` | Recon matrix slicing |
| `IX_portfolio_valuation_fund` | `portfolio_valuation` | `fund_id` | Fund-level portfolio drill-down |
| `IX_payment_summary_fund` | `payment_summary` | `fund_id` | Payment aggregation by fund |
| `IX_market_price_fund` | `market_price` | `fund_id` WHERE NOT NULL | Filtered index for fund-linked price rows |
| `IX_data_quality_source_date` | `data_quality` | `source_name, business_date` | DQ trend queries |

---

## reference/crosswalk_tables.sql

Creates the `staging` schema and two crosswalk tables that map external `.dat`
identifiers to internal Faker-generated identifiers. Safe to re-run — uses
existence checks before creating or seeding.

### `staging.fund_id_mapping`

| external_fund_id | internal_fund_id |
|---|---|
| FND001 | FUND_001 |
| FND002 | FUND_002 |
| FND003 | FUND_003 |

### `staging.asset_id_mapping`

| external_asset_id | external_asset_name | internal_company_id |
|---|---|---|
| AST001 | ALPHACO | PORT_0001 |
| AST002 | BETATECH | PORT_0002 |
| AST003 | GAMMAIND | PORT_0003 |
| AST004 | DELTAENERGY | PORT_0004 |
| AST005 | EPSILONHC | PORT_0005 |
| AST006 | ZETALOG | PORT_0006 |
| AST007 | THETAMOB | PORT_0007 |

These crosswalk tables are read by Databricks Silver notebooks
(`07`–`10`) via Lakehouse Federation to resolve external IDs before
writing to Silver Delta tables.

---

## stored_procedure/audit_procedure.sql

Two procedures that write to `control.pipeline_audit`, called by ADF
activities at the start and end of each pipeline run.

### `control.usp_AuditStart`

| Parameter | Type | Required | Description |
|---|---|---|---|
| `@run_id` | UNIQUEIDENTIFIER | Yes | ADF pipeline run ID |
| `@pipeline_name` | VARCHAR(200) | Yes | Name of the ADF pipeline |
| `@source_name` | VARCHAR(100) | No | Source being processed |

Inserts a new row with `status = 'RUNNING'` and `start_time = SYSUTCDATETIME()`.

### `control.usp_AuditComplete`

| Parameter | Type | Required | Description |
|---|---|---|---|
| `@run_id` | UNIQUEIDENTIFIER | Yes | Matches the row written by `usp_AuditStart` |
| `@status` | VARCHAR(20) | Yes | `SUCCESS` or `FAILED` |
| `@records_read` | INT | No | Row count from source |
| `@records_written` | INT | No | Row count written |
| `@error_message` | VARCHAR(MAX) | No | Error detail on failure |

Updates the matching row with `end_time`, final `status`, counts, and any
error message.

---

## queries/ — full reference (Q1–Q22)

All queries target the `gold` schema.

### A. Filtering & Basic Selects — Q1–Q4
File: `queries/filtering_basic_selects/filtering_basic_selects.sql`

| # | Query | Table | What it returns |
|---|---|---|---|
| Q1 | All funds by vintage year | `fund_snapshot` | `fund_id`, `fund_name`, `vintage_year`, `fund_size_usd` — newest first |
| Q2 | CASH reconciliation BREAKs | `reconciliation` | All columns where `recon_type = CASH` and `status = BREAK` |
| Q3 | Partial-match portfolio companies | `portfolio_valuation` | Has benchmark but no position, or has position but no benchmark |
| Q4 | DQ failures with a reason code | `data_quality` | `reason_code IS NOT NULL` and `failure_rate > 0`; dates cast from NVARCHAR |

### B. Joins — Q5–Q8
File: `queries/joins/joins.sql`

| # | Query | Tables | What it returns |
|---|---|---|---|
| Q5 | Fund + portfolio companies + market value | `fund_snapshot` ⋈ `portfolio_valuation` | Every company under each fund with its `market_value` |
| Q6 | Fund name alongside BREAK recon rows | `reconciliation` ⋈ `fund_snapshot` | BREAK rows enriched with `fund_name` |
| Q7 | Portfolio companies vs price history coverage | `portfolio_valuation` ⟕ `market_price` | `price_coverage` flag: NO_BENCHMARK / NO_PRICE_HISTORY / HAS_PRICE_HISTORY |
| Q8 | CAPITAL_CALL totals per fund, INTERNAL vs EXTERNAL | `payment_summary` ⋈ `fund_snapshot` | Side-by-side amounts for capital call reconciliation |

### C. Aggregations — Q9–Q13
File: `queries/aggregations/aggregations.sql`

| # | Query | Table | What it returns |
|---|---|---|---|
| Q9 | Total estimated NAV | `fund_financials` | Single scalar: `SUM(estimated_nav)` |
| Q10 | Payment totals by type and source side | `payment_summary` | `sum_total_amount`, `sum_payment_count` — EXPENSE/DISTRIBUTION are EXTERNAL-only |
| Q11 | Recon row counts by type and status | `reconciliation` | Expected: CASH 3B/2ME; POSITION 2B/1M/29ME; REFERENCE 1B/17ME |
| Q12 | Avg DQ failure rate per source | `data_quality` | `avg_failure_rate`, `max_failure_rate` per source — worst first |
| Q13 | Price bar count per ticker | `market_price` | `total_rows`, `distinct_bars`, `company_count` — GOOGL ranks highest (fan-out) |

### D. Calculated / Derived — Q14–Q16
File: `queries/calculated_derived/calculated_derived.sql`

| # | Query | Table | What it returns |
|---|---|---|---|
| Q14 | Percent-called ratio per fund | `fund_snapshot` | `pct_called = (1 − uncalled / commitments) × 100`; NULL-safe |
| Q15 | NAV integrity check | `fund_financials` | Rows where `estimated_nav ≠ portfolio_value + available_cash_internal` (should be empty) |
| Q16 | MATCH rows with non-zero difference | `reconciliation` | Rows marked MATCH but `ABS(difference) > 0` — should always be empty |

### E. Window Functions — Q17–Q19
File: `queries/window_functions/window_functions.sql`

| # | Query | Table | What it returns |
|---|---|---|---|
| Q17 | Latest price bar per ticker | `market_price` | `ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY bar_timestamp DESC)` — one row per ticker |
| Q18 | Portfolio companies ranked by market value within fund | `portfolio_valuation` | `RANK() OVER (PARTITION BY fund_id ORDER BY market_value DESC)` |
| Q19 | Status % distribution per recon type | `reconciliation` | `pct_of_type` computed with `COUNT(*) OVER (PARTITION BY recon_type)` |

### F. Reconciliation Semantics — Q20–Q22
File: `queries/reconciliation_semantics/reconciliation_semantics.sql`

| # | Query | Table | What it returns |
|---|---|---|---|
| Q20 | Break reason frequency by recon type | `reconciliation` | How often each `break_reason` appears per `recon_type` |
| Q21 | Tolerance-based reclassification for POSITION | `reconciliation` | BREAK rows within 1% of quantity reclassified as `TOLERANCE_MATCH` |
| Q22 | Defect / RCA log — all BREAK rows | `reconciliation` | Full detail for every BREAK: both source values, difference, reason, timestamp |

---

## Design notes

- `business_date` and `created_at` in `gold.data_quality` are stored as
  `NVARCHAR` (passed through from the Databricks DQ log). Cast explicitly
  before sorting or filtering by date (see Q4).
- `gold.market_price` uses a surrogate key (`market_price_id`) because
  `(ticker, bar_timestamp)` is not unique — 6 tickers including `GOOGL` map to
  more than one company, causing fan-out when joining to `portfolio_valuation`.
- CASH reconciliation **cannot structurally produce a MATCH** — internal cash
  is a cumulative net-capital figure, external cash is a point-in-time bank
  balance. This is an accepted definitional limitation, not a bug.
- The `staging` crosswalk tables are created and seeded by
  `reference/crosswalk_tables.sql` and are read by Databricks via Lakehouse
  Federation — do not drop or truncate them without also updating the Silver
  notebooks.
