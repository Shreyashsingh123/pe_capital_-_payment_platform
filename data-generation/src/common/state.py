"""
Persisted state so each daily run builds on the last one, instead of
regenerating an unrelated random snapshot every time. Committed to the
repo (state/state.json) so the whole team shares one continuous history.
"""
import json
import os
from .config import STATE_PATH

DEFAULT_STATE = {
    "investors": [],
    "funds": [],
    "commitments": [],          # each tracks committed / contributed_total / invested_total
    "portfolio_companies": [],
    "counters": {
        "investor": 0,
        "fund": 0,
        "commitment": 0,
        "company": 0,
        "payment": 0,
    },
    "last_business_date": None,
}


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return dict(DEFAULT_STATE)
    with open(STATE_PATH, "r") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, default=str)


def next_id(state: dict, table: str, prefix: str, width: int = 4) -> str:
    """Increments and returns e.g. 'LP_0001', 'PMT_000001'."""
    state["counters"][table] += 1
    n = state["counters"][table]
    return f"{prefix}_{n:0{width}d}"
