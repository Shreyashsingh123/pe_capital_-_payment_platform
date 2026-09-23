# Databricks Notebooks — PE Fund Capital, Payment & Reconciliation Intelligence Platform

Covers Bronze ingestion, Silver (10 sources + 2 incremental), Financial
Calculations, Reconciliation, and Gold (7 tables) — the full build, all of it
done in this scope. Environment: Azure Databricks (serverless), Unity Catalog
`dbw_pe_platform`, storage account `pestorage3`.


## Bronze Layer

| Notebook | Does |
|---|---|
| `bronze_ingestion` | Ingests all 10 sources (6 internal CSV, 4 external pipe-delimited `.dat` feeds) via ADF-driven widget parameters (`source_name`, `folder_path`, `run_id`), writing to `abfss://bronze@pestorage3.dfs.core.windows.net/<source>/`. External `.dat` ingestion includes field-level validation and quarantine (null/invalid/negative-quantity checks) before Silver ever sees the data. Includes unit tests against the pack's known-bad rows (`_run_known_bad_row_tests`). |

## Setup

| Notebook | Does |
|---|---|
| `00_setup_silver_catalog` | Creates the `silver` schema (`MANAGED LOCATION abfss://silver@pestorage3.dfs.core.windows.net/`), pre-creates the shared `dq_log` table, sets up the `azure_sql` foreign catalog via Lakehouse Federation. Confirms all 10 Bronze sources visible before Silver work begins. |
| `silver_common` | Shared utility library, `%run` into every other notebook. Provides `read_bronze`/`read_crosswalk`, `split_on_required_nulls`, `split_duplicates`, `find_business_key_duplicates`, `flag_late`, `flag_day_over_day_change`, `check_foreign_key`, `write_silver`/`write_quarantine`/`write_gold`, `merge_into_silver` (Delta MERGE upsert), `log_dq`. |

## Silver Layer — Bronze → Silver, all 10 sources

Every notebook: type-cast → null-check required fields (quarantine failures) →
duplicate/break detection → FK validation where applicable → write to Silver
→ log to `dq_log` → assert bronze count = silver count + quarantined count.

| # | Notebook | Source | Bronze rows | Silver rows | Quarantined | Notable finding |
|---|---|---|---|---|---|---|
| 01 | `01_silver_fund` | `fund` (internal CSV) | 25 | 5 | 20 | 5× exact-duplicate rows (seeded, intentional — see below) |
| 02 | `02_silver_investor` | `investor` (internal CSV) | 250 | 50 | 200 | Same 5× duplication pattern |
| 03 | `03_silver_commitment` | `commitment` (internal CSV) | 330 | 66 | 264 | Same 5× duplication pattern; first table with FK checks (fund, investor) |
| 04 | `04_silver_portfolio_company` | `portfolio_company` (internal CSV) | 150 | 30 | 120 | Same 5× duplication pattern; 6/30 companies have no `benchmark_ticker` (expected) |
| 05 | `05_silver_payment_csv` | `payment` (internal CSV ledger) | 222 | 222 | 0 | No duplication; 8 `INVESTMENT` rows flagged (not rejected) for missing `company_id`/`entry_benchmark_price` |
| 06 | `06_silver_market_price` | `market_price` (internal CSV) | 205 | 205 | 0 | Clean; no FK check (market data is broader reference data) |
| 07 | `07_silver_external_position` | `external_position` (custodian `.dat`) | 21 | 20 | 1 | Crosswalk join + `POSITION_BREAK` detection: 4 rows flagged, incl. seeded FND002/AST004 conflicting-quantity case |
| 08 | `08_silver_external_cash` | `external_cash` (bank `.dat`) | 10 | 10 | 0 | Crosswalk join + late-record flag: 1 row flagged (`CASH20260917LATE`, ~21:45) |
| 09 | `09_silver_external_reference` | `external_reference` (vendor `.dat`) | 19 | 19 | 0 | Crosswalk join + day-over-day change detection: 2 `REFERENCE_BREAK` rows (seeded AST005 EUR→GBP→EUR flip) |
| 10 | `10_silver_external_payment` | `external_payment` (payment-system `.dat`) | 15 | 15 | 0 | Crosswalk join + exact-duplicate detection on `payment_id` (catches seeded `PMT-DUP-20260917-001`). All statuses loaded; SETTLED-only rule applied downstream |

### `fund`/`investor`/`commitment`/`portfolio_company` 5× duplication — why it isn't a bug

Bronze row count is consistently exactly 5× the deduplicated Silver count
across all four internal dimension/fact CSVs. **Confirmed intentional**:
seeded on purpose to validate the transformation layer's duplicate-detection
logic — correctly caught in all four cases by `split_duplicates`.

## Incremental Processing

| Notebook | Builds | Rows | Notable finding |
|---|---|---|---|
| `11_incremental_payment_lifecycle` | `silver.external_payment_current` | 5 threads | Groups payment events into "threads" via regex on `payment_id` (`^(PMT\d{3})\d{8}(\d{3})?$`), takes latest state per thread by `COALESCE(settlement_timestamp, event_timestamp)`, MERGEs — idempotent, re-run confirmed. **Flag for mentor sign-off:** thread-ID pattern inferred from only 15 rows. |
| `12_incremental_position_cash_reference` | `position_current` (20), `cash_current` (10), `reference_current` (19) | 49 total | Same MERGE-upsert pattern, one section per source, each on its natural business key. **Flag for mentor sign-off:** 2 unresolved `POSITION_BREAK` keys excluded entirely from `position_current` (missing key = "unresolved," not "zero"). Both notebooks re-run to confirm idempotent row counts. |

