# Data Generation — PE Fund Capital, Payment & Reconciliation Intelligence Platform

Covers two distinct things: the **recurring** internal data generator (runs
daily, automated) and the **one-time** external `.dat` feed pack upload
(fixed historical sample, not recurring). Keep these mental models separate —
mixing them up was a real source of confusion earlier in the build.

## Part 1 — Internal data (recurring, automated)

Generates 6 source tables via Python + Faker + a real market API (`yfinance`),
runs daily via GitHub Actions cron.

### Run order (enforced by `src/main.py`)

1. **Market_Price** — must run first; nothing else can reference prices
   that don't exist yet.
2. **Investor**, **Fund** — no dependencies, generated once, snapshotted
   each run.
3. **Commitment** — joins Investor + Fund.
4. **Portfolio_Company** — joins Fund; optionally tags a real ticker as
   `benchmark_ticker` (~80% of companies, intentionally left unbenchmarked
   for the rest).
5. **Payment** — joins Commitment + Portfolio_Company; looks up
   `entry_benchmark_price` from Market_Price for `INVESTMENT` rows.

### Behavior

- `Investor`, `Fund`, `Commitment`, `Portfolio_Company` write a **full
  current snapshot** each run — near-static reference data.
- `Market_Price` and `Payment` write **only new rows** each run —
  transactional/time-series data.
- Cross-day continuity lives in `state/state.json` — running totals per
  commitment (`contributed_total`, `invested_total`), full current
  reference lists, and ID counters. Committed to the repo so every team
  member's runs and the automated runs share one continuous history.

### Automation

`.github/workflows/daily-generation.yml` — runs at 00:30 UTC (6:00 AM
IST), chosen deliberately: this is after the previous day's US market
close (1:30 AM IST) and before Asia-Pacific markets reopen, so one run
captures one complete global trading day across all included markets
rather than a half-day snapshot.

### Weekend / non-trading-day behavior — verified

Manually verified by comparing live output across a Saturday → Sunday →
Monday sequence:

- **Saturday**: mostly carries forward Friday's last available data,
  since the run happens before Indian markets would open on a normal
  day and markets don't trade on weekends at all.
- **Sunday**: holds the same data as Saturday across the board — no
  market traded in between, so there's nothing new to fetch.
- **Monday**: holds the same carried-forward data as Saturday/Sunday for
  markets that haven't opened yet by the 6 AM IST run time, but a small number
  of rows for non-Indian markets that have already begun their Monday session by then show fresh,
  current-day data.

This is expected, correct behavior, not a gap — the generator simply
reflects whatever the latest available bar is per ticker at run time.
No changes needed based on this verification.

## Part 2 — External `.dat` feed pack (one-time, not recurring)

A fixed, pre-built 3-day sample (`PE_Fund_Sample_DAT_Feed_Pack.zip`,
business dates Sept 15–17, 2026) simulating custodian, bank, reference
vendor, and payment-system feeds — used as the "external" side of
reconciliation against our internal data.

- **4 feed types**: `position`, `cash`, `reference`, `payment` —
  pipe-delimited, wrapped with `HDR`/`TRL` control records.
- Includes one deliberately malformed file
  (`POSITION_..._INVALID.dat`) with known bad rows (null quantity,
  negative quantity, invalid price, bad timestamp, unmapped IDs) — used
  as the DQ/quarantine test fixture downstream.
- **Not part of the daily cron** — landed once via
  `scripts/upload_dat_pack.py`, a standalone script (not wired into
  `main.py` or the GitHub Actions workflow) that parses each filename
  (`<FEED_TYPE>_<YYYYMMDD>_<HHMMSS>[_SUFFIX].dat`) and uploads to
  `ingested/external_dat/<feed_type>/business_date=YYYY-MM-DD/`.

### Identifier mismatch — handled downstream, not here

The pack's IDs (`FND001`, `AST001`, etc.) don't match our internal IDs
(`FUND_001`, `PORT_0001`, etc.) — this is intentional, not a bug to fix
in generation. A crosswalk (`staging.fund_id_mapping`,
`staging.asset_id_mapping` in Azure SQL) resolves this at the Silver
layer. `AST999`/`FNDXXX` (only in the invalid file) are deliberately
**not** in the crosswalk — a lookup miss there is correct.

## Bugs found & fixed along the way

| Issue | Fix |
|---|---|
| `.env` didn't actually load — `python-dotenv` was in `requirements.txt` but never called | Added `load_dotenv()` to the top of `main.py` |
| Scheduled GitHub Actions runs failed while `data-generation/` only existed on `develop` | GitHub only runs scheduled workflows against the repo's **default branch** — synced tested code from `develop` into `main` |
| `market_summary` output (leftover from the original standalone script) wasn't one of the 6 agreed tables | Removed entirely — computing daily % change is a Silver/Gold-layer transformation, not something the raw layer should pre-aggregate |
| Company names with commas (e.g. `"Branch, Carter and Mack"`) appeared to render as empty in some CSV viewers | Confirmed via direct pandas round-trip that the data itself is correct — quoting works fine; it was a viewer rendering issue, not a generation bug |

## Known limitations

- **`state.json` continuity was validated manually**, not via an automated
  test suite — confirmed across simulated multi-day runs that reference
  tables stay static, `Payment` grows correctly, and IDs increment
  without resetting. This is a deliberate, documented manual verification,
  not automated testing.
- **GitHub Actions scheduled runs can drift** by anywhere from minutes to
  hours under GitHub's shared runner load — this is documented, expected
  platform behavior, not something the workflow can fully control.
