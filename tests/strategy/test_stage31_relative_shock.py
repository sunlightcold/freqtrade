from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pandas as pd

from user_data.strategies.Intp20Stage31RelativeShockStrategy import (
    Intp20Stage31RelativeShockStrategy,
)


def test_stage31_marks_crossing_shocks_on_both_sides():
    strategy = Intp20Stage31RelativeShockStrategy({})
    dataframe = pd.DataFrame(
        {
            "volume": [1.0, 3.0, 3.0, 3.0],
            "stage31_volume_ratio": [1.0, 2.1, 2.1, 2.1],
            "stage31_relative_return": [0.0, -0.026, 0.0, 0.061],
        }
    )

    result = strategy.populate_entry_trend(dataframe, {"pair": "FET/USDT:USDT"})

    assert result.loc[1, "enter_long"] == 1
    assert result.loc[1, "enter_tag"] == "stage31_relative_shock_long"
    assert result.loc[3, "enter_short"] == 1
    assert result.loc[3, "enter_tag"] == "stage31_relative_shock_short"


def test_stage31_exits_each_side_at_its_fixed_horizon():
    strategy = Intp20Stage31RelativeShockStrategy({})
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    long_trade = SimpleNamespace(
        open_date_utc=opened,
        enter_tag="stage31_relative_shock_long",
    )
    short_trade = SimpleNamespace(
        open_date_utc=opened,
        enter_tag="stage31_relative_shock_short",
    )

    assert (
        strategy.custom_exit("FET/USDT:USDT", long_trade, opened + timedelta(minutes=59), 1, 0)
        is None
    )
    assert (
        strategy.custom_exit("FET/USDT:USDT", long_trade, opened + timedelta(minutes=60), 1, 0)
        == "stage31_fixed_horizon"
    )
    assert (
        strategy.custom_exit("FET/USDT:USDT", short_trade, opened + timedelta(minutes=30), 1, 0)
        == "stage31_fixed_horizon"
    )
