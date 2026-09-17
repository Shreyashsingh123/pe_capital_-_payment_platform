"""
Payment — the transaction fact table. Unlike the other 5 tables, this
one is APPEND-ONLY: each run writes only TODAY's new events (not a
full snapshot), simulating real daily fund activity arriving.

Enforces the business rules Faker alone won't give you:
  - CONTRIBUTION can't push contributed_total above committed_amount_usd
  - INVESTMENT can't push invested_total above contributed_total
  - INVESTMENT rows capture entry_benchmark_price from today's market data

Mandatory scenarios from the plan (duplicates, status transitions,
failures, late records) are layered in separately as deliberate test
batches, not generated randomly here -- see README.
"""
import random
import pandas as pd
from faker import Faker
from ..common.config import NEW_PAYMENTS_PER_RUN, PAYMENT_STATUSES, partitioned_path, get_business_date
from ..common.state import next_id

fake = Faker()


def _pick_valid_type(commitment: dict) -> str:
    """Only offer event types that actually make sense for this
    commitment right now, so the data stays coherent (e.g. no
    INVESTMENT before anything's been contributed)."""
    uncalled = commitment["committed_amount_usd"] - commitment["contributed_total"]
    uninvested = commitment["contributed_total"] - commitment["invested_total"]

    valid_types = ["CAPITAL_CALL", "CONTRIBUTION"] if uncalled > 0 else []
    if uninvested > 0:
        valid_types.append("INVESTMENT")
    if commitment["invested_total"] > 0:
        valid_types.append("DISTRIBUTION")

    return random.choice(valid_types) if valid_types else "CAPITAL_CALL"


def generate_payments(state: dict, portfolio_companies: list, tickers_today: dict) -> list:
    business_date = get_business_date()
    n_new = random.randint(*NEW_PAYMENTS_PER_RUN)
    new_rows = []

    for _ in range(n_new):
        if not state["commitments"]:
            break
        commitment = random.choice(state["commitments"])
        payment_type = _pick_valid_type(commitment)
        status = random.choices(PAYMENT_STATUSES, weights=[2, 7, 1])[0]  # mostly SETTLED

        company_id = None
        entry_price = None
        amount = 0

        if payment_type in ("CAPITAL_CALL", "CONTRIBUTION"):
            remaining = commitment["committed_amount_usd"] - commitment["contributed_total"]
            amount = round(random.uniform(0.05, 0.25) * remaining, 2) if remaining > 0 else 0
            if payment_type == "CONTRIBUTION" and status == "SETTLED":
                commitment["contributed_total"] += amount

        elif payment_type == "INVESTMENT":
            remaining = commitment["contributed_total"] - commitment["invested_total"]
            amount = round(random.uniform(0.1, 0.4) * remaining, 2) if remaining > 0 else 0
            fund_companies = [c for c in portfolio_companies if c["fund_id"] == commitment["fund_id"]]
            if fund_companies:
                company = random.choice(fund_companies)
                company_id = company["company_id"]
                entry_price = tickers_today.get(company["benchmark_ticker"]) if company["benchmark_ticker"] else None
            if status == "SETTLED":
                commitment["invested_total"] += amount

        elif payment_type == "DISTRIBUTION":
            amount = round(random.uniform(0.02, 0.1) * max(commitment["invested_total"], 1), 2)

        if amount <= 0:
            continue

        new_rows.append({
            "payment_id": next_id(state, "payment", "PMT", width=6),
            "commitment_id": commitment["commitment_id"],
            "fund_id": commitment["fund_id"],
            "investor_id": commitment["investor_id"],
            "company_id": company_id,
            "payment_type": payment_type,
            "amount_usd": amount,
            "status": status,
            "event_date": business_date,
            "entry_benchmark_price": entry_price,
        })

    out_dir = partitioned_path("payment", business_date)
    pd.DataFrame(new_rows).to_csv(f"{out_dir}/payment.csv", index=False)
    print(f"[payment] Generated {len(new_rows)} new payment events for {business_date}")
    return new_rows
