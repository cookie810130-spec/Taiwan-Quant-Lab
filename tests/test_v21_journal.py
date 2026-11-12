from datetime import date

import pandas as pd
import pytest

from quantlab.data.sample import make_sample_data
from quantlab.v2.forecast import predict_scenarios
from quantlab.v2.journal import save_forecast, mature_forecasts, scorecard, history
from quantlab.v2.storage import upsert_prices


def test_forecast_not_scored_until_actual_trading_day(tmp_path):
    db = tmp_path / "journal.duckdb"
    frame = make_sample_data(date(2021, 1, 1), date(2024, 8, 1), "2330")
    anchor = 280
    horizon = 20
    upsert_prices("2330", frame.iloc[:anchor], "twse_official", db)
    result = predict_scenarios(frame.iloc[:anchor], "2330", "twse_official",
                               horizon, 250, 19)
    first = save_forecast(result, db)
    assert first["saved"] is True
    again = save_forecast(result, db)
    assert again["saved"] is False
    assert again["id"] == first["id"]
    assert mature_forecasts(db)["pending"] == 1
    upsert_prices("2330", frame.iloc[anchor:anchor + 19], "twse_official", db)
    assert mature_forecasts(db)["evaluated_now"] == 0
    assert history("2330", db_path=db)[0]["status"] == "pending"
    upsert_prices("2330", frame.iloc[anchor + 19:anchor + 20], "twse_official", db)
    assert mature_forecasts(db)["evaluated_now"] == 1
    assert mature_forecasts(db)["evaluated_now"] == 0
    h = history("2330", db_path=db)[0]
    assert h["status"] == "evaluated"
    assert h["actual_date"] == str(frame.iloc[anchor + 19]["date"].date())
    assert h["actual_close"] == float(frame.iloc[anchor + 19]["close"])
    assert h["realized_up"] == (
        float(frame.iloc[anchor + 19]["close"]) > float(frame.iloc[anchor - 1]["close"]))
    s = scorecard(db)
    assert s["count_evaluated"] == 1
    assert s["count_pending"] == 0
    assert s["horizons"][0]["evaluated"] == 1


def test_synthetic_forecasts_never_journaled(tmp_path):
    db = tmp_path / "journal.duckdb"
    frame = make_sample_data(date(2021, 1, 1), date(2023, 1, 1), "2330")
    result = predict_scenarios(frame, "2330", "demo", 5, 250, 7)
    with pytest.raises(ValueError, match="合成"):
        save_forecast(result, db)
    assert history(db_path=db) == []


def test_empty_scorecard_and_history(tmp_path):
    db = tmp_path / "new.duckdb"
    assert scorecard(db)["count_evaluated"] == 0
    assert history(limit=10, db_path=db) == []
    with pytest.raises(ValueError):
        history(limit=0, db_path=db)
