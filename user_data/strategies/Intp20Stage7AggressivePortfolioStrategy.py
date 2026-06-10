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
        dataframe["vwap_96"] = (
            (typical_price * dataframe["volume"]).rolling(96).sum()
            / dataframe["volume"].rolling(96).sum()
        )
        dataframe["vwap_96_dist"] = dataframe["close"] / dataframe["vwap_96"] - 1
        dataframe["vwap_96_dist_mean"] = dataframe["vwap_96_dist"].rolling(96).mean()
        dataframe["vwap_96_dist_std"] = dataframe["vwap_96_dist"].rolling(96).std()
        dataframe["vwap_96_z"] = (
            (dataframe["vwap_96_dist"] - dataframe["vwap_96_dist_mean"])
            / dataframe["vwap_96_dist_std"]
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
        dataframe["market_high_vol"] = (
            (dataframe["atr_pct"] > dataframe["atr_pct"].rolling(288).mean() * 1.20)
            | (dataframe["bb_width"] > dataframe["bb_width_mean_96"] * 1.25)
        )
        dataframe["market_chop"] = (
            ~dataframe["market_bull"]
            & ~dataframe["market_bear"]
            & (dataframe["bb_width"] < dataframe["bb_width_mean_96"] * 1.15)
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
                "market_high_vol",
                "market_chop",
                "market_panic_down",
                "market_euphoria_up",
            ]
        ].rename(
            columns={
                "market_bull": "btc_market_bull",
                "market_bear": "btc_market_bear",
                "market_high_vol": "btc_market_high_vol",
                "market_chop": "btc_market_chop",
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
                "btc_market_high_vol",
                "btc_market_chop",
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
        hold_minutes = self._hold_minutes_from_tag(trade.enter_tag)
        if trade_minutes >= hold_minutes:
            return f"{trade.enter_tag}_fixed_hold_exit"
        return None

    @staticmethod
    def _hold_minutes_from_tag(enter_tag: str | None) -> int:
        if enter_tag:
            for token in enter_tag.split("_"):
                if token.startswith("h") and token[1:].isdigit():
                    return int(token[1:]) * 5
        return 120

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
        if entry_tag:
            for token in entry_tag.split("_"):
                if token.startswith("l") and token[1:].isdigit():
                    return min(float(token[1:]), max_leverage)
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


class Intp20Stage8NoSuiCoreStrategy(Intp20Stage7AggressiveCoreStrategy):
    """
    Stage-8 first pruning pass.

    `sui_rsi_short_aligned_h24` was the largest native walk-forward drag in
    2024, while its 2025/2026 contribution was not large enough to justify the
    extra tail risk. This keeps the rest of the Stage-7 core unchanged so the
    impact of that single removal is directly comparable.
    """

    included_tags = Intp20Stage7AggressiveCoreStrategy.included_tags - {
        "sui_rsi_short_aligned_h24",
    }

    @staticmethod
    def _build_pair_signals(dataframe: DataFrame, pair: str) -> DataFrame:
        dataframe = Intp20Stage7AggressivePortfolioStrategy._build_pair_signals(dataframe, pair)
        keep = dataframe["stage7_enter_tag"].isin(Intp20Stage8NoSuiCoreStrategy.included_tags)
        dataframe.loc[~keep, ["stage7_enter_long", "stage7_enter_short"]] = False
        dataframe.loc[~keep, "stage7_enter_tag"] = None
        return dataframe


class Intp20Stage8LeaderCoreStrategy(Intp20Stage8NoSuiCoreStrategy):
    """
    Stage-8 conservative leader-only basket.

    Keeps the tags with the clearest native contribution across the validation
    slices. This variant is expected to trade less often, but it tests whether a
    cleaner basket can reduce drawdown enough to support higher exposure.
    """

    included_tags = {
        "mkr_range_short_h24",
        "aave_panic_long_h24",
        "xlm_panic_long_h12",
        "sol_panic_short_h24",
        "xtz_rsi_short_h24",
        "xrp_rsi_short_h24",
    }

    @staticmethod
    def _build_pair_signals(dataframe: DataFrame, pair: str) -> DataFrame:
        dataframe = Intp20Stage7AggressivePortfolioStrategy._build_pair_signals(dataframe, pair)
        keep = dataframe["stage7_enter_tag"].isin(Intp20Stage8LeaderCoreStrategy.included_tags)
        dataframe.loc[~keep, ["stage7_enter_long", "stage7_enter_short"]] = False
        dataframe.loc[~keep, "stage7_enter_tag"] = None
        return dataframe


class Intp20Stage9AggressiveBlendStrategy(Intp20Stage7AggressivePortfolioStrategy):
    """
    Stage-9 aggressive blend translated from the coarse greedy portfolio.

    This class keeps the Stage-7/8 native validation baseline intact and adds
    the higher-frequency micro-momentum and VWAP-reclaim templates found by the
    Stage-9 coarse search. It is intentionally a validation candidate, not an
    assumed production strategy.
    """

    stage9_rules = [
        ("AAVE", "panic_snapback", "long", "market_contra", 24, 4.0, {"atr_ceiling": 0.055, "atr_floor": 0.002, "range_mult": 0.85, "rsi_fast": 28, "shock": 0.007, "volume_z": 0.8, "wick_body": 1.4}),
        ("SOL", "panic_snapback", "short", "market_contra", 24, 4.0, {"atr_ceiling": 0.055, "atr_floor": 0.001, "range_mult": 0.85, "rsi_fast": 28, "shock": 0.004, "volume_z": 0.8, "wick_body": 1.4}),
        ("SUI", "rsi_reversion", "short", "local_chop", 24, 4.0, {"atr_ceiling": 0.014, "atr_floor": 0.0012, "band_pad": 0.998, "bb_width": 0.0035, "macro_limit": 0.045, "mfi_low": 35, "rsi_2_long": 8, "rsi_2_short": 92, "stoch_low": 28, "volume_mult": 0.7}),
        ("XLM", "panic_snapback", "long", "market_contra", 12, 4.0, {"atr_ceiling": 0.055, "atr_floor": 0.001, "range_mult": 0.85, "rsi_fast": 28, "shock": 0.007, "volume_z": 0.8, "wick_body": 1.4}),
        ("COMP", "rsi_reversion", "long", "market_extreme", 24, 4.0, {"atr_ceiling": 0.024, "atr_floor": 0.0006, "band_pad": 0.998, "bb_width": 0.0035, "macro_limit": 0.045, "mfi_low": 35, "rsi_2_long": 8, "rsi_2_short": 92, "stoch_low": 28, "volume_mult": 0.7}),
        ("XTZ", "panic_snapback", "long", "market_contra", 24, 4.0, {"atr_ceiling": 0.055, "atr_floor": 0.001, "range_mult": 0.85, "rsi_fast": 28, "shock": 0.004, "volume_z": 0.8, "wick_body": 1.4}),
        ("MKR", "range_breakout", "short", "market_contra", 24, 4.0, {"atr_ceiling": 0.018, "atr_floor": 0.0006, "range_mult": 0.65, "roc_fast": 0.0006, "rsi_max": 76, "rsi_min": 45, "slope": 0.0002, "squeeze_mult": 0.8, "volume_z": 0.7}),
        ("XTZ", "rsi_reversion", "short", "local_chop", 24, 4.0, {"atr_ceiling": 0.024, "atr_floor": 0.0012, "band_pad": 0.998, "bb_width": 0.0035, "macro_limit": 0.045, "mfi_low": 35, "rsi_2_long": 8, "rsi_2_short": 92, "stoch_low": 28, "volume_mult": 0.7}),
        ("LINK", "panic_snapback", "long", "market_contra", 24, 4.0, {"atr_ceiling": 0.03, "atr_floor": 0.001, "range_mult": 0.85, "rsi_fast": 28, "shock": 0.007, "volume_z": 0.8, "wick_body": 1.4}),
        ("XRP", "rsi_reversion", "short", "market_extreme", 24, 4.0, {"atr_ceiling": 0.024, "atr_floor": 0.0012, "band_pad": 0.998, "bb_width": 0.0035, "macro_limit": 0.045, "mfi_low": 35, "rsi_2_long": 8, "rsi_2_short": 92, "stoch_low": 28, "volume_mult": 0.7}),
        ("MKR", "micro_momentum", "long", "market_chop", 18, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0025, "roc_fast": 0.0015, "roc_slow": 0.002, "rsi_cap": 74, "rsi_fast": 58, "slope": 0.0004, "volume_mult": 1.0, "volume_z": 0.4, "width_mult": 0.9}),
        ("ETC", "micro_momentum", "long", "market_contra", 18, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0015, "roc_fast": 0.0015, "roc_slow": 0.002, "rsi_cap": 74, "rsi_fast": 58, "slope": 0.0004, "volume_mult": 1.0, "volume_z": 0.4, "width_mult": 0.9}),
        ("BCH", "vwap_reclaim", "long", "market_contra", 18, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0025, "macro_pullback": 0.045, "range_mult": 0.8, "rsi_reset": 38, "volume_mult": 1.0, "vwap_pad": 0.0008}),
        ("SUI", "rsi_reversion", "short", "market_aligned", 24, 4.0, {"atr_ceiling": 0.014, "atr_floor": 0.0006, "band_pad": 0.998, "bb_width": 0.0035, "macro_limit": 0.045, "mfi_low": 35, "rsi_2_long": 8, "rsi_2_short": 92, "stoch_low": 28, "volume_mult": 0.7}),
        ("ETH", "micro_momentum", "long", "market_contra", 18, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0015, "roc_fast": 0.0015, "roc_slow": 0.002, "rsi_cap": 74, "rsi_fast": 58, "slope": 0.0004, "volume_mult": 1.0, "volume_z": 0.4, "width_mult": 0.9}),
        ("LTC", "vwap_reclaim", "short", "local_chop", 18, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0015, "macro_pullback": 0.045, "range_mult": 0.8, "rsi_reset": 38, "volume_mult": 1.0, "vwap_pad": 0.0008}),
        ("MKR", "stoch_turn", "short", "local_trend", 24, 4.0, {"atr_ceiling": 0.026, "atr_floor": 0.0006, "cci_low": -70, "range_mult": 0.7, "roc_limit": 0.018, "turn_level": 24, "volume_mult": 0.7}),
        ("AVAX", "micro_momentum", "short", "market_contra", 20, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0025, "roc_fast": 0.0015, "roc_slow": 0.002, "rsi_cap": 74, "rsi_fast": 58, "slope": 0.0004, "volume_mult": 1.0, "volume_z": 0.4, "width_mult": 0.9}),
        ("SOL", "vwap_reclaim", "short", "market_contra", 30, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0025, "macro_pullback": 0.045, "range_mult": 0.8, "rsi_reset": 38, "volume_mult": 1.0, "vwap_pad": 0.0008}),
        ("XTZ", "rsi_reversion", "long", "local_chop", 24, 4.0, {"atr_ceiling": 0.014, "atr_floor": 0.0012, "band_pad": 0.998, "bb_width": 0.0035, "macro_limit": 0.045, "mfi_low": 35, "rsi_2_long": 8, "rsi_2_short": 92, "stoch_low": 28, "volume_mult": 0.7}),
        ("SOL", "vwap_reclaim", "short", "market_high_vol", 18, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0015, "macro_pullback": 0.045, "range_mult": 0.8, "rsi_reset": 38, "volume_mult": 1.0, "vwap_pad": 0.0008}),
        ("OP", "vwap_reclaim", "short", "local_chop", 12, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0025, "macro_pullback": 0.045, "range_mult": 0.8, "rsi_reset": 38, "volume_mult": 1.0, "vwap_pad": 0.0008}),
        ("LTC", "stoch_turn", "short", "market_contra", 24, 4.0, {"atr_ceiling": 0.026, "atr_floor": 0.0012, "cci_low": -70, "range_mult": 0.7, "roc_limit": 0.018, "turn_level": 24, "volume_mult": 0.7}),
        ("MKR", "vwap_reclaim", "short", "market_chop", 12, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0015, "macro_pullback": 0.045, "range_mult": 0.8, "rsi_reset": 38, "volume_mult": 1.0, "vwap_pad": 0.0008}),
        ("SUI", "vwap_reclaim", "long", "local_chop", 18, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0015, "macro_pullback": 0.045, "range_mult": 0.8, "rsi_reset": 38, "volume_mult": 1.0, "vwap_pad": 0.0008}),
        ("BNB", "micro_momentum", "short", "market_chop", 30, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0025, "roc_fast": 0.0015, "roc_slow": 0.002, "rsi_cap": 74, "rsi_fast": 58, "slope": 0.0004, "volume_mult": 1.0, "volume_z": 0.4, "width_mult": 0.9}),
        ("ETC", "vwap_reclaim", "short", "market_chop", 12, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0025, "macro_pullback": 0.045, "range_mult": 0.8, "rsi_reset": 38, "volume_mult": 1.0, "vwap_pad": 0.0008}),
        ("APT", "vwap_reclaim", "long", "market_chop", 30, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0025, "macro_pullback": 0.045, "range_mult": 0.8, "rsi_reset": 38, "volume_mult": 1.0, "vwap_pad": 0.0008}),
        ("LTC", "vwap_reclaim", "short", "market_chop", 18, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0025, "macro_pullback": 0.045, "range_mult": 0.8, "rsi_reset": 38, "volume_mult": 1.0, "vwap_pad": 0.0008}),
        ("TRX", "vwap_reclaim", "short", "market_contra", 12, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0015, "macro_pullback": 0.045, "range_mult": 0.8, "rsi_reset": 38, "volume_mult": 1.0, "vwap_pad": 0.0008}),
    ]

    @staticmethod
    def _micro_momentum(dataframe: DataFrame, side: str, params: dict) -> DataFrame:
        risk_ok = (
            (dataframe["atr_pct"] > params["atr_floor"])
            & (dataframe["atr_pct"] < params["atr_ceiling"])
            & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
            & (dataframe["volume_z"] > params["volume_z"])
            & (dataframe["bb_width"] > dataframe["bb_width_mean_96"] * params["width_mult"])
        )
        if side == "long":
            return (
                risk_ok
                & (dataframe["ema_8"] > dataframe["ema_20"])
                & (dataframe["ema_20"] > dataframe["ema_50"])
                & (dataframe["ema_20_slope"] > params["slope"])
                & (dataframe["close"] > dataframe["don_high_12"])
                & (dataframe["roc_3"] > params["roc_fast"])
                & (dataframe["roc_12"] > params["roc_slow"])
                & (dataframe["rsi_fast"] > params["rsi_fast"])
                & (dataframe["rsi"] < params["rsi_cap"])
            )
        return (
            risk_ok
            & (dataframe["ema_8"] < dataframe["ema_20"])
            & (dataframe["ema_20"] < dataframe["ema_50"])
            & (dataframe["ema_20_slope"] < -params["slope"])
            & (dataframe["close"] < dataframe["don_low_12"])
            & (dataframe["roc_3"] < -params["roc_fast"])
            & (dataframe["roc_12"] < -params["roc_slow"])
            & (dataframe["rsi_fast"] < 100 - params["rsi_fast"])
            & (dataframe["rsi"] > 100 - params["rsi_cap"])
        )

    @staticmethod
    def _vwap_reclaim(dataframe: DataFrame, side: str, params: dict) -> DataFrame:
        crossed_above_vwap = (dataframe["close"] > dataframe["vwap_96"]) & (
            dataframe["close"].shift(1) <= dataframe["vwap_96"].shift(1)
        )
        crossed_below_vwap = (dataframe["close"] < dataframe["vwap_96"]) & (
            dataframe["close"].shift(1) >= dataframe["vwap_96"].shift(1)
        )
        risk_ok = (
            (dataframe["atr_pct"] > params["atr_floor"])
            & (dataframe["atr_pct"] < params["atr_ceiling"])
            & (dataframe["volume"] > dataframe["volume_mean_96"] * params["volume_mult"])
            & (dataframe["range_pct"] > dataframe["atr_pct"] * params["range_mult"])
        )
        if side == "long":
            return (
                risk_ok
                & (dataframe["ema_20"] > dataframe["ema_50"])
                & (dataframe["roc_24"] > -params["macro_pullback"])
                & (dataframe["low"] < dataframe["vwap_96"] * (1 - params["vwap_pad"]))
                & crossed_above_vwap
                & (dataframe["rsi_fast"] > dataframe["rsi_fast"].shift(1))
                & (dataframe["rsi_fast"].shift(1) < params["rsi_reset"])
            )
        return (
            risk_ok
            & (dataframe["ema_20"] < dataframe["ema_50"])
            & (dataframe["roc_24"] < params["macro_pullback"])
            & (dataframe["high"] > dataframe["vwap_96"] * (1 + params["vwap_pad"]))
            & crossed_below_vwap
            & (dataframe["rsi_fast"] < dataframe["rsi_fast"].shift(1))
            & (dataframe["rsi_fast"].shift(1) > 100 - params["rsi_reset"])
        )

    @staticmethod
    def _rsi_reversion(dataframe: DataFrame, side: str, params: dict) -> DataFrame:
        risk_ok = (
            (dataframe["atr_pct"] > params["atr_floor"])
            & (dataframe["atr_pct"] < params["atr_ceiling"])
            & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
            & (dataframe["bb_width"] > params["bb_width"])
        )
        if side == "long":
            return (
                risk_ok
                & (dataframe["low"] < dataframe["bb_low"] * params["band_pad"])
                & (dataframe["rsi_2"] < params["rsi_2_long"])
                & (dataframe["stoch_k"] < params["stoch_low"])
                & (dataframe["mfi"] < params["mfi_low"])
                & (dataframe["roc_12"] > -params["macro_limit"])
                & (dataframe["close"] > dataframe["low"] + (dataframe["high"] - dataframe["low"]) * 0.35)
            )
        return (
            risk_ok
            & (dataframe["high"] > dataframe["bb_high"] / params["band_pad"])
            & (dataframe["rsi_2"] > params["rsi_2_short"])
            & (dataframe["stoch_k"] > 100 - params["stoch_low"])
            & (dataframe["mfi"] > 100 - params["mfi_low"])
            & (dataframe["roc_12"] < params["macro_limit"])
            & (dataframe["close"] < dataframe["high"] - (dataframe["high"] - dataframe["low"]) * 0.35)
        )

    @staticmethod
    def _stoch_turn(dataframe: DataFrame, side: str, params: dict) -> DataFrame:
        crossed_up = (dataframe["stoch_k"] > dataframe["stoch_d"]) & (
            dataframe["stoch_k"].shift(1) <= dataframe["stoch_d"].shift(1)
        )
        crossed_down = (dataframe["stoch_k"] < dataframe["stoch_d"]) & (
            dataframe["stoch_k"].shift(1) >= dataframe["stoch_d"].shift(1)
        )
        risk_ok = (
            (dataframe["atr_pct"] > params["atr_floor"])
            & (dataframe["atr_pct"] < params["atr_ceiling"])
            & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
            & (dataframe["range_pct"] > dataframe["atr_pct"] * params["range_mult"])
        )
        if side == "long":
            return (
                risk_ok
                & (dataframe["local_up"] | dataframe["local_chop"])
                & crossed_up
                & (dataframe["stoch_k"].shift(1) < params["turn_level"])
                & (dataframe["rsi_fast"] > dataframe["rsi_fast"].shift(1))
                & (dataframe["cci"] < params["cci_low"])
                & (dataframe["roc_6"] > -params["roc_limit"])
            )
        return (
            risk_ok
            & (dataframe["local_down"] | dataframe["local_chop"])
            & crossed_down
            & (dataframe["stoch_k"].shift(1) > 100 - params["turn_level"])
            & (dataframe["rsi_fast"] < dataframe["rsi_fast"].shift(1))
            & (dataframe["cci"] > -params["cci_low"])
            & (dataframe["roc_6"] < params["roc_limit"])
        )

    @staticmethod
    def _range_breakout(dataframe: DataFrame, side: str, params: dict) -> DataFrame:
        squeezed = dataframe["bb_width"].shift(1) < dataframe["bb_width_mean_96"].shift(1) * params["squeeze_mult"]
        risk_ok = (
            (dataframe["atr_pct"] > params["atr_floor"])
            & (dataframe["atr_pct"] < params["atr_ceiling"])
            & (dataframe["volume_z"] > params["volume_z"])
            & (dataframe["range_pct"] > dataframe["atr_pct"] * params["range_mult"])
            & squeezed
        )
        if side == "long":
            return (
                risk_ok
                & (dataframe["close"] > dataframe["don_high_24"])
                & (dataframe["close"] > dataframe["vwap_24"])
                & (dataframe["ema_8_slope"] > params["slope"])
                & (dataframe["roc_3"] > params["roc_fast"])
                & (dataframe["rsi"] > params["rsi_min"])
                & (dataframe["rsi"] < params["rsi_max"])
            )
        return (
            risk_ok
            & (dataframe["close"] < dataframe["don_low_24"])
            & (dataframe["close"] < dataframe["vwap_24"])
            & (dataframe["ema_8_slope"] < -params["slope"])
            & (dataframe["roc_3"] < -params["roc_fast"])
            & (dataframe["rsi"] < 100 - params["rsi_min"])
            & (dataframe["rsi"] > 100 - params["rsi_max"])
        )

    @staticmethod
    def _panic_snapback(dataframe: DataFrame, side: str, params: dict) -> DataFrame:
        risk_ok = (
            (dataframe["atr_pct"] > params["atr_floor"])
            & (dataframe["atr_pct"] < params["atr_ceiling"])
            & (dataframe["volume_z"] > params["volume_z"])
            & (dataframe["range_pct"] > dataframe["atr_pct"] * params["range_mult"])
        )
        if side == "long":
            return (
                risk_ok
                & (dataframe["roc_3"] < -params["shock"])
                & (dataframe["low"] < dataframe["don_low_12"])
                & (dataframe["lower_wick_pct"] > dataframe["body_pct"] * params["wick_body"])
                & (dataframe["close"] > dataframe["open"])
                & (dataframe["rsi_fast"] < params["rsi_fast"])
            )
        return (
            risk_ok
            & (dataframe["roc_3"] > params["shock"])
            & (dataframe["high"] > dataframe["don_high_12"])
            & (dataframe["upper_wick_pct"] > dataframe["body_pct"] * params["wick_body"])
            & (dataframe["close"] < dataframe["open"])
            & (dataframe["rsi_fast"] > 100 - params["rsi_fast"])
        )

    @staticmethod
    def _regime_filter(dataframe: DataFrame, regime: str, side: str) -> DataFrame:
        if regime == "local_trend":
            return dataframe["local_up"] if side == "long" else dataframe["local_down"]
        if regime == "local_chop":
            return dataframe["local_chop"]
        if regime == "market_aligned":
            return dataframe["btc_market_bull"] if side == "long" else dataframe["btc_market_bear"]
        if regime == "market_contra":
            return dataframe["btc_market_bear"] if side == "long" else dataframe["btc_market_bull"]
        if regime == "market_chop":
            return dataframe["btc_market_chop"]
        if regime == "market_high_vol":
            return dataframe["btc_market_high_vol"]
        if regime == "market_extreme":
            return dataframe["btc_market_panic_down"] if side == "long" else dataframe["btc_market_euphoria_up"]
        raise ValueError(f"Unsupported Stage-9 regime: {regime}")

    @staticmethod
    def _signal_for_rule(dataframe: DataFrame, template: str, side: str, params: dict) -> DataFrame:
        if template == "micro_momentum":
            return Intp20Stage9AggressiveBlendStrategy._micro_momentum(dataframe, side, params)
        if template == "vwap_reclaim":
            return Intp20Stage9AggressiveBlendStrategy._vwap_reclaim(dataframe, side, params)
        if template == "rsi_reversion":
            return Intp20Stage9AggressiveBlendStrategy._rsi_reversion(dataframe, side, params)
        if template == "stoch_turn":
            return Intp20Stage9AggressiveBlendStrategy._stoch_turn(dataframe, side, params)
        if template == "range_breakout":
            return Intp20Stage9AggressiveBlendStrategy._range_breakout(dataframe, side, params)
        if template == "panic_snapback":
            return Intp20Stage9AggressiveBlendStrategy._panic_snapback(dataframe, side, params)
        raise ValueError(f"Unsupported Stage-9 template: {template}")

    @staticmethod
    def _tag(index: int, base: str, template: str, side: str, regime: str, hold: int, leverage: float) -> str:
        template_alias = {
            "micro_momentum": "micro",
            "vwap_reclaim": "vwap",
            "rsi_reversion": "rsi",
            "stoch_turn": "stoch",
            "range_breakout": "range",
            "panic_snapback": "panic",
        }[template]
        regime_alias = {
            "local_trend": "lt",
            "local_chop": "lc",
            "market_aligned": "ma",
            "market_contra": "mc",
            "market_chop": "mchop",
            "market_high_vol": "mhv",
            "market_extreme": "mx",
        }[regime]
        return f"s9_{index:02d}_{base.lower()}_{template_alias}_{side[0]}_{regime_alias}_h{hold}_l{int(leverage)}"

    @staticmethod
    def _build_pair_signals(dataframe: DataFrame, pair: str) -> DataFrame:
        dataframe = dataframe.copy()
        dataframe["stage7_enter_long"] = False
        dataframe["stage7_enter_short"] = False
        dataframe["stage7_enter_tag"] = None
        base = pair.split("/")[0]

        for index, (rule_base, template, side, regime, hold, leverage, params) in enumerate(
            Intp20Stage9AggressiveBlendStrategy.stage9_rules,
            start=1,
        ):
            if base != rule_base:
                continue
            mask = Intp20Stage9AggressiveBlendStrategy._signal_for_rule(
                dataframe,
                template,
                side,
                params,
            )
            mask &= Intp20Stage9AggressiveBlendStrategy._regime_filter(dataframe, regime, side)
            mask &= dataframe["stage7_enter_tag"].isna()
            tag = Intp20Stage9AggressiveBlendStrategy._tag(index, base, template, side, regime, hold, leverage)
            if side == "long":
                dataframe.loc[mask, ["stage7_enter_long", "stage7_enter_tag"]] = (True, tag)
            else:
                dataframe.loc[mask, ["stage7_enter_short", "stage7_enter_tag"]] = (True, tag)
        return dataframe


