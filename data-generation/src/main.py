import argparse
from dotenv import load_dotenv
load_dotenv()

from .common.state import load_state, save_state
from .common.config import get_business_date, DATA_ROOT, TABLE_FOLDERS
from .common.adls_upload import upload_folder
from .generators.market_price import fetch_market_data
from .generators.reference_data import (
    generate_investors, generate_funds, generate_commitments, generate_portfolio_companies,
)
from .generators.payment import generate_payments


def run(upload: bool = False):
    business_date = get_business_date()
    print(f"=== Daily generation run for {business_date} ===")

    state = load_state()

    # 1. Market data first -- nothing else can reference it until it exists
    tickers_today = fetch_market_data()

    # 2-3. Static reference data
    generate_investors(state)
    generate_funds(state)

    # 4. Joins Investor + Fund
    generate_commitments(state)

    # 5. Joins Fund, optionally tags a ticker from today's market data
    portfolio_companies = generate_portfolio_companies(state, list(tickers_today.keys()))

    # 6. The daily-growing transaction log
    generate_payments(state, portfolio_companies, tickers_today)

    state["last_business_date"] = business_date
    save_state(state)

    if upload:
        for table, folder in TABLE_FOLDERS.items():
            import os
            local_dir = os.path.join(DATA_ROOT, folder, f"ingestion_date={business_date}")
            if os.path.exists(local_dir):
                upload_folder(local_dir, f"{folder}/ingestion_date={business_date}")

    print(f"=== Run complete for {business_date} ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", action="store_true", help="Upload today's output to ADLS")
    args = parser.parse_args()
    run(upload=args.upload)
