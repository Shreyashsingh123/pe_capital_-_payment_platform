import pandas as pd
import pytest

from src.common.config import PAYMENT_STATUSES, PAYMENT_TYPES
from src.generators import payment as pay

COLUMNS = [
    "payment_id", "commitment_id", "fund_id", "investor_id", "company_id",
    "payment_type", "amount_usd", "status", "event_date", "entry_benchmark_price",
]


def commitment(committed=100, contributed=0, invested=0, fund="FUND_001", cid="CMT_00001"):
    return {
        "commitment_id": cid, "fund_id": fund, "investor_id": "LP_0001",
        "committed_amount_usd": committed, "commitment_date": "2023-01-01",
        "contributed_total": contributed, "invested_total": invested,
    }


def company(fund="FUND_001", ticker="AAPL", cid="PORT_0001"):
    return {"company_id": cid, "company_name": "Acme", "fund_id": fund,
            "industry": "x", "benchmark_ticker": ticker}


# ---- _pick_valid_type -------------------------------------------------

@pytest.mark.parametrize("c,expected", [
    (commitment(100, 0, 0), ["CAPITAL_CALL", "CONTRIBUTION"]),
    (commitment(100, 40, 0), ["CAPITAL_CALL", "CONTRIBUTION", "INVESTMENT"]),
    (commitment(100, 40, 10), ["CAPITAL_CALL", "CONTRIBUTION", "INVESTMENT", "DISTRIBUTION"]),
    (commitment(100, 100, 10), ["INVESTMENT", "DISTRIBUTION"]),
    (commitment(100, 100, 0), ["INVESTMENT"]),
    (commitment(100, 100, 100), ["DISTRIBUTION"]),
])
def test_pick_valid_type_offers_only_sensible_options(monkeypatch, c, expected):
    monkeypatch.setattr(pay.random, "choice", lambda seq: list(seq))
    assert pay._pick_valid_type(c) == expected


def test_pick_valid_type_nothing_valid_defaults_to_capital_call(monkeypatch):
    def boom(seq):
        raise AssertionError("random.choice must not be called")
    monkeypatch.setattr(pay.random, "choice", boom)
    assert pay._pick_valid_type(commitment(0, 0, 0)) == "CAPITAL_CALL"


# ---- generate_payments: shape ----------------------------------------

def test_generate_payments_shape(populated_state, tickers_today, monkeypatch, read_csv, business_date):
    monkeypatch.setattr(pay.random, "randint", lambda a, b: 25)

    rows = pay.generate_payments(populated_state, populated_state["portfolio_companies"], tickers_today)

    # a few draws may be skipped (amount 0), so there are at most 25 rows
    assert 0 < len(rows) <= 25
    assert list(rows[0]) == COLUMNS
    assert [r["payment_id"] for r in rows] == [f"PMT_{n:06d}" for n in range(1, len(rows) + 1)]
    by_id = {c["commitment_id"]: c for c in populated_state["commitments"]}
    for r in rows:
        c = by_id[r["commitment_id"]]
        assert (r["fund_id"], r["investor_id"]) == (c["fund_id"], c["investor_id"])
        assert r["event_date"] == business_date
        assert r["status"] in PAYMENT_STATUSES
        assert r["payment_type"] in PAYMENT_TYPES
        assert r["amount_usd"] > 0
    df = read_csv("payment")
    assert list(df.columns) == COLUMNS
    assert len(df) == len(rows)
    assert populated_state["counters"]["payment"] == len(rows)


def test_payment_ids_continue_from_counter(populated_state, tickers_today, monkeypatch):
    populated_state["counters"]["payment"] = 10
    monkeypatch.setattr(pay.random, "randint", lambda a, b: 5)
    rows = pay.generate_payments(populated_state, populated_state["portfolio_companies"], tickers_today)
    assert rows[0]["payment_id"] == "PMT_000011"


def test_no_commitments_returns_empty_but_writes_file(fresh_state, read_csv, data_root, business_date):
    assert pay.generate_payments(fresh_state, [], {}) == []
    path = data_root / "payment" / f"ingestion_date={business_date}" / "payment.csv"
    assert path.exists()
    assert fresh_state["counters"]["payment"] == 0


# ---- generate_payments: business rules -------------------------------

@pytest.fixture
def rule_env(monkeypatch):
    """One draw per run; payment type and status are set by the test."""
    def configure(ptype, status):
        monkeypatch.setattr(pay.random, "randint", lambda a, b: 1)
        monkeypatch.setattr(pay, "_pick_valid_type", lambda c: ptype)
        monkeypatch.setattr(pay.random, "choices", lambda *a, **k: [status])
    return configure


def run_one(c, companies=(), tickers=None):
    state = {"commitments": [c], "counters": {"payment": 0}}
    return pay.generate_payments(state, list(companies), tickers or {}), state


