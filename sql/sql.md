# SQL — PE Fund Capital, Payment & Reconciliation Platform

All SQL targets the **`gold` schema** in Azure SQL, which is the serving layer
populated by the Databricks Gold notebooks. Queries are grouped into five
categories across 22 numbered questions (Q1–Q22).

---

## Folder structure

```
sql/
├── ddl/
│   └── ddl_gold_schema.sql          # CREATE TABLE statements for all 7 gold tables
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
├── control/                         # Pipeline control / audit tables
├── reference/                       # Reference / lookup tables
└── stored_procedure/                # Stored procedures
```

---

## Gold schema — tables

Defined in `ddl/ddl_gold_schema.sql`.

| Table | Grain | Key columns | Notes |
|---|---|---|---|
| `gold.fund_snapshot` | Fund | `fund_id` | Denormalised view: fund metadata + financial metrics in one row |
| `gold.fund_financials` | Fund | `fund_id` | Pure financial metrics: commitments, contributions, uncalled capital, NAV |
| `gold.portfolio_valuation` | Portfolio company | `company_id` | `market_value = latest_close × quantity`; flags `has_benchmark`, `has_position` |
| `gold.reconciliation` | Recon check | `recon_id` | Three types: CASH, POSITION, REFERENCE. Status: MATCH / BREAK / MISSING_EXTERNAL |
| `gold.payment_summary` | Fund × payment type × source side | `(fund_id, payment_type, source_side)` | Aggregated totals; `source_side` = INTERNAL or EXTERNAL |
| `gold.data_quality` | DQ log entry | `dq_log_id` (surrogate) | Every `log_dq()` call from notebooks 01–14; includes `failure_rate` |
| `gold.market_price` | Price bar | `market_price_id` (surrogate) | 271 rows; enriched with `company_id`/`fund_id`; `(ticker, bar_timestamp)` is NOT unique due to ticker fan-out |

Indexes created for Power BI query performance:

```sql
IX_market_price_ticker_ts          ON gold.market_price (ticker, bar_timestamp)
IX_reconciliation_fund_type_status ON gold.reconciliation (fund_id, recon_type, status)
IX_portfolio_valuation_fund        ON gold.portfolio_valuation (fund_id)
IX_payment_summary_fund            ON gold.payment_summary (fund_id)
IX_market_price_fund               ON gold.market_price (fund_id) WHERE fund_id IS NOT NULL
IX_data_quality_source_date        ON gold.data_quality (source_name, business_date)
```

---

## Query reference

### A. Filtering & Basic Selects — Q1–Q4

File: `queries/filtering_basic_selects/filtering_basic_selects.sql`

| # | Query | Table(s) | What it returns |
|---|---|---|---|
| Q1 | All funds ordered by vintage year | `fund_snapshot` | `fund_id`, `fund_name`, `vintage_year`, `fund_size_usd` — newest first |
| Q2 | CASH reconciliation BREAKs | `reconciliation` | All columns for rows where `recon_type = CASH` and `status = BREAK` |
| Q3 | Partial-match portfolio companies | `portfolio_valuation` | Companies that have a benchmark but no position, or a position but no benchmark |
| Q4 | DQ failures with a reason code | `data_quality` | Rows where `reason_code IS NOT NULL` and `failure_rate > 0`; `business_date` / `created_at` cast from text |

---

### B. Joins — Q5–Q8

File: `queries/joins/joins.sql`

| # | Query | Table(s) | What it returns |
|---|---|---|---|
| Q5 | Fund + portfolio companies + market value | `fund_snapshot` ⋈ `portfolio_valuation` | Every company under each fund with its `market_value` |
| Q6 | Fund name alongside BREAK recon rows | `reconciliation` ⋈ `fund_snapshot` | BREAK rows enriched with `fund_name` |
| Q7 | Portfolio companies vs price history coverage | `portfolio_valuation` ⟕ `market_price` | `price_coverage` flag: NO_BENCHMARK / NO_PRICE_HISTORY / HAS_PRICE_HISTORY |
| Q8 | CAPITAL_CALL totals per fund, INTERNAL vs EXTERNAL | `payment_summary` ⋈ `fund_snapshot` | Side-by-side amounts for capital call reconciliation |