class Intp20Stage9PrunedSmokeStrategy(Intp20Stage9AggressiveBlendStrategy):
    """
    Stage-9B smoke-pruned blend.

    Keeps only the Stage-9 rules that were positive in the first native smoke
    window. This is a walk-forward candidate for checking whether the new
    high-frequency streams survive outside the pruning window.
    """

    included_rule_numbers = {
        1,
        2,
        4,
        5,
        7,
        8,
        10,
        11,
        12,
        15,
        16,
        18,
        24,
        25,
        26,
        28,
    }

    @classmethod
    def _build_pair_signals(cls, dataframe: DataFrame, pair: str) -> DataFrame:
        dataframe = dataframe.copy()
        dataframe["stage7_enter_long"] = False
        dataframe["stage7_enter_short"] = False
        dataframe["stage7_enter_tag"] = None
        base = pair.split("/")[0]

        for index, (rule_base, template, side, regime, hold, leverage, params) in enumerate(
            Intp20Stage9AggressiveBlendStrategy.stage9_rules,
            start=1,
        ):
            if index not in cls.included_rule_numbers:
                continue
            if base != rule_base:
                continue
            mask = Intp20Stage9AggressiveBlendStrategy._signal_for_rule(
                dataframe,
                template,
                side,
                params,
            )
            mask &= Intp20Stage9AggressiveBlendStrategy._regime_filter(dataframe, regime, side)
            mask &= dataframe["stage7_enter_tag"].isna()
            tag = Intp20Stage9AggressiveBlendStrategy._tag(index, base, template, side, regime, hold, leverage)
            if side == "long":
                dataframe.loc[mask, ["stage7_enter_long", "stage7_enter_tag"]] = (True, tag)
            else:
                dataframe.loc[mask, ["stage7_enter_short", "stage7_enter_tag"]] = (True, tag)
        return dataframe


