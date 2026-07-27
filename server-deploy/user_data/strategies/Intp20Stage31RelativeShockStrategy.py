from __future__ import annotations

from datetime import datetime

from pandas import DataFrame

from freqtrade.enums import CandleType
from freqtrade.strategy import IStrategy


class Intp20Stage31RelativeShockStrategy(IStrategy):
    """Trade short-lived, volume-backed dislocations relative to BTC."""

    INTERFACE_VERSION = 3

    timeframe = "1m"
    can_short = True
    startup_candle_count = 240
    process_only_new_candles = True

    minimal_roi = {"0": 10.0}
    stoploss = -0.60
    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    order_types = {
        "entry": "market",
        "exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "gtc", "exit": "gtc"}

    btc_pair = "BTC/USDT:USDT"
    relative_lookback = 30
    volume_lookback = 240
    long_shock = -0.025
    short_shock = 0.060
    volume_ratio_floor = 2.0
    long_hold_minutes = 60
    short_hold_minutes = 30
    fixed_leverage = 3.0

    def informative_pairs(self) -> list[tuple[str, str, CandleType]]:
        return [(self.btc_pair, self.timeframe, CandleType.FUTURES)]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["stage31_volume_ratio"] = dataframe["volume"] / (
            dataframe["volume"].rolling(self.volume_lookback).median()
        )

        btc_close = None
        if self.dp:
            btc = self.dp.get_pair_dataframe(pair=self.btc_pair, timeframe=self.timeframe)
            if not btc.empty:
                btc_close = btc.set_index("date")["close"].reindex(dataframe["date"]).to_numpy()

        if btc_close is None:
            dataframe["stage31_relative_return"] = 0.0
            return dataframe

        pair_return = dataframe["close"] / dataframe["close"].shift(self.relative_lookback)
        btc_series = dataframe["close"].copy()
        btc_series[:] = btc_close
        btc_return = btc_series / btc_series.shift(self.relative_lookback)
        dataframe["stage31_relative_return"] = pair_return / btc_return - 1.0
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        relative_return = dataframe["stage31_relative_return"]
        liquid_shock = dataframe["stage31_volume_ratio"] > self.volume_ratio_floor
        has_volume = dataframe["volume"] > 0

        long_entry = (
            has_volume
            & liquid_shock
            & (relative_return < self.long_shock)
            & (relative_return.shift(1) >= self.long_shock)
        )
        short_entry = (
            has_volume
            & liquid_shock
            & (relative_return > self.short_shock)
            & (relative_return.shift(1) <= self.short_shock)
        )

        dataframe.loc[long_entry, ["enter_long", "enter_tag"]] = (
            1,
            "stage31_relative_shock_long",
        )
        dataframe.loc[short_entry, ["enter_short", "enter_tag"]] = (
            1,
            "stage31_relative_shock_short",
        )
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        dataframe["exit_tag"] = ""
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | None:
        age_minutes = (current_time - trade.open_date_utc).total_seconds() / 60.0
        hold_minutes = (
            self.short_hold_minutes
            if trade.enter_tag == "stage31_relative_shock_short"
            else self.long_hold_minutes
        )
        if age_minutes >= hold_minutes:
            return "stage31_fixed_horizon"
        return None

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        return max(1.0, min(self.fixed_leverage, max_leverage))
