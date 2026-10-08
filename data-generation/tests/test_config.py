from datetime import date

import pytest

import src.common.config as config


def test_business_date_uses_env_override(monkeypatch):
    monkeypatch.setenv("BUSINESS_DATE", "2031-07-04")
    assert config.get_business_date() == "2031-07-04"


class _FakeDate:
    @staticmethod
    def today():
        return date(2030, 2, 3)


@pytest.mark.parametrize("env_value", [None, ""])
def test_business_date_falls_back_to_today(monkeypatch, env_value):
    if env_value is None:
        monkeypatch.delenv("BUSINESS_DATE", raising=False)
    else:
        monkeypatch.setenv("BUSINESS_DATE", env_value)
    monkeypatch.setattr(config, "date", _FakeDate)
    assert config.get_business_date() == "2030-02-03"


@pytest.mark.parametrize("table", list(config.TABLE_FOLDERS))
def test_partitioned_path_creates_folder(table, data_root):
    path = config.partitioned_path(table, "2025-01-06")
    expected = data_root / config.TABLE_FOLDERS[table] / "ingestion_date=2025-01-06"
    assert expected.is_dir()
    assert str(path).replace("\\", "/").endswith(
        f"{config.TABLE_FOLDERS[table]}/ingestion_date=2025-01-06"
    )
    # idempotent
    assert config.partitioned_path(table, "2025-01-06") == path


def test_partitioned_path_unknown_table():
    with pytest.raises(KeyError):
        config.partitioned_path("nope", "2025-01-06")


def test_constants_invariants():
    assert set(config.TABLE_FOLDERS) == {
        "market_price", "investor", "fund", "commitment", "portfolio_company", "payment",
    }
    assert config.TICKERS and len(config.TICKERS) == len(set(config.TICKERS))
    for lo, hi in (config.NUM_INITIAL_COMMITMENTS_PER_FUND, config.NEW_PAYMENTS_PER_RUN):
        assert 0 < lo <= hi
    assert config.PAYMENT_STATUSES == ["INITIATED", "SETTLED", "FAILED"]
    assert config.PAYMENT_TYPES == ["CAPITAL_CALL", "CONTRIBUTION", "INVESTMENT", "DISTRIBUTION"]
    assert len(config.INVESTOR_TYPES) == 4


def test_state_path_points_to_state_json():
    # config.STATE_PATH itself is never patched (state.py holds its own copy)
    normalised = config.STATE_PATH.replace("\\", "/")
    assert normalised.endswith("state/state.json")
