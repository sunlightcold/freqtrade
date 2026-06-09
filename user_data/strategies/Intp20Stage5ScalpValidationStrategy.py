from datetime import datetime

import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair


class Intp20Stage5LinkPanicLongStrategy(IStrategy):
    """
    Stage-5 native validation for the 1m fast-screener winner.

    Candidate:
    - pair: LINK/USDT:USDT
    - side: long
    - template: panic_snapback
    - regime: BTC market_contra
    - hold: 40 candles on 1m
    """

    INTERFACE_VERSION = 3

    timeframe = "1m"
    startup_candle_count = 300
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

    def informative_pairs(self):
        return [("BTC/USDT:USDT", self.timeframe)]

    @staticmethod
    def _rsi_2(dataframe: DataFrame) -> DataFrame:
        return ta.RSI(dataframe, timeperiod=2)

    @staticmethod
    def _add_common_indicators(dataframe: DataFrame) -> DataFrame:
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_fast"] = ta.RSI(dataframe, timeperiod=4)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["volume_mean_96"] = dataframe["volume"].rolling(96).mean()
        dataframe["volume_z"] = (
            (dataframe["volume"] - dataframe["volume_mean_96"])
            / dataframe["volume"].rolling(96).std()
        )
        dataframe["don_low_12"] = dataframe["low"].rolling(12).min().shift(1)
        dataframe["roc_3"] = dataframe["close"] / dataframe["close"].shift(3) - 1
        dataframe["roc_24"] = dataframe["close"] / dataframe["close"].shift(24) - 1
        dataframe["roc_48"] = dataframe["close"] / dataframe["close"].shift(48) - 1
        dataframe["ema_50_slope"] = dataframe["ema_50"] / dataframe["ema_50"].shift(24) - 1
        dataframe["range_pct"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"]
        dataframe["body_pct"] = (dataframe["close"] - dataframe["open"]).abs() / dataframe["close"]
        dataframe["lower_wick_pct"] = (
            dataframe[["open", "close"]].min(axis=1) - dataframe["low"]
        ) / dataframe["close"]
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_low"] = bollinger["lower"]
        dataframe["bb_mid"] = bollinger["mid"]
        dataframe["bb_high"] = bollinger["upper"]
        dataframe["bb_width"] = (dataframe["bb_high"] - dataframe["bb_low"]) / dataframe["bb_mid"]
        dataframe["bb_width_mean_96"] = dataframe["bb_width"].rolling(96).mean()
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
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self._add_common_indicators(dataframe)

        if self.dp:
            btc = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe=self.timeframe)
            btc = self._add_common_indicators(btc)
            btc = btc[["date", "market_bull"]].rename(columns={"market_bull": "btc_market_bull"})
            dataframe = merge_informative_pair(dataframe, btc, self.timeframe, self.timeframe, ffill=True)

        if "btc_market_bull_1m" not in dataframe:
            dataframe["btc_market_bull_1m"] = False
        return dataframe

    @staticmethod
    def _link_panic_snapback_long(dataframe: DataFrame) -> DataFrame:
        return (
            (dataframe["atr_pct"] > 0.001)
            & (dataframe["atr_pct"] < 0.055)
            & (dataframe["volume_z"] > 0.8)
            & (dataframe["range_pct"] > dataframe["atr_pct"] * 0.85)
            & (dataframe["roc_3"] < -0.007)
            & (dataframe["low"] < dataframe["don_low_12"])
            & (dataframe["lower_wick_pct"] > dataframe["body_pct"] * 1.4)
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["rsi_fast"] < 28)
            & ~dataframe["btc_market_bull_1m"].fillna(False)
            & (dataframe["volume"] > 0)
        )

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"].startswith("LINK/"):
            dataframe.loc[
                self._link_panic_snapback_long(dataframe),
                ["enter_long", "enter_tag"],
            ] = (1, "link_panic_long_1m")
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
        if trade_minutes >= 40:
            return "link_panic_long_1m_fixed_hold_exit"
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


class Intp20Stage5LinkPanicWideStopStrategy(Intp20Stage5LinkPanicLongStrategy):
    """
    Same candidate with a wider stop to test coarse-screener alignment.
    """

    stoploss = -0.80


class Intp20Stage5LinkPanicRiskCutStrategy(Intp20Stage5LinkPanicLongStrategy):
    """
    Same entry with a tighter tail-risk cut.
    """

    stoploss = -0.12