class Intp20Stage9CrossYearCoreStrategy(Intp20Stage9PrunedSmokeStrategy):
    """
    Stage-9C cross-year core.

    Removes the Stage-9B rules that flipped sharply between 2024 and 2025/2026.
    The aim is to keep enough high-frequency opportunity count while avoiding
    rules whose apparent edge came from one regime only.
    """

    included_rule_numbers = {
        1,
        2,
        4,
        5,
        7,
        8,
        10,
        11,
        15,
        16,
        24,
        25,
    }


class Intp20Stage10MaOffsetHybridStrategy(Intp20Stage9CrossYearCoreStrategy):
    """
    Stage-10 hybrid candidate.

    Keeps the native-validated Stage-9C 5m core and adds sparse 1m MA-offset
    reversion rules found by the Stage-10 screener. This is a validation
    candidate, not an assumed improvement.
    """

    stage10_rules = [
        ("OP", "long", "market_contra", 12, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0006, "bb_width": 0.0025, "ema20_offset": 0.0035, "ema50_guard": 0.020, "macro_limit": 0.055, "range_mult": 0.60, "rsi_2": 10, "slope_guard": 0.0030, "volume_mult": 0.7}),
        ("ETC", "long", "market_chop", 18, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0012, "bb_width": 0.0025, "ema20_offset": 0.0035, "ema50_guard": 0.020, "macro_limit": 0.055, "range_mult": 0.60, "rsi_2": 10, "slope_guard": 0.0030, "volume_mult": 0.7}),
        ("XRP", "long", "market_aligned", 18, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0012, "bb_width": 0.0025, "ema20_offset": 0.0020, "ema50_guard": 0.020, "macro_limit": 0.055, "range_mult": 0.60, "rsi_2": 14, "slope_guard": 0.0030, "volume_mult": 0.7}),
        ("DOGE", "long", "market_aligned", 12, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0006, "bb_width": 0.0025, "ema20_offset": 0.0035, "ema50_guard": 0.020, "macro_limit": 0.055, "range_mult": 0.60, "rsi_2": 14, "slope_guard": 0.0030, "volume_mult": 0.7}),
        ("LTC", "long", "market_chop", 12, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0006, "bb_width": 0.0025, "ema20_offset": 0.0035, "ema50_guard": 0.020, "macro_limit": 0.055, "range_mult": 0.60, "rsi_2": 10, "slope_guard": 0.0030, "volume_mult": 0.7}),
        ("XLM", "long", "market_aligned", 12, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0012, "bb_width": 0.0025, "ema20_offset": 0.0020, "ema50_guard": 0.020, "macro_limit": 0.055, "range_mult": 0.60, "rsi_2": 10, "slope_guard": 0.0030, "volume_mult": 0.7}),
        ("LTC", "long", "market_contra", 3, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0012, "bb_width": 0.0025, "ema20_offset": 0.0035, "ema50_guard": 0.020, "macro_limit": 0.055, "range_mult": 0.60, "rsi_2": 10, "slope_guard": 0.0030, "volume_mult": 0.7}),
        ("XTZ", "short", "market_contra", 12, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0012, "bb_width": 0.0025, "ema20_offset": 0.0020, "ema50_guard": 0.020, "macro_limit": 0.055, "range_mult": 0.60, "rsi_2": 14, "slope_guard": 0.0030, "volume_mult": 0.7}),
        ("XRP", "long", "market_aligned", 12, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0006, "bb_width": 0.0025, "ema20_offset": 0.0020, "ema50_guard": 0.020, "macro_limit": 0.055, "range_mult": 0.60, "rsi_2": 10, "slope_guard": 0.0030, "volume_mult": 0.7}),
    ]

    @staticmethod
    def _ma_offset_reversion(dataframe: DataFrame, side: str, params: dict) -> DataFrame:
        risk_ok = (
            (dataframe["atr_pct"] > params["atr_floor"])
            & (dataframe["atr_pct"] < params["atr_ceiling"])
            & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
            & (dataframe["bb_width"] > params["bb_width"])
            & (dataframe["range_pct"] > dataframe["atr_pct"] * params["range_mult"])
        )
        if side == "long":
            return (
                risk_ok
                & (dataframe["close"] < dataframe["ema_20"] * (1 - params["ema20_offset"]))
                & (dataframe["close"] > dataframe["ema_50"] * (1 - params["ema50_guard"]))
                & (dataframe["ema_50_slope"] > -params["slope_guard"])
                & (dataframe["rsi_2"] < params["rsi_2"])
                & (dataframe["rsi_fast"] > dataframe["rsi_fast"].shift(1))
                & (dataframe["close"] > dataframe["open"])
                & (dataframe["roc_12"] > -params["macro_limit"])
            )
        return (
            risk_ok
            & (dataframe["close"] > dataframe["ema_20"] * (1 + params["ema20_offset"]))
            & (dataframe["close"] < dataframe["ema_50"] * (1 + params["ema50_guard"]))
            & (dataframe["ema_50_slope"] < params["slope_guard"])
            & (dataframe["rsi_2"] > 100 - params["rsi_2"])
            & (dataframe["rsi_fast"] < dataframe["rsi_fast"].shift(1))
            & (dataframe["close"] < dataframe["open"])
            & (dataframe["roc_12"] < params["macro_limit"])
        )

    @staticmethod
    def _stage10_tag(index: int, base: str, side: str, regime: str, hold: int, leverage: float) -> str:
        regime_alias = {
            "market_aligned": "ma",
            "market_contra": "mc",
            "market_chop": "mchop",
        }[regime]
        return f"s10_{index:02d}_{base.lower()}_maoff_{side[0]}_{regime_alias}_h{hold}m_l{int(leverage)}"

    @classmethod
    def _build_stage10_signals(cls, dataframe: DataFrame, pair: str) -> DataFrame:
        dataframe = dataframe.copy()
        dataframe["stage10_enter_long"] = False
        dataframe["stage10_enter_short"] = False
        dataframe["stage10_enter_tag"] = None
        base = pair.split("/")[0]

        for index, (rule_base, side, regime, hold, leverage, params) in enumerate(
            cls.stage10_rules,
            start=1,
        ):
            if base != rule_base:
                continue
            mask = cls._ma_offset_reversion(dataframe, side, params)
            mask &= Intp20Stage9AggressiveBlendStrategy._regime_filter(dataframe, regime, side)
            mask &= dataframe["stage10_enter_tag"].isna()
            tag = cls._stage10_tag(index, base, side, regime, hold, leverage)
            if side == "long":
                dataframe.loc[mask, ["stage10_enter_long", "stage10_enter_tag"]] = (True, tag)
            else:
                dataframe.loc[mask, ["stage10_enter_short", "stage10_enter_tag"]] = (True, tag)
        return dataframe

    def _btc_1m_regime(self) -> DataFrame:
        if not self.dp:
            return DataFrame()
        btc = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe=self.timeframe)
        btc_1m = self._add_5m_indicators(btc)
        return btc_1m[
            [
                "date",
                "market_bull",
                "market_bear",
                "market_high_vol",
                "market_chop",
                "market_panic_down",
                "market_euphoria_up",
            ]
        ].rename(
            columns={
                "market_bull": "btc_market_bull",
                "market_bear": "btc_market_bear",
                "market_high_vol": "btc_market_high_vol",
                "market_chop": "btc_market_chop",
                "market_panic_down": "btc_market_panic_down",
                "market_euphoria_up": "btc_market_euphoria_up",
            }
        )

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        pair = metadata["pair"]
        pair_1m = self._add_5m_indicators(dataframe)
        btc_1m = self._btc_1m_regime()
        if not btc_1m.empty:
            pair_1m = pair_1m.merge(btc_1m, on="date", how="left")
            btc_columns = [column for column in pair_1m.columns if column.startswith("btc_")]
            pair_1m[btc_columns] = pair_1m[btc_columns].ffill().fillna(False)
        else:
            for column in (
                "btc_market_bull",
                "btc_market_bear",
                "btc_market_high_vol",
                "btc_market_chop",
                "btc_market_panic_down",
                "btc_market_euphoria_up",
            ):
                pair_1m[column] = False

        signals = self._build_stage10_signals(pair_1m, pair)[
            ["date", "stage10_enter_long", "stage10_enter_short", "stage10_enter_tag"]
        ]
        dataframe = dataframe.merge(signals, on="date", how="left")
        dataframe["stage10_enter_long"] = dataframe["stage10_enter_long"].fillna(False)
        dataframe["stage10_enter_short"] = dataframe["stage10_enter_short"].fillna(False)

        free_slot = ~dataframe["stage7_enter_long"] & ~dataframe["stage7_enter_short"]
        long_mask = free_slot & dataframe["stage10_enter_long"]
        dataframe.loc[long_mask, "stage7_enter_long"] = True
        dataframe.loc[long_mask, "stage7_enter_tag"] = dataframe.loc[
            long_mask,
            "stage10_enter_tag",
        ]
        short_mask = free_slot & dataframe["stage10_enter_short"]
        dataframe.loc[short_mask, "stage7_enter_short"] = True
        dataframe.loc[short_mask, "stage7_enter_tag"] = dataframe.loc[
            short_mask,
            "stage10_enter_tag",
        ]
        return dataframe

    @staticmethod
    def _hold_minutes_from_tag(enter_tag: str | None) -> int:
        if enter_tag:
            for token in enter_tag.split("_"):
                if token.startswith("h") and token.endswith("m") and token[1:-1].isdigit():
                    return int(token[1:-1])
                if token.startswith("h") and token[1:].isdigit():
                    return int(token[1:]) * 5
        return 120


