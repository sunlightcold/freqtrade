from datetime import datetime

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy


class Intp20Stage7AggressivePortfolioStrategy(IStrategy):
    """
    Native validation for the Stage-7 aggressive 5m portfolio.

    Runs on local 1m candles and internally resamples to 5m. This mirrors the
    Stage-7 coarse portfolio that reached the 0.5% daily target only under an
    aggressive 5x / 25% capital-slot assumption.
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
        return (
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

    @staticmethod
    def _add_5m_indicators(dataframe: DataFrame) -> DataFrame:
        dataframe = dataframe.copy()
        dataframe["ema_8"] = ta.EMA(dataframe, timeperiod=8)
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

        typical_price = qtpylib.typical_price(dataframe)
        bollinger = qtpylib.bollinger_bands(typical_price, window=20, stds=2)
        dataframe["bb_low"] = bollinger["lower"]
        dataframe["bb_mid"] = bollinger["mid"]
        dataframe["bb_high"] = bollinger["upper"]
        dataframe["bb_width"] = (dataframe["bb_high"] - dataframe["bb_low"]) / dataframe["bb_mid"]
        dataframe["bb_width_mean_96"] = dataframe["bb_width"].rolling(96).mean()

        dataframe["don_high_12"] = dataframe["high"].rolling(12).max().shift(1)
        dataframe["don_low_12"] = dataframe["low"].rolling(12).min().shift(1)
        dataframe["don_high_24"] = dataframe["high"].rolling(24).max().shift(1)
        dataframe["don_low_24"] = dataframe["low"].rolling(24).min().shift(1)
        for period in (3, 6, 12, 24, 48):
            dataframe[f"roc_{period}"] = dataframe["close"] / dataframe["close"].shift(period) - 1
        dataframe["ema_8_slope"] = dataframe["ema_8"] / dataframe["ema_8"].shift(8) - 1
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
        dataframe["stoch_d"] = dataframe["stoch_k"].rolling(3).mean()
        money_flow = typical_price * dataframe["volume"]
        positive_flow = money_flow.where(typical_price > typical_price.shift(), 0.0)
        negative_flow = money_flow.where(typical_price < typical_price.shift(), 0.0)
        money_ratio = (
            positive_flow.rolling(14).sum()
            / negative_flow.rolling(14).sum().replace(0, np.nan)
        )
        dataframe["mfi"] = 100 - (100 / (1 + money_ratio))
        typical_mean = typical_price.rolling(20).mean()
        typical_dev = (typical_price - typical_mean).abs().rolling(20).mean()
        dataframe["cci"] = (typical_price - typical_mean) / (0.015 * typical_dev)
        dataframe["vwap_24"] = (
            (typical_price * dataframe["volume"]).rolling(24).sum()
            / dataframe["volume"].rolling(24).sum()
        )

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
    def _panic_long(
        dataframe: DataFrame,
        shock: float,
        atr_floor: float,
        atr_ceiling: float,
    ) -> DataFrame:
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
    def _panic_short(
        dataframe: DataFrame,
        shock: float,
        atr_floor: float,
        atr_ceiling: float,
    ) -> DataFrame:
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
    def _range_breakout_short(dataframe: DataFrame, atr_floor: float) -> DataFrame:
        squeezed = dataframe["bb_width"].shift(1) < dataframe["bb_width_mean_96"].shift(1) * 0.80
        return (
            (dataframe["atr_pct"] > atr_floor)
            & (dataframe["atr_pct"] < 0.018)
            & (dataframe["volume_z"] > 0.7)
            & (dataframe["range_pct"] > dataframe["atr_pct"] * 0.65)
            & squeezed
            & (dataframe["close"] < dataframe["don_low_24"])
            & (dataframe["close"] < dataframe["vwap_24"])
            & (dataframe["ema_8_slope"] < -0.0002)
            & (dataframe["roc_3"] < -0.0006)
            & (dataframe["rsi"] < 55)
            & (dataframe["rsi"] > 24)
        )

    @staticmethod
    def _stoch_turn_short(dataframe: DataFrame, atr_floor: float) -> DataFrame:
        crossed_down = (dataframe["stoch_k"] < dataframe["stoch_d"]) & (
            dataframe["stoch_k"].shift(1) >= dataframe["stoch_d"].shift(1)
        )
        return (
            (dataframe["atr_pct"] > atr_floor)
            & (dataframe["atr_pct"] < 0.016)
            & (dataframe["volume"] > dataframe["volume_mean_48"] * 0.7)
            & (dataframe["range_pct"] > dataframe["atr_pct"] * 0.7)
            & (dataframe["local_down"] | dataframe["local_chop"])
            & crossed_down
            & (dataframe["stoch_k"].shift(1) > 76)
            & (dataframe["rsi_fast"] < dataframe["rsi_fast"].shift(1))
            & (dataframe["cci"] > 70)
            & (dataframe["roc_6"] < 0.018)
        )

    @staticmethod
    def _build_pair_signals(dataframe: DataFrame, pair: str) -> DataFrame:
        dataframe = dataframe.copy()
        dataframe["stage7_enter_long"] = False
        dataframe["stage7_enter_short"] = False
        dataframe["stage7_enter_tag"] = None

        btc_bull = dataframe["btc_market_bull"].fillna(False)
        btc_bear = dataframe["btc_market_bear"].fillna(False)
        btc_panic = dataframe["btc_market_panic_down"].fillna(False)
        btc_euphoria = dataframe["btc_market_euphoria_up"].fillna(False)

        if pair.startswith("XRP/"):
            mask = Intp20Stage7AggressivePortfolioStrategy._rsi_reversion_short(dataframe, 0.014)
            mask &= btc_euphoria
            dataframe.loc[mask, ["stage7_enter_short", "stage7_enter_tag"]] = (True, "xrp_rsi_short_h24")

        if pair.startswith("XLM/"):
            mask = Intp20Stage7AggressivePortfolioStrategy._panic_long(dataframe, 0.007, 0.001, 0.030)
            mask &= btc_bear
            dataframe.loc[mask, ["stage7_enter_long", "stage7_enter_tag"]] = (True, "xlm_panic_long_h12")

        if pair.startswith("AAVE/"):
            mask = Intp20Stage7AggressivePortfolioStrategy._panic_long(dataframe, 0.007, 0.001, 0.030)
            mask &= btc_bear
            dataframe.loc[mask, ["stage7_enter_long", "stage7_enter_tag"]] = (True, "aave_panic_long_h24")

        if pair.startswith("XTZ/"):
            mask = Intp20Stage7AggressivePortfolioStrategy._rsi_reversion_short(dataframe, 0.024)
            mask &= dataframe["local_chop"].fillna(False)
            dataframe.loc[mask, ["stage7_enter_short", "stage7_enter_tag"]] = (True, "xtz_rsi_short_h24")

            mask = Intp20Stage7AggressivePortfolioStrategy._panic_long(dataframe, 0.004, 0.001, 0.030)
            mask &= btc_bear
            dataframe.loc[mask, ["stage7_enter_long", "stage7_enter_tag"]] = (True, "xtz_panic_long_h24")

            mask = Intp20Stage7AggressivePortfolioStrategy._rsi_reversion_long(dataframe, 0.014)
            mask &= dataframe["local_chop"].fillna(False)
            dataframe.loc[mask, ["stage7_enter_long", "stage7_enter_tag"]] = (True, "xtz_rsi_long_h24")

        if pair.startswith("SOL/"):
            mask = Intp20Stage7AggressivePortfolioStrategy._panic_short(dataframe, 0.004, 0.002, 0.030)
            mask &= btc_bull
            dataframe.loc[mask, ["stage7_enter_short", "stage7_enter_tag"]] = (True, "sol_panic_short_h24")

        if pair.startswith("SUI/"):
            mask = Intp20Stage7AggressivePortfolioStrategy._rsi_reversion_short(dataframe, 0.014)
            mask &= dataframe["local_chop"].fillna(False)
            dataframe.loc[mask, ["stage7_enter_short", "stage7_enter_tag"]] = (True, "sui_rsi_short_chop_h24")

            mask = Intp20Stage7AggressivePortfolioStrategy._rsi_reversion_short(dataframe, 0.014)
            mask &= btc_bear
            dataframe.loc[mask, ["stage7_enter_short", "stage7_enter_tag"]] = (True, "sui_rsi_short_aligned_h24")

        if pair.startswith("COMP/"):
            mask = Intp20Stage7AggressivePortfolioStrategy._rsi_reversion_long(dataframe, 0.024)
            mask &= btc_panic
            dataframe.loc[mask, ["stage7_enter_long", "stage7_enter_tag"]] = (True, "comp_rsi_long_h24")

        if pair.startswith("MKR/"):
            mask = Intp20Stage7AggressivePortfolioStrategy._range_breakout_short(dataframe, 0.0006)
            mask &= btc_bull
            dataframe.loc[mask, ["stage7_enter_short", "stage7_enter_tag"]] = (True, "mkr_range_short_h24")

            mask = Intp20Stage7AggressivePortfolioStrategy._stoch_turn_short(dataframe, 0.0006)
            mask &= dataframe["local_down"].fillna(False)
            dataframe.loc[mask, ["stage7_enter_short", "stage7_enter_tag"]] = (True, "mkr_stoch_short_h24")

        if pair.startswith("LINK/"):
            mask = Intp20Stage7AggressivePortfolioStrategy._panic_long(dataframe, 0.007, 0.001, 0.030)
            mask &= btc_bear
            dataframe.loc[mask, ["stage7_enter_long", "stage7_enter_tag"]] = (True, "link_panic_long_h24")

        if pair.startswith("LTC/"):
            mask = Intp20Stage7AggressivePortfolioStrategy._stoch_turn_short(dataframe, 0.0012)
            mask &= btc_bull
            dataframe.loc[mask, ["stage7_enter_short", "stage7_enter_tag"]] = (True, "ltc_stoch_short_h24")

        if pair.startswith("TRX/"):
            mask = Intp20Stage7AggressivePortfolioStrategy._range_breakout_short(dataframe, 0.0012)
            mask &= btc_bull
            dataframe.loc[mask, ["stage7_enter_short", "stage7_enter_tag"]] = (True, "trx_range_short_h24")

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
            ["date", "stage7_enter_long", "stage7_enter_short", "stage7_enter_tag"]
        ]
        dataframe = dataframe.merge(signals, on="date", how="left")
        dataframe["stage7_enter_long"] = dataframe["stage7_enter_long"].fillna(False)
        dataframe["stage7_enter_short"] = dataframe["stage7_enter_short"].fillna(False)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        long_mask = dataframe["stage7_enter_long"]
        dataframe.loc[long_mask, "enter_long"] = 1
        dataframe.loc[long_mask, "enter_tag"] = dataframe.loc[long_mask, "stage7_enter_tag"]

        short_mask = dataframe["stage7_enter_short"]
        dataframe.loc[short_mask, "enter_short"] = 1
        dataframe.loc[short_mask, "enter_tag"] = dataframe.loc[short_mask, "stage7_enter_tag"]
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
        hold_minutes = 60 if trade.enter_tag and "h12" in trade.enter_tag else 120
        if trade_minutes >= hold_minutes:
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
        return min(5.0, max_leverage)


class Intp20Stage7AggressiveCoreStrategy(Intp20Stage7AggressivePortfolioStrategy):
    """
    Short-window native-pruned Stage-7 variant.

    The full aggressive portfolio reached the target only in the coarse model.
    Native smoke validation showed several tags were immediate drag sources, so
    this subclass keeps only the tags that were positive in the first native
    validation window before running wider walk-forward checks.
    """

    included_tags = {
        "mkr_range_short_h24",
        "aave_panic_long_h24",
        "xlm_panic_long_h12",
        "sol_panic_short_h24",
        "xtz_rsi_short_h24",
        "trx_range_short_h24",
        "xrp_rsi_short_h24",
        "sui_rsi_short_aligned_h24",
    }

    @staticmethod
    def _build_pair_signals(dataframe: DataFrame, pair: str) -> DataFrame:
        dataframe = Intp20Stage7AggressivePortfolioStrategy._build_pair_signals(dataframe, pair)
        keep = dataframe["stage7_enter_tag"].isin(Intp20Stage7AggressiveCoreStrategy.included_tags)
        dataframe.loc[~keep, ["stage7_enter_long", "stage7_enter_short"]] = False
        dataframe.loc[~keep, "stage7_enter_tag"] = None
        return dataframe
