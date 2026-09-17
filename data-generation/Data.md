# PE Capital & Payment Platform — Data Generation

Generates the 6 source tables for the platform: `Market_Price` (real,
via yfinance), plus 5 Faker-generated tables (`Investor`, `Fund`,
`Commitment`, `Portfolio_Company`, `Payment`).

1. **Market_Price** — must run first; `Portfolio_Company` and `Payment`
   both read its output.
2. **Investor**, **Fund** — no dependencies.
3. **Commitment** — joins Investor + Fund.
4. **Portfolio_Company** — joins Fund; optionally tags a real ticker
   from Market_Price as `benchmark_ticker` (loose link, not a true FK
   — private companies don't have real ticker symbols).
5. **Payment** — joins Commitment + Portfolio_Company; looks up
   `entry_benchmark_price` from today's Market_Price for INVESTMENT rows.

## Local run

```bash
pip install -r requirements.txt
cp .env.example .env        # fill in AZURE_STORAGE_CONNECTION_STRING if uploading
python -m src.main           # generate only, writes to data/
python -m src.main --upload  # generate + push to ADLS "ingested" container
```

## Output layout

Each table lands date-partitioned, mirroring the ADLS structure:

```
data/<table>/ingestion_date=YYYY-MM-DD/<table>.csv
```

`Investor`, `Fund`, `Commitment`, `Portfolio_Company` write a **full
current snapshot** each run (they're near-static reference data —
all four generated together in `src/generators/reference_data.py`).
`Market_Price` and `Payment` write **only today's new rows**
(transactional/time-series data).

## State

`state/state.json` is the cross-day memory — running totals per
commitment (`contributed_total`, `invested_total`), the full current
investor/fund/commitment/company lists, and ID counters. It's
committed to the repo (via the GitHub Actions workflow) so every
team member's run continues from the same history rather than
starting fresh.

## Automation

`.github/workflows/daily-generation.yml` runs this on a daily cron
(`workflow_dispatch` also lets you trigger it manually from the
Actions tab). Requires `AZURE_STORAGE_CONNECTION_STRING` set as a
repo secret.
