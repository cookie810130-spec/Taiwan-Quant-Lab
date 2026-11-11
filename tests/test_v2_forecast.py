from datetime import date, timedelta
import math

import pandas as pd
import pytest

from quantlab.data.sample import make_sample_data
from quantlab.v2.forecast import predict_scenarios
from quantlab.v2.storage import check_symbol, import_csv, read_prices, list_symbols


def data():
    return make_sample_data(date(2021, 1, 1), date(2026, 1, 1), "2330")


def test_scenario_reproducible_and_exclusive():
    frame = data()
    a = predict_scenarios(frame, "2330", "demo", 20, 250, 7)
    b = predict_scenarios(frame, "2330", "demo", 20, 250, 7)
    assert a == b
    assert a["synthetic_data"] is True
    s = a["simulation"]["scenario_frequency"]
    assert abs(sum(s.values()) - 1) < 0.0002
    assert a["simulation"]["terminal_price_p05"] <= a["simulation"]["terminal_price_p50"] <= a["simulation"]["terminal_price_p95"]
    assert a["ml_direction"]["probability_up"] is not None
    assert 0 <= a["ml_direction"]["probability_up"] <= 1
    assert a["ml_direction"]["holdout_rows"] >= 30


def test_bad_inputs():
    frame = data()
    for h in [0, 3, 100]:
        with pytest.raises(ValueError):
            predict_scenarios(frame, "2330", "demo", h, 250)
    with pytest.raises(ValueError):
        predict_scenarios(frame, "2330", "demo", 20, 10)
    with pytest.raises(ValueError):
        predict_scenarios(frame.iloc[:50], "2330", "demo", 20, 250)


def test_different_seeds_change_scenario_distribution():
    frame = data()
    a = predict_scenarios(frame, "2330", "demo", 20, 250, 7)
    b = predict_scenarios(frame, "2330", "demo", 20, 250, 8)
    assert a["simulation"]["terminal_price_p50"] != b["simulation"]["terminal_price_p50"]


def test_import_and_read_user_csv(tmp_path):
    frame = data().iloc[:250]
    csv = tmp_path / "2330.csv"
    db = tmp_path / "test.duckdb"
    frame.to_csv(csv, index=False)
    assert import_csv("2330", str(csv), db)["imported_rows"] == 250
    assert import_csv("2330", str(csv), db)["imported_rows"] == 250
    loaded = read_prices("2330", db)
    assert len(loaded) == 250
    assert len(list_symbols(db)) == 1
    assert list_symbols(db)[0]["provenance"] == "user_csv_unverified"


@pytest.mark.parametrize("bad", ["../2330", "2330/abc", "", "a?b"])
def test_reject_pathlike_symbols(bad):
    with pytest.raises(ValueError):
        check_symbol(bad)
