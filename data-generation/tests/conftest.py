import copy
import hashlib
import random
from pathlib import Path

import pandas as pd
import pytest
from faker import Faker

import src.common.config as config_mod
import src.common.state as state_mod
import src.main as main_mod

BUSINESS_DATE = "2025-01-06"
DG_ROOT = Path(__file__).resolve().parents[1]
REAL_STATE = DG_ROOT / "state" / "state.json"
REAL_DATA = DG_ROOT / "data"


def _sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


@pytest.fixture(scope="session", autouse=True)
def real_state_untouched():
    """Fail the session if any test touched the real state file or data dir."""
    before = (_sha(REAL_STATE), REAL_DATA.exists())
    yield
    assert (_sha(REAL_STATE), REAL_DATA.exists()) == before, \
        "tests modified the real state/state.json or created data-generation/data"


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr(state_mod, "STATE_PATH", str(tmp_path / "state" / "state.json"))
    data_root = str(tmp_path / "data")
    monkeypatch.setattr(config_mod, "DATA_ROOT", data_root)
    monkeypatch.setattr(main_mod, "DATA_ROOT", data_root)
    monkeypatch.setenv("BUSINESS_DATE", BUSINESS_DATE)
    # A developer .env loaded at import time must never leak credentials in.
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("ADLS_CONTAINER", raising=False)
    # load_state() returns a shallow copy of DEFAULT_STATE; keep it pristine per test.
    monkeypatch.setattr(state_mod, "DEFAULT_STATE", copy.deepcopy(state_mod.DEFAULT_STATE))
    random.seed(1234)
    Faker.seed(1234)


@pytest.fixture
def business_date():
    return BUSINESS_DATE


@pytest.fixture
def data_root():
    return Path(config_mod.DATA_ROOT)


@pytest.fixture
def fresh_state():
    return copy.deepcopy(state_mod.DEFAULT_STATE)


@pytest.fixture
def tickers_today():
    return {"AAPL": 190.1234, "MSFT": 410.5}


@pytest.fixture
def populated_state(fresh_state, tickers_today):
    from src.generators.reference_data import (
        generate_commitments, generate_funds, generate_investors,
        generate_portfolio_companies,
    )
    generate_investors(fresh_state)
    generate_funds(fresh_state)
    generate_commitments(fresh_state)
    generate_portfolio_companies(fresh_state, list(tickers_today))
    return fresh_state


@pytest.fixture
def read_csv(data_root, business_date):
    def _read(table, date=None):
        date = date or business_date
        return pd.read_csv(data_root / table / f"ingestion_date={date}" / f"{table}.csv")
    return _read
