# Power BI — PE Fund Capital, Payment & Reconciliation Platform

## File

| File | Description |
|---|---|
| `powerbi.pbix` | Main Power BI Desktop report — connects to the Azure SQL `gold` schema |

---

## Data source

The report connects directly to **Azure SQL** via DirectQuery or Import mode
against the `gold` schema. All seven tables are used:

| Table | Used for |
|---|---|
| `gold.fund_snapshot` | Fund overview, vintage year, fund size, NAV cards |
| `gold.fund_financials` | Capital structure waterfall, NAV decomposition |
| `gold.portfolio_valuation` | Portfolio company cards, market value ranking |
| `gold.reconciliation` | Reconciliation status matrix, break drill-through |
| `gold.payment_summary` | Payment flow by type and source side |
| `gold.data_quality` | DQ health scorecard, failure rate trends |
| `gold.market_price` | Price history line charts per ticker |

---

## Report pages

| Page | Visuals | Key measures |
|---|---|---|
| **Fund Overview** | KPI cards, bar chart by vintage year | Total NAV, fund size, % called per fund |
| **Portfolio Valuation** | Table + bar chart | Market value rank within fund, benchmark coverage flags |
| **Payments** | Stacked bar / matrix | Total amount by payment type, INTERNAL vs EXTERNAL side-by-side |
| **Market Prices** | Line chart | Closing price history per ticker; latest close highlighted |
| **Reconciliation** | Matrix heat map, drill-through table | Row counts by type × status; BREAK detail with break reason |
| **Data Quality** | Scorecard table, trend line | Average and max failure rate per source; records checked vs failed |

---

## DAX measures (key)

```dax
-- Total Estimated NAV
Total NAV = SUM(fund_financials[estimated_nav])

-- Percent Called
Pct Called =
DIVIDE(
    SUM(fund_snapshot[contributions]),
    SUM(fund_snapshot[total_commitments]),
    BLANK()
) * 100

-- NAV Discrepancy (integrity check)
NAV Discrepancy =
SUMX(
    fund_financials,
    fund_financials[estimated_nav]
        - (fund_financials[portfolio_value] + fund_financials[available_cash_internal])
)

-- Reconciliation Break Rate
Break Rate =
DIVIDE(
    CALCULATE(COUNTROWS(reconciliation), reconciliation[status] = "BREAK"),
    COUNTROWS(reconciliation),
    BLANK()
)

-- DQ Avg Failure Rate
Avg Failure Rate = AVERAGE(data_quality[failure_rate])
```

---

## Relationships

```
fund_snapshot[fund_id]        → fund_financials[fund_id]        (1:1)
fund_snapshot[fund_id]        → portfolio_valuation[fund_id]    (1:many)
fund_snapshot[fund_id]        → reconciliation[fund_id]         (1:many)
fund_snapshot[fund_id]        → payment_summary[fund_id]        (1:many)
fund_snapshot[fund_id]        → market_price[fund_id]           (1:many)
portfolio_valuation[benchmark_ticker] → market_price[ticker]    (1:many)
```

> **Note:** `gold.data_quality` has no direct foreign key to `fund_snapshot`.
> Filter by `source_name` in slicers to scope DQ results per data source.

---

## Known data behaviours

- **CASH reconciliation will never show a MATCH** — internal cash is a
  cumulative net-capital figure; external cash is a point-in-time bank
  balance. Filter these rows out of any "match rate" KPI or document the
  caveat in the visual tooltip.
- **Ticker fan-out in `market_price`** — 6 tickers (including `GOOGL`) map to
  more than one company. A `(ticker, bar_timestamp)` slicer will return
  multiple rows. Use `market_price_id` as the row identifier, not the
  composite key.
- **`business_date` and `created_at` in `data_quality`** are stored as text
  (`NVARCHAR`) in Azure SQL. Apply a Power Query transform (`Date.From` /
  `DateTime.From`) or a DAX `DATEVALUE` conversion before using them on a
  date axis.
- **Portfolio value** — only 1 of 30 companies (`PORT_0003` / FUND_001) has
  both a benchmark price and a position record. The remaining companies
  correctly show $0 market value given the current sample data set.

---

## Refresh / connection setup

1. Open `powerbi.pbix` in Power BI Desktop.
2. Go to **Home → Transform data → Data source settings**.
3. Update the Azure SQL server and database name to match your environment.
4. Credentials: use **Database** authentication with the read-only SQL login
   provisioned for the `gold` schema.
5. Click **Refresh** to load the latest data from Azure SQL.

For scheduled refresh after publishing to Power BI Service, configure a
**gateway** connection pointing to the same Azure SQL instance.