class Intp20Stage10MaOffsetTop3Strategy(Intp20Stage10MaOffsetHybridStrategy):
    """
    Conservative Stage-10 variant with only the three strongest MA-offset rules.
    """

    stage10_rules = Intp20Stage10MaOffsetHybridStrategy.stage10_rules[:3]


class Intp20Stage11VwapStretchHybridStrategy(Intp20Stage10MaOffsetHybridStrategy):
    """
    Stage-11 validation candidate.

    Keeps the native Stage-10 hybrid intact and adds sparse 1m VWAP-stretch
    reversion rules that improved the coarse Stage-10/11 greedy portfolio.
    """

    stage11_rules = [
        ("APT", "long", "market_aligned", 12, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0006, "bb_width": 0.0025, "close_pos": 0.35, "macro_limit": 0.055, "min_dist": 0.0035, "rsi_2": 10, "volume_mult": 0.7, "z_entry": 1.8}),
        ("SOL", "long", "market_chop", 12, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0012, "bb_width": 0.0025, "close_pos": 0.35, "macro_limit": 0.055, "min_dist": 0.0035, "rsi_2": 10, "volume_mult": 0.7, "z_entry": 1.8}),
        ("ETC", "long", "market_chop", 12, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0006, "bb_width": 0.0025, "close_pos": 0.35, "macro_limit": 0.055, "min_dist": 0.0020, "rsi_2": 10, "volume_mult": 0.7, "z_entry": 2.4}),
        ("DOGE", "short", "market_chop", 12, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0012, "bb_width": 0.0025, "close_pos": 0.35, "macro_limit": 0.055, "min_dist": 0.0020, "rsi_2": 10, "volume_mult": 0.7, "z_entry": 2.4}),
        ("XTZ", "long", "market_chop", 8, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0006, "bb_width": 0.0025, "close_pos": 0.35, "macro_limit": 0.055, "min_dist": 0.0035, "rsi_2": 10, "volume_mult": 0.7, "z_entry": 1.8}),
        ("APT", "long", "market_chop", 12, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0006, "bb_width": 0.0025, "close_pos": 0.35, "macro_limit": 0.055, "min_dist": 0.0035, "rsi_2": 10, "volume_mult": 0.7, "z_entry": 2.4}),
        ("APT", "long", "market_aligned", 12, 5.0, {"atr_ceiling": 0.018, "atr_floor": 0.0006, "bb_width": 0.0025, "close_pos": 0.35, "macro_limit": 0.055, "min_dist": 0.0035, "rsi_2": 14, "volume_mult": 0.7, "z_entry": 2.4}),
    ]

    @staticmethod
    def _vwap_stretch_reversion(dataframe: DataFrame, side: str, params: dict) -> DataFrame:
        risk_ok = (
            (dataframe["atr_pct"] > params["atr_floor"])
            & (dataframe["atr_pct"] < params["atr_ceiling"])
            & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
            & (dataframe["bb_width"] > params["bb_width"])
            & (dataframe["vwap_96_dist"].abs() > params["min_dist"])
        )
        if side == "long":
            return (
                risk_ok
                & (dataframe["vwap_96_z"] < -params["z_entry"])
                & (dataframe["close"] < dataframe["vwap_96"] * (1 - params["min_dist"]))
                & (dataframe["rsi_2"] < params["rsi_2"])
                & (dataframe["rsi_fast"] > dataframe["rsi_fast"].shift(1))
                & (dataframe["close"] > dataframe["low"] + (dataframe["high"] - dataframe["low"]) * params["close_pos"])
                & (dataframe["roc_24"] > -params["macro_limit"])
            )
        return (
            risk_ok
            & (dataframe["vwap_96_z"] > params["z_entry"])
            & (dataframe["close"] > dataframe["vwap_96"] * (1 + params["min_dist"]))
            & (dataframe["rsi_2"] > 100 - params["rsi_2"])
            & (dataframe["rsi_fast"] < dataframe["rsi_fast"].shift(1))
            & (dataframe["close"] < dataframe["high"] - (dataframe["high"] - dataframe["low"]) * params["close_pos"])
            & (dataframe["roc_24"] < params["macro_limit"])
        )

    @staticmethod
    def _stage11_tag(index: int, base: str, side: str, regime: str, hold: int, leverage: float) -> str:
        regime_alias = {
            "market_aligned": "ma",
            "market_chop": "mchop",
        }[regime]
        return f"s11_{index:02d}_{base.lower()}_vstretch_{side[0]}_{regime_alias}_h{hold}m_l{int(leverage)}"

    @classmethod
    def _build_stage10_signals(cls, dataframe: DataFrame, pair: str) -> DataFrame:
        dataframe = super()._build_stage10_signals(dataframe, pair)
        base = pair.split("/")[0]

        for index, (rule_base, side, regime, hold, leverage, params) in enumerate(
            cls.stage11_rules,
            start=1,
        ):
            if base != rule_base:
                continue
            mask = cls._vwap_stretch_reversion(dataframe, side, params)
            mask &= Intp20Stage9AggressiveBlendStrategy._regime_filter(dataframe, regime, side)
            mask &= dataframe["stage10_enter_tag"].isna()
            tag = cls._stage11_tag(index, base, side, regime, hold, leverage)
            if side == "long":
                dataframe.loc[mask, ["stage10_enter_long", "stage10_enter_tag"]] = (True, tag)
            else:
                dataframe.loc[mask, ["stage10_enter_short", "stage10_enter_tag"]] = (True, tag)
        return dataframe