@pytest.mark.parametrize("status,changes", [("SETTLED", True), ("FAILED", False), ("INITIATED", False)])
def test_contribution_updates_contributed_total_only_when_settled(rule_env, status, changes):
    rule_env("CONTRIBUTION", status)
    c = commitment(1000, 200, 0)

    rows, _ = run_one(c)

    (row,) = rows
    assert 0.05 * 800 <= row["amount_usd"] <= 0.25 * 800
    assert c["contributed_total"] == (200 + row["amount_usd"] if changes else 200)
    assert c["invested_total"] == 0
    assert row["company_id"] is None and row["entry_benchmark_price"] is None


def test_capital_call_never_changes_totals(rule_env):
    rule_env("CAPITAL_CALL", "SETTLED")
    c = commitment(1000, 200, 0)
    rows, _ = run_one(c)
    assert rows[0]["payment_type"] == "CAPITAL_CALL"
    assert (c["contributed_total"], c["invested_total"]) == (200, 0)


def test_settled_investment_captures_company_and_price(rule_env):
    rule_env("INVESTMENT", "SETTLED")
    c = commitment(1_000_000, 500_000, 0)
    companies = [company(fund="OTHER", cid="PORT_0009"), company(cid="PORT_0001")]

    rows, _ = run_one(c, companies, {"AAPL": 190.1234})

    (row,) = rows
    assert 0.1 * 500_000 <= row["amount_usd"] <= 0.4 * 500_000
    assert row["company_id"] == "PORT_0001"
    assert row["entry_benchmark_price"] == 190.1234
    assert c["invested_total"] == row["amount_usd"]
    assert c["contributed_total"] == 500_000


def test_failed_investment_leaves_invested_total(rule_env):
    rule_env("INVESTMENT", "FAILED")
    c = commitment(1_000_000, 500_000, 0)
    rows, _ = run_one(c, [company()], {"AAPL": 1.0})
    assert len(rows) == 1
    assert c["invested_total"] == 0


@pytest.mark.parametrize("ticker,tickers", [(None, {"AAPL": 1.0}), ("ZZZ", {"AAPL": 1.0})])
def test_investment_without_price_has_null_entry_price(rule_env, ticker, tickers):
    rule_env("INVESTMENT", "SETTLED")
    rows, _ = run_one(commitment(1000, 500, 0), [company(ticker=ticker)], tickers)
    assert rows[0]["company_id"] == "PORT_0001"
    assert rows[0]["entry_benchmark_price"] is None


def test_investment_without_fund_company_still_emitted(rule_env):
    rule_env("INVESTMENT", "SETTLED")
    rows, _ = run_one(commitment(1000, 500, 0), [company(fund="OTHER")], {"AAPL": 1.0})
    assert rows[0]["company_id"] is None
    assert rows[0]["entry_benchmark_price"] is None


def test_distribution_amount_range_and_no_state_change(rule_env):
    rule_env("DISTRIBUTION", "SETTLED")
    c = commitment(5_000_000, 2_000_000, 1_000_000)
    rows, _ = run_one(c, [company()], {"AAPL": 1.0})
    (row,) = rows
    assert 20_000 <= row["amount_usd"] <= 100_000
    assert (c["contributed_total"], c["invested_total"]) == (2_000_000, 1_000_000)
    assert row["company_id"] is None and row["entry_benchmark_price"] is None


def test_zero_amount_rows_are_skipped_and_do_not_consume_ids(rule_env):
    rule_env("CAPITAL_CALL", "SETTLED")
    c = commitment(100, 100, 0)  # fully drawn -> nothing remaining
    rows, state = run_one(c)
    assert rows == []
    assert state["counters"]["payment"] == 0


# ---- generate_payments: multi-day invariants -------------------------

def test_multi_day_invariants(populated_state, tickers_today, monkeypatch, data_root):
    all_rows = []
    for day in range(6, 21):
        monkeypatch.setenv("BUSINESS_DATE", f"2025-01-{day:02d}")
        all_rows += pay.generate_payments(
            populated_state, populated_state["portfolio_companies"], tickers_today
        )

    ids = [r["payment_id"] for r in all_rows]
    assert ids == [f"PMT_{n:06d}" for n in range(1, len(ids) + 1)]
    assert len(list((data_root / "payment").iterdir())) == 15

    df = pd.DataFrame(all_rows)
    settled = df[df.status == "SETTLED"]
    for c in populated_state["commitments"]:
        mine = settled[settled.commitment_id == c["commitment_id"]]
        contributed = mine[mine.payment_type == "CONTRIBUTION"].amount_usd.sum()
        invested = mine[mine.payment_type == "INVESTMENT"].amount_usd.sum()
        assert c["contributed_total"] <= c["committed_amount_usd"] + 0.01
        assert c["invested_total"] <= c["contributed_total"] + 0.01
        assert c["contributed_total"] == pytest.approx(contributed, abs=0.05)
        assert c["invested_total"] == pytest.approx(invested, abs=0.05)
    assert (df.amount_usd > 0).all()
    assert set(df.payment_type) <= set(PAYMENT_TYPES)
