from datetime import datetime

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy


class Intp20Stage6FiveMinutePortfolioStrategy(IStrategy):
    """
    Native validation for the Stage-6 coarse 5m candidate portfolio.

    The repository currently has 1m, 15m, and 1h data. This strategy runs on
    1m candles and internally resamples to 5m so it can validate the 5m coarse
    screener without downloading an extra 5m dataset.
    """

    INTERFACE_VERSION = 3

    timeframe = "1m"
    startup_candle_count = 1500
    can_short = True

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    position_adjustment_enable = False
    max_entry_position_adjustment = 0

    minimal_roi = {"0": 10.0}
    stoploss = -0.80
    trailing_stop = False

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    order_time_in_force = {
        "entry": "gtc",
        "exit": "gtc",
    }

    @staticmethod
    def _resample_5m(dataframe: DataFrame) -> DataFrame:
        resampled = (
            dataframe.set_index("date")
            .resample("5min", label="right", closed="right")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna()
            .reset_index()
        )
        return resampled

    @staticmethod
    def _add_5m_indicators(dataframe: DataFrame) -> DataFrame:
        dataframe = dataframe.copy()
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_100"] = ta.EMA(dataframe, timeperiod=100)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi_2"] = ta.RSI(dataframe, timeperiod=2)
        dataframe["rsi_fast"] = ta.RSI(dataframe, timeperiod=4)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["volume_mean_48"] = dataframe["volume"].rolling(48).mean()
        dataframe["volume_mean_96"] = dataframe["volume"].rolling(96).mean()
        dataframe["volume_z"] = (
            (dataframe["volume"] - dataframe["volume_mean_96"])
            / dataframe["volume"].rolling(96).std()
        )

        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_low"] = bollinger["lower"]
        dataframe["bb_mid"] = bollinger["mid"]
        dataframe["bb_high"] = bollinger["upper"]
        dataframe["bb_width"] = (dataframe["bb_high"] - dataframe["bb_low"]) / dataframe["bb_mid"]
        dataframe["bb_width_mean_96"] = dataframe["bb_width"].rolling(96).mean()

        dataframe["don_high_12"] = dataframe["high"].rolling(12).max().shift(1)
        dataframe["don_low_12"] = dataframe["low"].rolling(12).min().shift(1)
        dataframe["roc_3"] = dataframe["close"] / dataframe["close"].shift(3) - 1
        dataframe["roc_12"] = dataframe["close"] / dataframe["close"].shift(12) - 1
        dataframe["roc_24"] = dataframe["close"] / dataframe["close"].shift(24) - 1
        dataframe["roc_48"] = dataframe["close"] / dataframe["close"].shift(48) - 1
        dataframe["ema_20_slope"] = dataframe["ema_20"] / dataframe["ema_20"].shift(12) - 1
        dataframe["ema_50_slope"] = dataframe["ema_50"] / dataframe["ema_50"].shift(24) - 1
        dataframe["range_pct"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"]
        dataframe["body_pct"] = (dataframe["close"] - dataframe["open"]).abs() / dataframe["close"]
        dataframe["upper_wick_pct"] = (
            dataframe["high"] - dataframe[["open", "close"]].max(axis=1)
        ) / dataframe["close"]
        dataframe["lower_wick_pct"] = (
            dataframe[["open", "close"]].min(axis=1) - dataframe["low"]
        ) / dataframe["close"]

        low_14 = dataframe["low"].rolling(14).min()
        high_14 = dataframe["high"].rolling(14).max()
        dataframe["stoch_k"] = 100 * (dataframe["close"] - low_14) / (high_14 - low_14)
        typical_price = qtpylib.typical_price(dataframe)
        money_flow = typical_price * dataframe["volume"]
        positive_flow = money_flow.where(typical_price > typical_price.shift(), 0.0)
        negative_flow = money_flow.where(typical_price < typical_price.shift(), 0.0)
        money_ratio = (
            positive_flow.rolling(14).sum()
            / negative_flow.rolling(14).sum().replace(0, np.nan)
        )
        dataframe["mfi"] = 100 - (100 / (1 + money_ratio))

        dataframe["local_up"] = (
            (dataframe["close"] > dataframe["ema_50"])
            & (dataframe["ema_20"] > dataframe["ema_50"])
            & (dataframe["ema_20_slope"] > 0)
        )
        dataframe["local_down"] = (
            (dataframe["close"] < dataframe["ema_50"])
            & (dataframe["ema_20"] < dataframe["ema_50"])
            & (dataframe["ema_20_slope"] < 0)
        )
        dataframe["local_chop"] = (
            ~dataframe["local_up"]
            & ~dataframe["local_down"]
            & (dataframe["bb_width"] < dataframe["bb_width_mean_96"] * 1.10)
        )
        dataframe["market_bull"] = (
            (dataframe["close"] > dataframe["ema_200"])
            & (dataframe["ema_50_slope"] > 0)
            & (dataframe["rsi"] > 45)
        )
        dataframe["market_bear"] = (
            (dataframe["close"] < dataframe["ema_200"])
            & (dataframe["ema_50_slope"] < 0)
            & (dataframe["rsi"] < 55)
        )
        dataframe["market_panic_down"] = (dataframe["roc_48"] < -0.035) | (
            dataframe["roc_24"] < -0.025
        )
        dataframe["market_euphoria_up"] = (dataframe["roc_48"] > 0.035) | (
            dataframe["roc_24"] > 0.025
        )
        return dataframe

    @staticmethod
    def _panic_long(dataframe: DataFrame, shock: float, atr_floor: float, atr_ceiling: float) -> DataFrame:
        return (
            (dataframe["atr_pct"] > atr_floor)
            & (dataframe["atr_pct"] < atr_ceiling)
            & (dataframe["volume_z"] > 0.8)
            & (dataframe["range_pct"] > dataframe["atr_pct"] * 0.85)
            & (dataframe["roc_3"] < -shock)
            & (dataframe["low"] < dataframe["don_low_12"])
            & (dataframe["lower_wick_pct"] > dataframe["body_pct"] * 1.4)
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["rsi_fast"] < 28)
        )

    @staticmethod
    def _panic_short(dataframe: DataFrame, shock: float, atr_floor: float, atr_ceiling: float) -> DataFrame:
        return (
            (dataframe["atr_pct"] > atr_floor)
            & (dataframe["atr_pct"] < atr_ceiling)
            & (dataframe["volume_z"] > 0.8)
            & (dataframe["range_pct"] > dataframe["atr_pct"] * 0.85)
            & (dataframe["roc_3"] > shock)
            & (dataframe["high"] > dataframe["don_high_12"])
            & (dataframe["upper_wick_pct"] > dataframe["body_pct"] * 1.4)
            & (dataframe["close"] < dataframe["open"])
            & (dataframe["rsi_fast"] > 72)
        )

    @staticmethod
    def _rsi_reversion_long(dataframe: DataFrame, atr_ceiling: float) -> DataFrame:
        return (
            (dataframe["atr_pct"] > 0.0006)
            & (dataframe["atr_pct"] < atr_ceiling)
            & (dataframe["volume"] > dataframe["volume_mean_48"] * 0.7)
            & (dataframe["bb_width"] > 0.0035)
            & (dataframe["low"] < dataframe["bb_low"] * 0.998)
            & (dataframe["rsi_2"] < 8)
            & (dataframe["stoch_k"] < 28)
            & (dataframe["mfi"] < 35)
            & (dataframe["roc_12"] > -0.045)
            & (dataframe["close"] > dataframe["low"] + (dataframe["high"] - dataframe["low"]) * 0.35)
        )

    @staticmethod
    def _rsi_reversion_short(dataframe: DataFrame, atr_ceiling: float) -> DataFrame:
        return (
            (dataframe["atr_pct"] > 0.0006)
            & (dataframe["atr_pct"] < atr_ceiling)
            & (dataframe["volume"] > dataframe["volume_mean_48"] * 0.7)
            & (dataframe["bb_width"] > 0.0035)
            & (dataframe["high"] > dataframe["bb_high"] / 0.998)
            & (dataframe["rsi_2"] > 92)
            & (dataframe["stoch_k"] > 72)
            & (dataframe["mfi"] > 65)
            & (dataframe["roc_12"] < 0.045)
            & (dataframe["close"] < dataframe["high"] - (dataframe["high"] - dataframe["low"]) * 0.35)
        )

    @staticmethod
    def _build_pair_signals(dataframe: DataFrame, pair: str) -> DataFrame:
        dataframe = dataframe.copy()
        dataframe["stage6_enter_long"] = False
        dataframe["stage6_enter_short"] = False
        dataframe["stage6_enter_tag"] = None

        if pair.startswith("XTZ/"):
            mask = Intp20Stage6FiveMinutePortfolioStrategy._panic_long(dataframe, 0.004, 0.001, 0.030)
            mask &= dataframe["btc_market_bear"].fillna(False)
            dataframe.loc[mask, ["stage6_enter_long", "stage6_enter_tag"]] = (True, "xtz_panic_long_5m")

        if pair.startswith("SOL/"):
            mask = Intp20Stage6FiveMinutePortfolioStrategy._panic_short(dataframe, 0.004, 0.002, 0.030)
            mask &= dataframe["btc_market_bull"].fillna(False)
            dataframe.loc[mask, ["stage6_enter_short", "stage6_enter_tag"]] = (True, "sol_panic_short_5m")

        if pair.startswith("SUI/"):
            mask = Intp20Stage6FiveMinutePortfolioStrategy._rsi_reversion_short(dataframe, 0.014)
            mask &= dataframe["local_chop"].fillna(False)
            dataframe.loc[mask, ["stage6_enter_short", "stage6_enter_tag"]] = (True, "sui_rsi_short_5m")

        if pair.startswith("XRP/"):
            mask = Intp20Stage6FiveMinutePortfolioStrategy._rsi_reversion_short(dataframe, 0.024)
            mask &= dataframe["btc_market_euphoria_up"].fillna(False)
            dataframe.loc[mask, ["stage6_enter_short", "stage6_enter_tag"]] = (True, "xrp_rsi_short_5m")

        if pair.startswith("LINK/"):
            mask = Intp20Stage6FiveMinutePortfolioStrategy._panic_long(dataframe, 0.007, 0.001, 0.030)
            mask &= dataframe["btc_market_bear"].fillna(False)
            dataframe.loc[mask, ["stage6_enter_long", "stage6_enter_tag"]] = (True, "link_panic_long_5m")

        if pair.startswith("AAVE/"):
            mask = Intp20Stage6FiveMinutePortfolioStrategy._panic_long(dataframe, 0.007, 0.001, 0.030)
            mask &= dataframe["btc_market_bear"].fillna(False)
            dataframe.loc[mask, ["stage6_enter_long", "stage6_enter_tag"]] = (True, "aave_panic_long_5m")

        if pair.startswith("COMP/"):
            mask = Intp20Stage6FiveMinutePortfolioStrategy._rsi_reversion_long(dataframe, 0.024)
            mask &= dataframe["btc_market_panic_down"].fillna(False)
            dataframe.loc[mask, ["stage6_enter_long", "stage6_enter_tag"]] = (True, "comp_rsi_long_5m")

        return dataframe

    def _btc_5m_regime(self) -> DataFrame:
        if not self.dp:
            return DataFrame()
        btc = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe=self.timeframe)
        btc_5m = self._add_5m_indicators(self._resample_5m(btc))
        return btc_5m[
            [
                "date",
                "market_bull",
                "market_bear",
                "market_panic_down",
                "market_euphoria_up",
            ]
        ].rename(
            columns={
                "market_bull": "btc_market_bull",
                "market_bear": "btc_market_bear",
                "market_panic_down": "btc_market_panic_down",
                "market_euphoria_up": "btc_market_euphoria_up",
            }
        )

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        pair_5m = self._add_5m_indicators(self._resample_5m(dataframe))
        btc_5m = self._btc_5m_regime()
        if not btc_5m.empty:
            pair_5m = pair_5m.merge(btc_5m, on="date", how="left")
            btc_columns = [column for column in pair_5m.columns if column.startswith("btc_")]
            pair_5m[btc_columns] = pair_5m[btc_columns].ffill().fillna(False)
        else:
            for column in (
                "btc_market_bull",
                "btc_market_bear",
                "btc_market_panic_down",
                "btc_market_euphoria_up",
            ):
                pair_5m[column] = False

        signals = self._build_pair_signals(pair_5m, pair)[
            ["date", "stage6_enter_long", "stage6_enter_short", "stage6_enter_tag"]
        ]
        dataframe = dataframe.merge(signals, on="date", how="left")
        dataframe["stage6_enter_long"] = dataframe["stage6_enter_long"].fillna(False)
        dataframe["stage6_enter_short"] = dataframe["stage6_enter_short"].fillna(False)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        long_mask = dataframe["stage6_enter_long"]
        dataframe.loc[long_mask, "enter_long"] = 1
        dataframe.loc[long_mask, "enter_tag"] = dataframe.loc[long_mask, "stage6_enter_tag"]

        short_mask = dataframe["stage6_enter_short"]
        dataframe.loc[short_mask, "enter_short"] = 1
        dataframe.loc[short_mask, "enter_tag"] = dataframe.loc[short_mask, "stage6_enter_tag"]
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool | None:
        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        if trade_minutes >= 120:
            return f"{trade.enter_tag}_fixed_hold_exit"
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
        return min(4.0, max_leverage)
