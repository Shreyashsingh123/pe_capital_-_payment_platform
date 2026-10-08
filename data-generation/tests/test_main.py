import json
import os
import runpy
import sys

import pandas as pd
import pytest

import src.main as main
from src.common import config, state as state_mod

PRICES = {"AAPL": 190.0, "MSFT": 410.0}
FOLDERS = ["market_price", "investor", "fund", "commitment", "portfolio_company", "payment"]


@pytest.fixture
def stubs(monkeypatch):
    """Stub the only two network seams in run(): market data fetch and ADLS upload."""
    uploads = []
    fetches = []

    def fake_fetch():
        fetches.append(1)
        config.partitioned_path("market_price", config.get_business_date())
        return dict(PRICES)

    monkeypatch.setattr(main, "fetch_market_data", fake_fetch)
    monkeypatch.setattr(main, "upload_folder", lambda local, rel: uploads.append((local, rel)))
    return uploads


def saved_state():
    with open(state_mod.STATE_PATH) as f:
        return json.load(f)


def test_run_end_to_end(stubs, capsys, read_csv):
    main.run()

    out = capsys.readouterr().out
    assert "=== Daily generation run for 2025-01-06 ===" in out
    assert "=== Run complete for 2025-01-06 ===" in out
    s = saved_state()
    assert s["last_business_date"] == "2025-01-06"
    assert len(s["investors"]) == 50
    assert len(s["funds"]) == 5
    assert len(s["commitments"]) >= 40
    assert len(s["portfolio_companies"]) == 30
    payments = read_csv("payment")
    assert s["counters"]["payment"] == len(payments)
    for table in ("investor", "fund", "commitment", "portfolio_company"):
        assert len(read_csv(table)) > 0
    assert {c["benchmark_ticker"] for c in s["portfolio_companies"]} <= {"AAPL", "MSFT", None}
    assert stubs == []  # upload off by default


def test_run_with_upload_uploads_every_partition(stubs, data_root):
    main.run(upload=True)

    expected = [
        (os.path.join(config.DATA_ROOT, f, "ingestion_date=2025-01-06"), f"{f}/ingestion_date=2025-01-06")
        for f in FOLDERS
    ]
    assert sorted(stubs) == sorted(expected)


def test_upload_skips_missing_partitions(monkeypatch, stubs):
    monkeypatch.setattr(main, "fetch_market_data", lambda: dict(PRICES))  # writes no market_price dir
    main.run(upload=True)
    assert len(stubs) == 5
    assert not any(rel.startswith("market_price/") for _, rel in stubs)


def test_run_call_order(monkeypatch):
    calls = []
    tickers = {"AAA": 1.0, "BBB": 2.0}
    sentinel_state = {"last_business_date": None}
    companies = [{"company_id": "PORT_0001"}]

    monkeypatch.setattr(main, "load_state", lambda: calls.append("load") or sentinel_state)
    monkeypatch.setattr(main, "fetch_market_data", lambda: calls.append("fetch") or tickers)
    monkeypatch.setattr(main, "generate_investors", lambda s: calls.append("investors"))
    monkeypatch.setattr(main, "generate_funds", lambda s: calls.append("funds"))
    monkeypatch.setattr(main, "generate_commitments", lambda s: calls.append("commitments"))

    def fake_companies(s, t):
        calls.append(("companies", list(t)))
        return companies

    def fake_payments(s, c, t):
        calls.append(("payments", c, t))

    def fake_save(s):
        calls.append(("save", s["last_business_date"]))

    monkeypatch.setattr(main, "generate_portfolio_companies", fake_companies)
    monkeypatch.setattr(main, "generate_payments", fake_payments)
    monkeypatch.setattr(main, "save_state", fake_save)

    main.run()

    assert calls == [
        "load", "fetch", "investors", "funds", "commitments",
        ("companies", ["AAA", "BBB"]),
        ("payments", companies, tickers),
        ("save", "2025-01-06"),
    ]


def test_second_day_continues_from_saved_state(stubs, monkeypatch, data_root):
    main.run()
    day1 = saved_state()

    monkeypatch.setenv("BUSINESS_DATE", "2025-01-07")
    main.run()
    day2 = saved_state()

    assert day2["last_business_date"] == "2025-01-07"
    assert day2["investors"] == day1["investors"]
    assert day2["counters"]["investor"] == 50
    assert day2["counters"]["payment"] >= day1["counters"]["payment"]
    p1 = pd.read_csv(data_root / "payment" / "ingestion_date=2025-01-06" / "payment.csv")
    p2 = pd.read_csv(data_root / "payment" / "ingestion_date=2025-01-07" / "payment.csv")
    assert set(p1.payment_id).isdisjoint(p2.payment_id)
    assert day2["counters"]["payment"] == len(p1) + len(p2)
    assert (data_root / "investor" / "ingestion_date=2025-01-07").is_dir()


def test_existing_state_is_loaded_and_overwritten(stubs):
    os.makedirs(os.path.dirname(state_mod.STATE_PATH))
    with open(state_mod.STATE_PATH, "w") as f:
        json.dump({**state_mod.DEFAULT_STATE, "last_business_date": "2024-12-31"}, f)
    main.run()
    assert saved_state()["last_business_date"] == "2025-01-06"


# ---- CLI (__main__ block) -------------------------------------------

@pytest.fixture
def cli(monkeypatch, stubs):
    """Run src.main as __main__. The re-executed module re-imports its collaborators,
    so the stubs are installed on the source modules, and load_dotenv is neutralised."""
    import dotenv
    import src.common.adls_upload as adls
    import src.generators.market_price as mp

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(mp, "fetch_market_data", lambda: dict(PRICES))
    monkeypatch.setattr(adls, "upload_folder", lambda local, rel: stubs.append((local, rel)))
    monkeypatch.delitem(sys.modules, "src.main", raising=False)

    def invoke(*args):
        monkeypatch.setattr(sys, "argv", ["main", *args])
        runpy.run_module("src.main", run_name="__main__")

    return invoke


def test_cli_without_flag_does_not_upload(cli, stubs):
    cli()
    assert saved_state()["last_business_date"] == "2025-01-06"
    assert stubs == []


def test_cli_upload_flag_uploads(cli, stubs):
    cli("--upload")
    assert len(stubs) == 5  # the stubbed fetch writes no market_price partition
    assert all(rel.endswith("ingestion_date=2025-01-06") for _, rel in stubs)


def test_cli_rejects_unknown_flag(cli):
    with pytest.raises(SystemExit) as exc:
        cli("--bogus")
    assert exc.value.code == 2