class Intp20Stage11BPrunedVwapStretchStrategy(Intp20Stage11VwapStretchHybridStrategy):
    """
    Stage-11B pruning pass.

    Removes Stage-10/11 add-on rules that were clear cross-year drag sources in
    native validation while leaving the Stage-9C core untouched.
    """

    stage10_rules = [
        rule
        for rule in Intp20Stage10MaOffsetHybridStrategy.stage10_rules
        if not (rule[0] == "XTZ" and rule[1] == "short" and rule[2] == "market_contra")
    ]
    stage11_rules = [
        rule
        for rule in Intp20Stage11VwapStretchHybridStrategy.stage11_rules
        if not (
            (rule[0] == "XTZ" and rule[1] == "long" and rule[2] == "market_chop")
            or (rule[0] == "DOGE" and rule[1] == "short" and rule[2] == "market_chop")
        )
    ]


class Intp20Stage11CNoXtzMaoffStrategy(Intp20Stage11VwapStretchHybridStrategy):
    """
    Stage-11C pruning pass.

    Removes only the Stage-10 XTZ short MA-offset add-on while keeping all
    Stage-11 VWAP-stretch rules for a narrower risk-control comparison.
    """

    stage10_rules = [
        rule
        for rule in Intp20Stage10MaOffsetHybridStrategy.stage10_rules
        if not (rule[0] == "XTZ" and rule[1] == "short" and rule[2] == "market_contra")
    ]


