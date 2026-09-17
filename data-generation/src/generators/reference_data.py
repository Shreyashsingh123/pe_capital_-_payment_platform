"""
Reference data — Investor, Fund, Commitment, Portfolio_Company.
All four are near-static: generated once, then re-emitted as a
snapshot on later runs (no daily growth, unlike Payment).
Combined into one file since they follow the same simple pattern.
"""
import random
import pandas as pd
from faker import Faker

from ..common.config import (
    NUM_INVESTORS, NUM_FUNDS, NUM_INITIAL_COMMITMENTS_PER_FUND,
    NUM_PORTFOLIO_COMPANIES, INVESTOR_TYPES, partitioned_path, get_business_date,
)
from ..common.state import next_id

fake = Faker()


def _snapshot(table: str, rows: list) -> None:
    out_dir = partitioned_path(table, get_business_date())
    pd.DataFrame(rows).to_csv(f"{out_dir}/{table}.csv", index=False)


def generate_investors(state: dict) -> list:
    if not state["investors"]:
        state["investors"] = [
            {
                "investor_id": next_id(state, "investor", "LP"),
                "investor_name": fake.company(),
                "investor_type": fake.random_element(INVESTOR_TYPES),
                "country": fake.country(),
            }
            for _ in range(NUM_INVESTORS)
        ]
    _snapshot("investor", state["investors"])
    return state["investors"]


def generate_funds(state: dict) -> list:
    if not state["funds"]:
        state["funds"] = [
            {
                "fund_id": next_id(state, "fund", "FUND", width=3),
                "fund_name": f"{fake.word().capitalize()} Capital Fund {i + 1}",
                "vintage_year": random.randint(2020, 2025),
                "fund_size_usd": random.randint(50_000_000, 500_000_000),
            }
            for i in range(NUM_FUNDS)
        ]
    _snapshot("fund", state["funds"])
    return state["funds"]


def generate_commitments(state: dict) -> list:
    if not state["commitments"]:
        for fund in state["funds"]:
            k = random.randint(*NUM_INITIAL_COMMITMENTS_PER_FUND)
            for inv in random.sample(state["investors"], k=min(k, len(state["investors"]))):
                state["commitments"].append({
                    "commitment_id": next_id(state, "commitment", "CMT", width=5),
                    "fund_id": fund["fund_id"],
                    "investor_id": inv["investor_id"],
                    "committed_amount_usd": random.randint(1_000_000, 20_000_000),
                    "commitment_date": fake.date_between(start_date="-3y", end_date="-1y").isoformat(),
                    "contributed_total": 0,
                    "invested_total": 0,
                })
    _snapshot("commitment", state["commitments"])
    return state["commitments"]


def generate_portfolio_companies(state: dict, tickers_today: list) -> list:
    if not state["portfolio_companies"]:
        for _ in range(NUM_PORTFOLIO_COMPANIES):
            # ~80% get a benchmark ticker; rest intentionally left unbenchmarked
            ticker = random.choice(tickers_today) if tickers_today and random.random() < 0.8 else None
            state["portfolio_companies"].append({
                "company_id": next_id(state, "company", "PORT", width=4),
                "company_name": fake.company(),
                "fund_id": random.choice(state["funds"])["fund_id"],
                "industry": fake.bs(),
                "benchmark_ticker": ticker,
            })
    _snapshot("portfolio_company", state["portfolio_companies"])
    return state["portfolio_companies"]
