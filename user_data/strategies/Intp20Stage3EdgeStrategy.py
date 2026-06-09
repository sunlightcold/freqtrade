from datetime import datetime

import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy


class Intp20Stage3EdgeStrategy(IStrategy):
    """
    Stage-3 edge validation strategy.

    This converts the fast walk-forward screener's best 15m single-pair rules
    into native Freqtrade signals. It is intentionally simple: entries are
    pair/template gated, exits use the screened fixed-hold window.
    """

    INTERFACE_VERSION = 3

    timeframe = "15m"
    startup_candle_count = 240
    can_short = True

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    position_adjustment_enable = False
    max_entry_position_adjustment = 0

    minimal_roi = {"0": 10.0}
    stoploss = -0.35
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

    hold_minutes = {
        "doge_meanrev_long": 24 * 15,
        "eth_squeeze_short": 24 * 15,
        "etc_breakout_short": 24 * 15,
        "op_vwap_short": 12 * 15,
        "comp_meanrev_short": 12 * 15,
        "trx_wick_short": 24 * 15,
        "ltc_meanrev_short": 24 * 15,
        "apt_vwap_short": 6 * 15,
    }

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 2,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 192,
                "trade_limit": 4,
                "stop_duration_candles": 48,
                "only_per_side": True,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 768,
                "trade_limit": 50,
                "stop_duration_candles": 96,
                "max_allowed_drawdown": 0.35,
            },
        ]

    @staticmethod
    def _add_common_indicators(dataframe: DataFrame) -> DataFrame:
        dataframe["ema_8"] = ta.EMA(dataframe, timeperiod=8)
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_34"] = ta.EMA(dataframe, timeperiod=34)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_100"] = ta.EMA(dataframe, timeperiod=100)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
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
        dataframe["don_high_34"] = dataframe["high"].rolling(34).max().shift(1)
        dataframe["don_low_34"] = dataframe["low"].rolling(34).min().shift(1)
        dataframe["roc_3"] = dataframe["close"] / dataframe["close"].shift(3) - 1
        dataframe["roc_6"] = dataframe["close"] / dataframe["close"].shift(6) - 1
        dataframe["roc_12"] = dataframe["close"] / dataframe["close"].shift(12) - 1
        dataframe["roc_24"] = dataframe["close"] / dataframe["close"].shift(24) - 1
        dataframe["ema_50_slope"] = dataframe["ema_50"] / dataframe["ema_50"].shift(24) - 1
        dataframe["range_pct"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"]
        dataframe["body_pct"] = (dataframe["close"] - dataframe["open"]).abs() / dataframe["close"]
        dataframe["upper_wick_pct"] = (
            dataframe["high"] - dataframe[["open", "close"]].max(axis=1)
        ) / dataframe["close"]

        typical_price = qtpylib.typical_price(dataframe)
        dataframe["vwap_96"] = (
            (typical_price * dataframe["volume"]).rolling(96).sum()
            / dataframe["volume"].rolling(96).sum()
        )
        dataframe["trend_up"] = (
            (dataframe["close"] > dataframe["ema_100"])
            & (dataframe["ema_50"] > dataframe["ema_200"])
        )
        dataframe["trend_down"] = (
            (dataframe["close"] < dataframe["ema_100"])
            & (dataframe["ema_50"] < dataframe["ema_200"])
        )
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return self._add_common_indicators(dataframe)

    @staticmethod
    def _mean_reversion_long(dataframe: DataFrame, atr_floor: float, bb_width: float) -> DataFrame:
        return (
            (dataframe["atr_pct"] > atr_floor)
            & (dataframe["bb_width"] > bb_width)
            & (dataframe["volume"] > dataframe["volume_mean_48"] * 0.6)
            & dataframe["trend_up"]
            & (dataframe["low"] < dataframe["bb_low"] * 0.998)
            & (dataframe["rsi"] < 42)
            & (dataframe["close"] > dataframe["close"].shift(1))
            & (dataframe["volume"] > 0)
        )

    @staticmethod
    def _mean_reversion_short(dataframe: DataFrame, atr_floor: float, bb_width: float) -> DataFrame:
        return (
            (dataframe["atr_pct"] > atr_floor)
            & (dataframe["bb_width"] > bb_width)
            & (dataframe["volume"] > dataframe["volume_mean_48"] * 0.6)
            & dataframe["trend_down"]
            & (dataframe["high"] > dataframe["bb_high"] / 0.998)
            & (dataframe["rsi"] > 58)
            & (dataframe["close"] < dataframe["close"].shift(1))
            & (dataframe["volume"] > 0)
        )

    @staticmethod
    def _squeeze_short(dataframe: DataFrame, atr_floor: float) -> DataFrame:
        squeezed = dataframe["bb_width"].shift(1) < dataframe["bb_width_mean_96"].shift(1) * 0.8
        return (
            (dataframe["atr_pct"] > atr_floor)
            & (dataframe["atr_pct"] < 0.018)
            & (dataframe["volume_z"] > 0.6)
            & squeezed
            & (dataframe["close"] < dataframe["don_low_12"])
            & (dataframe["close"] < dataframe["ema_34"])
            & (dataframe["ema_50_slope"] < 0.002)
            & (dataframe["roc_6"] < -0.0015)
            & (dataframe["rsi"] < 54)
            & (dataframe["rsi"] > 26)
            & (dataframe["volume"] > 0)
        )

    @staticmethod
    def _breakout_short(dataframe: DataFrame, atr_floor: float) -> DataFrame:
        return (
            (dataframe["atr_pct"] > atr_floor)
            & (dataframe["atr_pct"] < 0.030)
            & (dataframe["volume"] > dataframe["volume_mean_48"] * 0.8)
            & dataframe["trend_down"]
            & (dataframe["close"] < dataframe["don_low_34"])
            & (dataframe["rsi"] < 52)
            & (dataframe["rsi"] > 30)
            & (dataframe["volume"] > 0)
        )

    @staticmethod
    def _vwap_reclaim_short(dataframe: DataFrame, atr_floor: float) -> DataFrame:
        crossed_below_vwap = (dataframe["close"] < dataframe["vwap_96"]) & (
            dataframe["close"].shift(1) >= dataframe["vwap_96"].shift(1)
        )
        return (
            (dataframe["atr_pct"] > atr_floor)
            & (dataframe["atr_pct"] < 0.018)
            & (dataframe["volume"] > dataframe["volume_mean_96"])
            & (dataframe["range_pct"] > dataframe["atr_pct"] * 0.8)
            & (dataframe["ema_20"] < dataframe["ema_50"])
            & (dataframe["roc_24"] < 0.045)
            & (dataframe["high"] > dataframe["vwap_96"] * 1.0008)
            & crossed_below_vwap
            & (dataframe["rsi_fast"] < dataframe["rsi_fast"].shift(1))
            & (dataframe["rsi_fast"].shift(1) > 62)
            & (dataframe["volume"] > 0)
        )

    @staticmethod
    def _wick_reversal_short(dataframe: DataFrame) -> DataFrame:
        blowoff = (
            (dataframe["high"] > dataframe["don_high_12"])
            | (dataframe["high"] > dataframe["bb_high"] / 0.998)
        )
        return (
            (dataframe["atr_pct"] > 0.002)
            & (dataframe["atr_pct"] < 0.020)
            & (dataframe["volume"] > dataframe["volume_mean_48"])
            & (dataframe["bb_width"] > 0.006)
            & blowoff
            & (dataframe["upper_wick_pct"] > dataframe["body_pct"] * 1.6)
            & (dataframe["upper_wick_pct"] > dataframe["atr_pct"] * 0.6)
            & (dataframe["close"] < dataframe["open"])
            & (dataframe["rsi_fast"] > 68)
            & (dataframe["roc_12"] < 0.035)
            & (dataframe["volume"] > 0)
        )

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        if pair.startswith("DOGE/"):
            dataframe.loc[
                self._mean_reversion_long(dataframe, 0.0025, 0.022),
                ["enter_long", "enter_tag"],
            ] = (1, "doge_meanrev_long")

        if pair.startswith("ETH/"):
            dataframe.loc[
                self._squeeze_short(dataframe, 0.0025),
                ["enter_short", "enter_tag"],
            ] = (1, "eth_squeeze_short")

        if pair.startswith("ETC/"):
            dataframe.loc[
                self._breakout_short(dataframe, 0.0045),
                ["enter_short", "enter_tag"],
            ] = (1, "etc_breakout_short")

        if pair.startswith("OP/"):
            dataframe.loc[
                self._vwap_reclaim_short(dataframe, 0.0015),
                ["enter_short", "enter_tag"],
            ] = (1, "op_vwap_short")

        if pair.startswith("COMP/"):
            dataframe.loc[
                self._mean_reversion_short(dataframe, 0.0025, 0.012),
                ["enter_short", "enter_tag"],
            ] = (1, "comp_meanrev_short")

        if pair.startswith("TRX/"):
            dataframe.loc[
                self._wick_reversal_short(dataframe),
                ["enter_short", "enter_tag"],
            ] = (1, "trx_wick_short")

        if pair.startswith("LTC/"):
            dataframe.loc[
                self._mean_reversion_short(dataframe, 0.0025, 0.022),
                ["enter_short", "enter_tag"],
            ] = (1, "ltc_meanrev_short")

        if pair.startswith("APT/"):
            dataframe.loc[
                self._vwap_reclaim_short(dataframe, 0.0015),
                ["enter_short", "enter_tag"],
            ] = (1, "apt_vwap_short")

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
        tag = trade.enter_tag or ""
        hold_minutes = self.hold_minutes.get(tag)
        if hold_minutes is None:
            return None

        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        if trade_minutes >= hold_minutes:
            return f"{tag}_fixed_hold_exit"
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


class Intp20Stage3EdgeShortCoreStrategy(Intp20Stage3EdgeStrategy):
    """
    Smoke-test survivor subset from the first native Freqtrade validation.
    """

    hold_minutes = {
        "etc_breakout_short": 24 * 15,
        "trx_wick_short": 24 * 15,
    }

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        if pair.startswith("ETC/"):
            dataframe.loc[
                self._breakout_short(dataframe, 0.0045),
                ["enter_short", "enter_tag"],
            ] = (1, "etc_breakout_short")

        if pair.startswith("TRX/"):
            dataframe.loc[
                self._wick_reversal_short(dataframe),
                ["enter_short", "enter_tag"],
            ] = (1, "trx_wick_short")

        return dataframe