class Intp20Stage12NoXtzVstretchStrategy(Intp20Stage11CNoXtzMaoffStrategy):
    """
    Stage-12 risk-pruning candidate.

    Keeps the Stage-11C portfolio but removes the XTZ long VWAP-stretch add-on,
    which was the weakest cross-window Stage-11 rule in native validation.
    """

    stage11_rules = [
        rule
        for rule in Intp20Stage11VwapStretchHybridStrategy.stage11_rules
        if not (rule[0] == "XTZ" and rule[1] == "long" and rule[2] == "market_chop")
    ]


class Intp20Stage12NoDogeVstretchStrategy(Intp20Stage11CNoXtzMaoffStrategy):
    """
    Stage-12 risk-pruning candidate.

    Keeps the Stage-11C portfolio but removes the DOGE short VWAP-stretch add-on,
    which had negative aggregate contribution across the validated windows.
    """

    stage11_rules = [
        rule
        for rule in Intp20Stage11VwapStretchHybridStrategy.stage11_rules
        if not (rule[0] == "DOGE" and rule[1] == "short" and rule[2] == "market_chop")
    ]


class Intp20Stage12PrunedVstretchStrategy(Intp20Stage11CNoXtzMaoffStrategy):
    """
    Stage-12 risk-pruning candidate.

    Removes both weak Stage-11 VWAP-stretch add-ons while keeping the Stage-9C
    core and Stage-10 MA-offset stream unchanged.
    """

    stage11_rules = [
        rule
        for rule in Intp20Stage11VwapStretchHybridStrategy.stage11_rules
        if not (
            (rule[0] == "XTZ" and rule[1] == "long" and rule[2] == "market_chop")
            or (rule[0] == "DOGE" and rule[1] == "short" and rule[2] == "market_chop")
        )
    ]


