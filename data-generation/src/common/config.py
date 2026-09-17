"""
Central configuration for all generators.
Keep every path, table name, and tunable constant here so no generator
script hardcodes a folder name or ticker list independently.
"""
import os
from datetime import date, datetime

# ---- Business date -------------------------------------------------
# Lets you simulate "today" independently of the real calendar date,
# e.g. for backfilling several business days in one dev session.
def get_business_date() -> str:
    override = os.environ.get("BUSINESS_DATE")
    if override:
        return override
    return date.today().isoformat()


# ---- Local output root ---------------------------------------------
DATA_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "data")
STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "state", "state.json")

# ---- Table -> folder name mapping (mirrors ADLS container layout) --
TABLE_FOLDERS = {
    "market_price": "market_price",
    "investor": "investor",
    "fund": "fund",
    "commitment": "commitment",
    "portfolio_company": "portfolio_company",
    "payment": "payment",
}


def partitioned_path(table: str, business_date: str) -> str:
    """Returns e.g. data/payment/ingestion_date=2026-01-05/"""
    folder = os.path.join(DATA_ROOT, TABLE_FOLDERS[table], f"ingestion_date={business_date}")
    os.makedirs(folder, exist_ok=True)
    return folder


# ---- Market data universe -------------------------------------------
# Representative multi-country ticker set. Expand freely -- nothing
# downstream depends on the exact count, only that Market_Price runs
# before Portfolio_Company and Payment.
TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "V", "WMT", "XOM", "UNH", "PG",
    "HSBA.L", "BP.L", "ULVR.L",              # UK
    "SAP.DE", "SIE.DE", "ALV.DE",             # Germany
    "7203.T", "6758.T",                        # Japan
    "RELIANCE.NS", "TCS.NS",                   # India
    "RY.TO", "SHOP.TO",                         # Canada
    "BHP.AX", "CBA.AX",                          # Australia
    "MC.PA", "OR.PA",                             # France
    "NESN.SW", "NOVN.SW",                          # Switzerland
    "0700.HK",                                       # China/HK
]

# ---- Faker volumes ----------------------------------------------------
NUM_INVESTORS = 50
NUM_FUNDS = 5
NUM_INITIAL_COMMITMENTS_PER_FUND = (8, 20)     # random range
NUM_PORTFOLIO_COMPANIES = 30
NEW_PAYMENTS_PER_RUN = (20, 60)                # random range, per daily run

INVESTOR_TYPES = ["Pension Fund", "Endowment", "Family Office", "Insurance"]
PAYMENT_TYPES = ["CAPITAL_CALL", "CONTRIBUTION", "INVESTMENT", "DISTRIBUTION"]
PAYMENT_STATUSES = ["INITIATED", "SETTLED", "FAILED"]
