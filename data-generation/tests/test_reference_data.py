from datetime import date, timedelta

import pandas as pd
import pytest

from src.common.config import INVESTOR_TYPES
from src.generators import reference_data as rd


def test_generate_investors(fresh_state, read_csv):
    result = rd.generate_investors(fresh_state)

    assert result is fresh_state["investors"]
    assert len(result) == 50
    assert [i["investor_id"] for i in result] == [f"LP_{n:04d}" for n in range(1, 51)]
    assert all(set(i) == {"investor_id", "investor_name", "investor_type", "country"} for i in result)
    assert {i["investor_type"] for i in result} <= set(INVESTOR_TYPES)
    assert fresh_state["counters"]["investor"] == 50
    df = read_csv("investor")
    assert len(df) == 50
    assert list(df.columns) == ["investor_id", "investor_name", "investor_type", "country"]


def test_generate_funds(fresh_state, read_csv):
    funds = rd.generate_funds(fresh_state)

    assert [f["fund_id"] for f in funds] == [f"FUND_{n:03d}" for n in range(1, 6)]
    for i, f in enumerate(funds, start=1):
        assert f["fund_name"].endswith(f"Capital Fund {i}")
        assert 2020 <= f["vintage_year"] <= 2025
        assert isinstance(f["fund_size_usd"], int)
        assert 50_000_000 <= f["fund_size_usd"] <= 500_000_000
    assert list(read_csv("fund").columns) == ["fund_id", "fund_name", "vintage_year", "fund_size_usd"]


def test_generate_commitments(fresh_state, read_csv):
    rd.generate_investors(fresh_state)
    rd.generate_funds(fresh_state)

    commitments = rd.generate_commitments(fresh_state)

    investor_ids = {i["investor_id"] for i in fresh_state["investors"]}
    fund_ids = {f["fund_id"] for f in fresh_state["funds"]}
    assert [c["commitment_id"] for c in commitments] == [f"CMT_{n:05d}" for n in range(1, len(commitments) + 1)]
    for fund_id in fund_ids:
        rows = [c for c in commitments if c["fund_id"] == fund_id]
        assert 8 <= len(rows) <= 20
        assert len({c["investor_id"] for c in rows}) == len(rows)  # sampled without replacement
    today = date.today()
    for c in commitments:
        assert c["investor_id"] in investor_ids
        assert 1_000_000 <= c["committed_amount_usd"] <= 20_000_000
        d = date.fromisoformat(c["commitment_date"])
        assert today - timedelta(days=1096) <= d <= today - timedelta(days=364)
        assert c["contributed_total"] == 0 and c["invested_total"] == 0
    df = read_csv("commitment")
    assert list(df.columns) == [
        "commitment_id", "fund_id", "investor_id", "committed_amount_usd",
        "commitment_date", "contributed_total", "invested_total",
    ]
    assert len(df) == len(commitments)


def test_commitments_capped_at_investor_count(fresh_state):
    fresh_state["investors"] = [
        {"investor_id": f"LP_{n:04d}", "investor_name": "x", "investor_type": "Endowment", "country": "c"}
        for n in range(1, 4)
    ]
    fresh_state["funds"] = [{"fund_id": "FUND_001"}]
    commitments = rd.generate_commitments(fresh_state)
    assert len(commitments) == 3
    assert {c["investor_id"] for c in commitments} == {"LP_0001", "LP_0002", "LP_0003"}


def test_generate_portfolio_companies(fresh_state, read_csv, tickers_today):
    rd.generate_funds(fresh_state)
    tickers = list(tickers_today)

    companies = rd.generate_portfolio_companies(fresh_state, tickers)

    fund_ids = {f["fund_id"] for f in fresh_state["funds"]}
    assert [c["company_id"] for c in companies] == [f"PORT_{n:04d}" for n in range(1, 31)]
    assert {c["fund_id"] for c in companies} <= fund_ids
    benchmarked = [c for c in companies if c["benchmark_ticker"] is not None]
    assert 0 < len(benchmarked) <= 30
    assert {c["benchmark_ticker"] for c in benchmarked} <= set(tickers)
    df = read_csv("portfolio_company")
    assert list(df.columns) == ["company_id", "company_name", "fund_id", "industry", "benchmark_ticker"]
    assert df.benchmark_ticker.isna().sum() == 30 - len(benchmarked)


def test_no_tickers_means_no_benchmarks(fresh_state, read_csv):
    rd.generate_funds(fresh_state)
    companies = rd.generate_portfolio_companies(fresh_state, [])
    assert all(c["benchmark_ticker"] is None for c in companies)
    assert read_csv("portfolio_company").benchmark_ticker.isna().all()


@pytest.mark.parametrize("table,gen,counter", [
    ("investor", "generate_investors", "investor"),
    ("fund", "generate_funds", "fund"),
])
def test_simple_generators_are_idempotent(fresh_state, read_csv, monkeypatch, data_root, table, gen, counter):
    fn = getattr(rd, gen)
    first = [dict(r) for r in fn(fresh_state)]
    count = fresh_state["counters"][counter]

    second = fn(fresh_state)

    assert second == first
    assert fresh_state["counters"][counter] == count
    assert len(read_csv(table)) == len(first)

    monkeypatch.setenv("BUSINESS_DATE", "2025-01-07")
    fn(fresh_state)
    next_day = read_csv(table, "2025-01-07")
    assert next_day.equals(read_csv(table))


def test_dependent_generators_are_idempotent(populated_state, tickers_today):
    snapshot = {k: [dict(r) for r in populated_state[k]]
                for k in ("commitments", "portfolio_companies")}
    counters = dict(populated_state["counters"])

    assert rd.generate_commitments(populated_state) == snapshot["commitments"]
    assert rd.generate_portfolio_companies(populated_state, list(tickers_today)) == snapshot["portfolio_companies"]
    assert populated_state["counters"] == counters
    assert isinstance(pd.DataFrame(populated_state["commitments"]), pd.DataFrame)