class Intp20Stage12NoXtzCoreShortStrategy(Intp20Stage11CNoXtzMaoffStrategy):
    """
    Stage-12 drawdown-cluster candidate.

    Removes the Stage-9 XTZ local-chop RSI short rule, which was the dominant
    2026 drawdown contributor and a recurring large-loss source.
    """

    included_rule_numbers = Intp20Stage9CrossYearCoreStrategy.included_rule_numbers - {8}


class Intp20Stage12XtzCoreRocFilterStrategy(Intp20Stage11CNoXtzMaoffStrategy):
    """
    Stage-12 dynamic XTZ short filter.

    Keeps the XTZ local-chop RSI short rule, but blocks it when both XTZ and BTC
    have non-negative 5m 48-bar momentum. That regime produced most of the
    2026 XTZ short damage while preserving the rule's 2024/2025 down-regime use.
    """

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
                "market_high_vol",
                "market_chop",
                "market_panic_down",
                "market_euphoria_up",
                "roc_48",
            ]
        ].rename(
            columns={
                "market_bull": "btc_market_bull",
                "market_bear": "btc_market_bear",
                "market_high_vol": "btc_market_high_vol",
                "market_chop": "btc_market_chop",
                "market_panic_down": "btc_market_panic_down",
                "market_euphoria_up": "btc_market_euphoria_up",
                "roc_48": "btc_roc_48",
            }
        )

    @classmethod
    def _build_pair_signals(cls, dataframe: DataFrame, pair: str) -> DataFrame:
        dataframe = dataframe.copy()
        dataframe["stage7_enter_long"] = False
        dataframe["stage7_enter_short"] = False
        dataframe["stage7_enter_tag"] = None
        base = pair.split("/")[0]

        for index, (rule_base, template, side, regime, hold, leverage, params) in enumerate(
            Intp20Stage9AggressiveBlendStrategy.stage9_rules,
            start=1,
        ):
            if index not in cls.included_rule_numbers:
                continue
            if base != rule_base:
                continue
            mask = Intp20Stage9AggressiveBlendStrategy._signal_for_rule(
                dataframe,
                template,
                side,
                params,
            )
            mask &= Intp20Stage9AggressiveBlendStrategy._regime_filter(dataframe, regime, side)
            if index == 8 and base == "XTZ" and "btc_roc_48" in dataframe.columns:
                mask &= ~((dataframe["roc_48"] >= 0) & (dataframe["btc_roc_48"] >= 0))
            mask &= dataframe["stage7_enter_tag"].isna()
            tag = Intp20Stage9AggressiveBlendStrategy._tag(index, base, template, side, regime, hold, leverage)
            if side == "long":
                dataframe.loc[mask, ["stage7_enter_long", "stage7_enter_tag"]] = (True, tag)
            else:
                dataframe.loc[mask, ["stage7_enter_short", "stage7_enter_tag"]] = (True, tag)
        return dataframe


