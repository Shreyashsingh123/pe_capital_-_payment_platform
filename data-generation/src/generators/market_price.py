"""
Market_Price generator — the one real (non-Faker) source.
Runs FIRST: Portfolio_Company (benchmark tagging) and Payment
(entry_benchmark_price on INVESTMENT rows) both depend on its output.

Writes one file: market_price.csv (raw OHLCV bars).
Returns a dict {ticker: latest_close} so the same run can pass prices
directly to reference_data.py / payment.py without re-reading from disk.
"""
import time
import pandas as pd
import yfinance as yf

from ..common.config import TICKERS, partitioned_path, get_business_date


def fetch_market_data(retries: int = 3, delay_seconds: int = 5) -> dict:
    business_date = get_business_date()
    price_rows = []
    latest_close = {}

    for ticker_sym in TICKERS:
        raw = None
        for attempt in range(retries):
            try:
                raw = yf.Ticker(ticker_sym).history(period="1d", interval="1h")
                if not raw.empty:
                    break
            except Exception as e:
                print(f"[market_price] {ticker_sym} attempt {attempt+1} failed: {e}")
            time.sleep(delay_seconds)

        if raw is None or raw.empty:
            print(f"[market_price] Skipping {ticker_sym} — no data after {retries} attempts")
            continue

        for ts, row in raw.iterrows():
            price_rows.append({
                "ticker": ticker_sym,
                "bar_timestamp": ts.isoformat(),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]),
            })

        latest_close[ticker_sym] = round(float(raw["Close"].iloc[-1]), 4)

    out_dir = partitioned_path("market_price", business_date)
    pd.DataFrame(price_rows).to_csv(f"{out_dir}/market_price.csv", index=False)
    print(f"[market_price] Wrote {len(price_rows)} price rows across {len(latest_close)} tickers")
    return latest_close


if __name__ == "__main__":
    fetch_market_data()