## Financial Calculations

`13_financial_calculations` — computes fund-level and company-level metrics
from Silver data. Produces `silver.fund_financials` (5 rows, fund grain) and
`silver.portfolio_valuation` (30 rows, company grain).

| Issue | Root cause | Fix |
|---|---|---|
| Portfolio Value understated | Summed raw market price without multiplying by quantity held | Joined `position_current`, computed `latest_close × quantity` |
| Available Cash double-counted | `available_cash_internal` summed Capital Calls (a request) alongside Contributions (actual cash), while Capital Calls were already used correctly elsewhere (Uncalled Capital) | `available_cash_internal = contributions − invested_capital` |

Only 1 of 30 companies (`PORT_0003`/FUND_001) has both a benchmark price and
a position record — the rest correctly show $0 portfolio value given this
project's limited sample data, not a bug.

## Reconciliation

`14_reconciliation` — builds `silver.reconciliation` (55 rows) across three
check types, one shared schema (extends the requirements PDF's Section 7.4
model with an `entity_id` column for asset/company grain — flag for mentor
sign-off).

| Type | Rows | Status breakdown | Notes |
|---|---|---|---|
| CASH | 5 | 3 BREAK, 2 MISSING_EXTERNAL | Compares `fund_financials.available_cash_internal` vs `available_cash_external`. Fixed mid-build: `left` join → `full_outer`, so a fund present only externally would surface as `MISSING_INTERNAL` instead of vanishing silently. Can structurally never MATCH — internal is a cumulative net-capital figure, external is a point-in-time bank balance; different questions by definition. |
| POSITION | 31 | 2 BREAK, 1 MATCH, 29 MISSING_EXTERNAL | Coverage check + re-surfaced `POSITION_BREAK` from `07`. **Flag for mentor sign-off:** no independent internal position-quantity source exists, so this is coverage + internal-consistency, not a true A-vs-B value comparison. |
| REFERENCE | 18 | 1 BREAK, 17 MISSING_EXTERNAL | Coverage check + re-surfaced day-over-day `changed` flag from `09`. |

## Gold Layer

| Notebook | Table | Rows | Built from |
|---|---|---|---|
| `15_gold_core` | `gold.fund_snapshot` | 5 | `fund` + `fund_financials` joined on `fund_id` |
| `15_gold_core` | `gold.fund_financials` | 5 | Pass-through of `silver.fund_financials` |
| `15_gold_core` | `gold.portfolio_valuation` | 30 | Pass-through of `silver.portfolio_valuation` |
| `15_gold_core` | `gold.reconciliation` | 55 | Pass-through of `silver.reconciliation` + `source_a_numeric`/`source_b_numeric` (via `try_cast`) for Power BI charting |
| `16_gold_payments_dq` | `gold.payment_summary` | — | Internal (`silver.payment`) and external (`silver.external_payment_current`) totals per `(fund_id, payment_type)`, tagged `source_side`, not blended |
| `16_gold_payments_dq` | `gold.data_quality` | — | Pass-through of `dq_log` (every `log_dq()` call, 01–14) + computed `failure_rate` |
| `17_gold_market_price` | `gold.market_price` | 271 | All 205 raw price bars from `silver.market_price`, left-enriched with `company_id`/`company_name`/`fund_id`. **Extra table, beyond original 6-table scope.** 6 tickers (incl. `GOOGL`) map to more than one company, so the join fans out — `(ticker, bar_timestamp)` is not unique; downstream Azure SQL uses a surrogate key instead. |

## Bugs found & fixed along the way

| Issue | Root cause | Fix |
|---|---|---|
| `check_foreign_key`/`merge_into_silver` silently broken in `silver_common` | `check_foreign_key`'s `def` line was accidentally deleted during a later edit, orphaning its body inside `merge_into_silver` | Found and fixed twice (once in an earlier session, re-confirmed here); verified |
| `15_gold_core` cells threw `SyntaxError` on import | Notebook-generation script joined multi-line cell source without newline characters, flattening several statements onto one line | Fixed generator to preserve newlines (`splitlines(keepends=True)`); every code cell verified to parse before resend |
| Portfolio Value understated (`13`) | See Financial Calculations table above | See above |
| Available Cash double-counted (`13`) | See Financial Calculations table above | See above |
| CASH recon silently dropped funds present only externally (`14`) | `left` join started from internal `fund_financials`, so a fund missing internally would vanish instead of surfacing as `MISSING_INTERNAL` | Rebuilt as `full_outer` join with explicit `_has_internal`/`_has_external_cash` checks |

## Known limitations

- **Security:** `00_setup_silver_catalog` cell 17 originally contained a
  hardcoded Azure SQL username/password for the Lakehouse Federation
  connection. **Resolved** — credentials removed, to be moved to a Databricks
  secret scope.
- **CASH reconciliation cannot structurally produce a MATCH** — accepted
  definitional limitation, not a bug (see Reconciliation section above).