class Intp20Stage13LiquidExpansionStrategy(Intp20Stage12XtzCoreRocFilterStrategy):
    """
    Stage-13 native validation candidate.

    Adds liquid-expansion template candidates to the Stage-12 core. These pairs
    were selected from the expanded 1m futures scan only after passing the main
    template windows; this class exists to test them under native Freqtrade
    portfolio constraints before any pair is promoted to dry-run.
    """

    stage13_rules = [
        ("NEAR", "rsi_reversion", "short", "local_chop", 24, 4.0, {"atr_ceiling": 0.024, "atr_floor": 0.0006, "band_pad": 0.998, "bb_width": 0.0035, "macro_limit": 0.045, "mfi_low": 35, "rsi_2_long": 8, "rsi_2_short": 92, "stoch_low": 28, "volume_mult": 0.7}),
        ("DOT", "rsi_reversion", "short", "local_chop", 24, 4.0, {"atr_ceiling": 0.024, "atr_floor": 0.0006, "band_pad": 0.998, "bb_width": 0.0035, "macro_limit": 0.045, "mfi_low": 35, "rsi_2_long": 8, "rsi_2_short": 92, "stoch_low": 28, "volume_mult": 0.7}),
        ("ICP", "rsi_reversion", "short", "local_chop", 24, 4.0, {"atr_ceiling": 0.024, "atr_floor": 0.0006, "band_pad": 0.998, "bb_width": 0.0035, "macro_limit": 0.045, "mfi_low": 35, "rsi_2_long": 8, "rsi_2_short": 92, "stoch_low": 28, "volume_mult": 0.7}),
        ("ADA", "micro_momentum", "short", "market_chop", 18, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0015, "roc_fast": 0.0015, "roc_slow": 0.002, "rsi_cap": 74, "rsi_fast": 58, "slope": 0.0004, "volume_mult": 1.0, "volume_z": 0.4, "width_mult": 0.9}),
        ("FET", "rsi_reversion", "long", "local_chop", 24, 4.0, {"atr_ceiling": 0.024, "atr_floor": 0.0006, "band_pad": 0.998, "bb_width": 0.0035, "macro_limit": 0.045, "mfi_low": 35, "rsi_2_long": 8, "rsi_2_short": 92, "stoch_low": 28, "volume_mult": 0.7}),
        ("RUNE", "micro_momentum", "short", "market_chop", 18, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0015, "roc_fast": 0.0015, "roc_slow": 0.002, "rsi_cap": 74, "rsi_fast": 58, "slope": 0.0004, "volume_mult": 1.0, "volume_z": 0.4, "width_mult": 0.9}),
        ("UNI", "rsi_reversion", "short", "local_chop", 24, 4.0, {"atr_ceiling": 0.024, "atr_floor": 0.0006, "band_pad": 0.998, "bb_width": 0.0035, "macro_limit": 0.045, "mfi_low": 35, "rsi_2_long": 8, "rsi_2_short": 92, "stoch_low": 28, "volume_mult": 0.7}),
        ("1000SHIB", "micro_momentum", "long", "market_chop", 18, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0015, "roc_fast": 0.0015, "roc_slow": 0.002, "rsi_cap": 74, "rsi_fast": 58, "slope": 0.0004, "volume_mult": 1.0, "volume_z": 0.4, "width_mult": 0.9}),
        ("1000PEPE", "panic_snapback", "long", "market_contra", 12, 4.0, {"atr_ceiling": 0.055, "atr_floor": 0.001, "range_mult": 0.85, "rsi_fast": 28, "shock": 0.004, "volume_z": 0.8, "wick_body": 1.4}),
        ("ARB", "rsi_reversion", "long", "local_chop", 24, 4.0, {"atr_ceiling": 0.024, "atr_floor": 0.0006, "band_pad": 0.998, "bb_width": 0.0035, "macro_limit": 0.045, "mfi_low": 35, "rsi_2_long": 8, "rsi_2_short": 92, "stoch_low": 28, "volume_mult": 0.7}),
        ("FIL", "panic_snapback", "long", "market_contra", 12, 4.0, {"atr_ceiling": 0.055, "atr_floor": 0.001, "range_mult": 0.85, "rsi_fast": 28, "shock": 0.004, "volume_z": 0.8, "wick_body": 1.4}),
        ("SAND", "panic_snapback", "long", "market_contra", 12, 4.0, {"atr_ceiling": 0.055, "atr_floor": 0.001, "range_mult": 0.85, "rsi_fast": 28, "shock": 0.004, "volume_z": 0.8, "wick_body": 1.4}),
        ("MANA", "stoch_turn", "short", "local_trend", 24, 4.0, {"atr_ceiling": 0.030, "atr_floor": 0.0006, "cci_low": -70, "range_mult": 0.7, "roc_limit": 0.018, "turn_level": 24, "volume_mult": 0.7}),
    ]

    @staticmethod
    def _stage13_tag(index: int, base: str, template: str, side: str, regime: str, hold: int, leverage: float) -> str:
        template_alias = {
            "micro_momentum": "micro",
            "panic_snapback": "panic",
            "rsi_reversion": "rsi",
            "stoch_turn": "stoch",
        }[template]
        regime_alias = {
            "local_chop": "lc",
            "local_trend": "lt",
            "market_chop": "mchop",
            "market_contra": "mc",
        }[regime]
        return f"s13_{index:02d}_{base.lower()}_{template_alias}_{side[0]}_{regime_alias}_h{hold}_l{int(leverage)}"

    @classmethod
    def _build_pair_signals(cls, dataframe: DataFrame, pair: str) -> DataFrame:
        dataframe = super()._build_pair_signals(dataframe, pair)
        base = pair.split("/")[0]

        for index, (rule_base, template, side, regime, hold, leverage, params) in enumerate(
            cls.stage13_rules,
            start=1,
        ):
            if base != rule_base:
                continue
            mask = Intp20Stage9AggressiveBlendStrategy._signal_for_rule(
                dataframe,
                template,
                side,
                params,
            )
            mask &= Intp20Stage9AggressiveBlendStrategy._regime_filter(dataframe, regime, side)
            mask &= dataframe["stage7_enter_tag"].isna()
            tag = cls._stage13_tag(index, base, template, side, regime, hold, leverage)
            if side == "long":
                dataframe.loc[mask, ["stage7_enter_long", "stage7_enter_tag"]] = (True, tag)
            else:
                dataframe.loc[mask, ["stage7_enter_short", "stage7_enter_tag"]] = (True, tag)
        return dataframe


class Intp20Stage13Validated20Strategy(Intp20Stage13LiquidExpansionStrategy):
    """
    Stage-13 dry-run candidate with the validated 20-pair universe.

    Keeps only the six expansion rules that survived native Freqtrade
    pair-level validation well enough to promote alongside the Stage-12 base
    universe. Excluded candidate rules stay in the broader research class.
    """

    stage13_rules = [
        rule
        for rule in Intp20Stage13LiquidExpansionStrategy.stage13_rules
        if rule[0] in {"DOT", "ICP", "NEAR", "FET", "UNI", "MANA"}
    ]
