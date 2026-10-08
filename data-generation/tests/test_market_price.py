import runpy
import sys

import pandas as pd
import pytest

import src.generators.market_price as mp


def make_frame(base=1.234567):
    idx = pd.date_range("2025-01-06 14:30", periods=3, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "Open": [base, base + 1, base + 2],
            "High": [base + 0.1] * 3,
            "Low": [base - 0.1] * 3,
            "Close": [base + 0.5, base + 1.5, base + 2.123456],
            "Volume": [100.0, 200.0, 300.0],
        },
        index=idx,
    )


class FakeTicker:
    """Scripted yf.Ticker replacement: behaviours maps symbol -> list of results/exceptions."""
    behaviours = {}
    calls = []

    def __init__(self, symbol):
        self.symbol = symbol

    def history(self, period, interval):
        FakeTicker.calls.append((self.symbol, period, interval))
        queue = FakeTicker.behaviours[self.symbol]
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def fake_yf(monkeypatch):
    FakeTicker.behaviours = {}
    FakeTicker.calls = []
    sleeps = []
    monkeypatch.setattr(mp.yf, "Ticker", FakeTicker)
    monkeypatch.setattr(mp.time, "sleep", sleeps.append)
    monkeypatch.setattr(mp, "TICKERS", ["AAA", "BBB"])
    FakeTicker.sleeps = sleeps
    return FakeTicker


def test_success_writes_csv_and_returns_latest_close(fake_yf, read_csv):
    frame = make_frame()
    fake_yf.behaviours = {"AAA": [frame], "BBB": [frame]}

    result = mp.fetch_market_data()

    assert result == {"AAA": round(frame["Close"].iloc[-1], 4), "BBB": round(frame["Close"].iloc[-1], 4)}
    df = read_csv("market_price")
    assert list(df.columns) == ["ticker", "bar_timestamp", "open", "high", "low", "close", "volume"]
    assert len(df) == 6
    assert (df.groupby("ticker").size() == 3).all()
    aaa = df[df.ticker == "AAA"].reset_index(drop=True)
    assert aaa.bar_timestamp[0] == frame.index[0].isoformat()
    assert aaa.open[0] == 1.2346  # rounded to 4 dp
    assert aaa.close[2] == round(frame["Close"].iloc[2], 4)
    assert pd.api.types.is_integer_dtype(df.volume)
    assert list(aaa.volume) == [100, 200, 300]
    assert fake_yf.sleeps == []
    assert {(c[1], c[2]) for c in fake_yf.calls} == {("1d", "1h")}


def test_retry_after_exception(fake_yf, capsys):
    fake_yf.behaviours = {"AAA": [RuntimeError("boom"), make_frame()], "BBB": [make_frame()]}

    result = mp.fetch_market_data()

    assert set(result) == {"AAA", "BBB"}
    assert fake_yf.sleeps == [5]
    assert "AAA attempt 1 failed: boom" in capsys.readouterr().out


def test_empty_frames_exhaust_retries_and_skip(fake_yf, read_csv, capsys):
    fake_yf.behaviours = {"AAA": [pd.DataFrame()], "BBB": [make_frame()]}

    result = mp.fetch_market_data(retries=3, delay_seconds=2)

    assert set(result) == {"BBB"}
    assert [c for c in fake_yf.calls if c[0] == "AAA"].__len__() == 3
    assert fake_yf.sleeps == [2, 2, 2]
    assert "Skipping AAA" in capsys.readouterr().out
    df = read_csv("market_price")
    assert set(df.ticker) == {"BBB"}


def test_retries_one_means_single_call(fake_yf):
    fake_yf.behaviours = {"AAA": [pd.DataFrame()], "BBB": [pd.DataFrame()]}
    mp.fetch_market_data(retries=1)
    assert len(fake_yf.calls) == 2


def test_all_tickers_fail_still_writes_file(fake_yf, data_root, business_date):
    fake_yf.behaviours = {"AAA": [RuntimeError("x")], "BBB": [RuntimeError("y")]}

    assert mp.fetch_market_data(retries=2) == {}

    path = data_root / "market_price" / f"ingestion_date={business_date}" / "market_price.csv"
    assert path.exists()
    assert path.read_text().strip() == ""


def test_business_date_selects_partition(fake_yf, data_root, monkeypatch):
    fake_yf.behaviours = {"AAA": [make_frame()], "BBB": [make_frame()]}
    monkeypatch.setenv("BUSINESS_DATE", "2026-03-04")
    mp.fetch_market_data()
    assert (data_root / "market_price" / "ingestion_date=2026-03-04" / "market_price.csv").exists()


def test_main_block_runs_fetch(monkeypatch, data_root, business_date):
    import src.common.config as config
    import yfinance

    FakeTicker.behaviours = {"ZZZ": [make_frame()]}
    FakeTicker.calls = []
    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)
    monkeypatch.setattr(config, "TICKERS", ["ZZZ"])
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.delitem(sys.modules, "src.generators.market_price", raising=False)

    runpy.run_module("src.generators.market_price", run_name="__main__")

    csv = data_root / "market_price" / f"ingestion_date={business_date}" / "market_price.csv"
    assert pd.read_csv(csv).ticker.unique().tolist() == ["ZZZ"]
