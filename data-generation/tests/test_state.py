import datetime
import json
import os

import pytest

import src.common.state as state


def test_load_state_missing_file_returns_defaults():
    assert not os.path.exists(state.STATE_PATH)
    loaded = state.load_state()
    assert loaded == state.DEFAULT_STATE
    assert loaded is not state.DEFAULT_STATE
    assert loaded["counters"] == {
        "investor": 0, "fund": 0, "commitment": 0, "company": 0, "payment": 0,
    }
    assert loaded["last_business_date"] is None


def test_save_state_creates_parent_dirs_and_indents():
    s = {"investors": [], "counters": {"payment": 3}}
    state.save_state(s)
    text = open(state.STATE_PATH).read()
    assert text == json.dumps(s, indent=2)
    assert '\n  "investors"' in text


def test_save_then_load_round_trip(fresh_state):
    fresh_state["counters"]["payment"] = 7
    fresh_state["last_business_date"] = "2025-01-06"
    state.save_state(fresh_state)
    assert state.load_state() == fresh_state


def test_save_state_stringifies_non_json_types():
    state.save_state({"when": datetime.date(2025, 1, 6)})
    assert state.load_state() == {"when": "2025-01-06"}


def test_load_state_reads_existing_content():
    os.makedirs(os.path.dirname(state.STATE_PATH))
    with open(state.STATE_PATH, "w") as f:
        json.dump({"last_business_date": "2024-12-31"}, f)
    assert state.load_state() == {"last_business_date": "2024-12-31"}


@pytest.mark.parametrize("prefix,width,expected", [
    ("LP", 4, "LP_0001"),
    ("FUND", 3, "FUND_001"),
    ("CMT", 5, "CMT_00001"),
    ("PMT", 6, "PMT_000001"),
])
def test_next_id_formats(fresh_state, prefix, width, expected):
    assert state.next_id(fresh_state, "investor", prefix, width=width) == expected


def test_next_id_sequential_and_independent(fresh_state):
    assert state.next_id(fresh_state, "investor", "LP") == "LP_0001"
    assert state.next_id(fresh_state, "investor", "LP") == "LP_0002"
    assert state.next_id(fresh_state, "fund", "FUND", width=3) == "FUND_001"
    assert fresh_state["counters"]["investor"] == 2
    assert fresh_state["counters"]["fund"] == 1


def test_next_id_does_not_truncate_wide_numbers(fresh_state):
    fresh_state["counters"]["investor"] = 12345
    assert state.next_id(fresh_state, "investor", "LP") == "LP_12346"


def test_next_id_unknown_table(fresh_state):
    with pytest.raises(KeyError):
        state.next_id(fresh_state, "unknown", "X")