---

### C. Aggregations — Q9–Q13

File: `queries/aggregations/aggregations.sql`

| # | Query | Table(s) | What it returns |
|---|---|---|---|
| Q9 | Total estimated NAV across all funds | `fund_financials` | Single scalar: `SUM(estimated_nav)` |
| Q10 | Payment totals by type and source side | `payment_summary` | `sum_total_amount` and `sum_payment_count` — surfaces that EXPENSE / DISTRIBUTION are EXTERNAL-only |
| Q11 | Reconciliation row counts by type and status | `reconciliation` | Expected breakdown: CASH 3 BREAK / 2 MISSING_EXT; POSITION 2 BREAK / 1 MATCH / 29 MISSING_EXT; REFERENCE 1 BREAK / 17 MISSING_EXT |
| Q12 | Average DQ failure rate per source | `data_quality` | `avg_failure_rate` and `max_failure_rate` per source, ordered worst first |
| Q13 | Price bar count per ticker | `market_price` | `total_rows`, `distinct_bars`, `company_count` — GOOGL ranks highest due to ticker fan-out |

---

### D. Calculated / Derived — Q14–Q16

File: `queries/calculated_derived/calculated_derived.sql`

| # | Query | Table(s) | What it returns |
|---|---|---|---|
| Q14 | Percent-called ratio per fund | `fund_snapshot` | `pct_called = (1 − uncalled_capital / total_commitments) × 100`; NULL-safe |
| Q15 | NAV integrity check | `fund_financials` | Rows where `estimated_nav ≠ portfolio_value + available_cash_internal` (should be empty in a clean run) |
| Q16 | MATCH rows with non-zero difference | `reconciliation` | Rows marked MATCH but with `ABS(difference) > 0` — should always be empty |

---

### E. Window Functions / Advanced — Q17–Q19

File: `queries/window_functions/window_functions.sql`

| # | Query | Table(s) | What it returns |
|---|---|---|---|
| Q17 | Latest price bar per ticker | `market_price` | `ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY bar_timestamp DESC)` — one row per ticker |
| Q18 | Portfolio companies ranked by market value within fund | `portfolio_valuation` | `RANK() OVER (PARTITION BY fund_id ORDER BY market_value DESC)` |
| Q19 | Status percentage distribution per recon type | `reconciliation` | `COUNT(*) OVER (PARTITION BY recon_type)` used to compute `pct_of_type` |

---

### F. Reconciliation Semantics — Q20–Q22

File: `queries/reconciliation_semantics/reconciliation_semantics.sql`

| # | Query | Table(s) | What it returns |
|---|---|---|---|
| Q20 | Break reason frequency by recon type | `reconciliation` | How often each `break_reason` appears per `recon_type` |
| Q21 | Tolerance-based reclassification for POSITION | `reconciliation` | BREAK rows within 1% of quantity reclassified as TOLERANCE_MATCH |
| Q22 | Defect / RCA log — all BREAK rows | `reconciliation` | Full detail for every BREAK: both source values, difference, reason, timestamp |

---

## Design notes

- `business_date` and `created_at` in `gold.data_quality` are stored as
  `NVARCHAR` (passed through from the Databricks DQ log). Cast explicitly
  before sorting or filtering by date (see Q4).
- `gold.market_price` uses a surrogate key (`market_price_id`) because
  `(ticker, bar_timestamp)` is not unique — 6 tickers including `GOOGL` map
  to more than one company, causing a fan-out when joining to
  `portfolio_valuation`.
- CASH reconciliation **cannot structurally produce a MATCH** — internal cash
  is a cumulative net-capital figure, external cash is a point-in-time bank
  balance. This is an accepted definitional limitation, not a bug.
