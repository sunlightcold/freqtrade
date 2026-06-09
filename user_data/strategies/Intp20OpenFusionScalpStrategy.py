from datetime import datetime

import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair


class Intp20OpenFusionScalpStrategy(IStrategy):
    """
    1m futures research strategy inspired by common open-source Freqtrade patterns.

    The model combines EMA trend filters, Bollinger pullbacks, Donchian breakouts,
    RSI/ADX confirmation, and small bounded DCA. It is intentionally more active
    than the previous 15m DCA profiles.
    """

    INTERFACE_VERSION = 3

    timeframe = "1m"
    startup_candle_count = 2400
    can_short = True

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    position_adjustment_enable = True
    max_entry_position_adjustment = 1
    max_dca_multiplier = 1.35

    trade_long = True
    trade_short = True
    enable_pullback_entry = True
    enable_breakout_entry = True
    enable_reclaim_entry = True

    minimal_roi = {
        "90": 0.0015,
        "30": 0.0028,
        "8": 0.0055,
        "0": 0.0100,
    }

    stoploss = -0.045
    trailing_stop = True
    trailing_stop_positive = 0.0025
    trailing_stop_positive_offset = 0.0085
    trailing_only_offset_is_reached = True

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

    pair_stake_weights = {
        "AVAX/": 1.18,
        "SOL/": 1.14,
        "DOGE/": 1.10,
        "APT/": 1.08,
        "XRP/": 1.06,
        "BCH/": 1.05,
        "LTC/": 1.04,
        "XLM/": 1.02,
        "BTC/": 0.96,
        "ETH/": 0.92,
        "BNB/": 0.72,
        "AAVE/": 0.70,
    }

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 4,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 720,
                "trade_limit": 6,
                "stop_duration_candles": 180,
                "only_per_side": True,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 2880,
                "trade_limit": 80,
                "stop_duration_candles": 360,
                "max_allowed_drawdown": 0.20,
            },
        ]

    plot_config = {
        "main_plot": {
            "ema_8": {"color": "yellow"},
            "ema_21": {"color": "orange"},
            "ema_55": {"color": "blue"},
            "bb_lowerband": {"color": "grey"},
            "bb_upperband": {"color": "grey"},
            "donchian_high": {"color": "green"},
            "donchian_low": {"color": "red"},
        },
        "subplots": {
            "Momentum": {
                "rsi": {"color": "purple"},
                "adx": {"color": "green"},
            },
            "Regime": {
                "trend_score_15m": {"color": "blue"},
                "regime_score_1h": {"color": "black"},
            },
        },
    }

    def informative_pairs(self):
        if not self.dp:
            return []
        pairs = self.dp.current_whitelist()
        return [(pair, "15m") for pair in pairs] + [(pair, "1h") for pair in pairs]

    @staticmethod
    def _add_main_indicators(dataframe: DataFrame) -> DataFrame:
        dataframe["ema_8"] = ta.EMA(dataframe, timeperiod=8)
        dataframe["ema_21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema_55"] = ta.EMA(dataframe, timeperiod=55)
        dataframe["ema_144"] = ta.EMA(dataframe, timeperiod=144)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_fast"] = ta.RSI(dataframe, timeperiod=5)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["volume_mean_30"] = dataframe["volume"].rolling(30).mean()
        dataframe["volume_mean_120"] = dataframe["volume"].rolling(120).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_mean_30"]
        dataframe["roc_3"] = dataframe["close"] / dataframe["close"].shift(3) - 1
        dataframe["roc_10"] = dataframe["close"] / dataframe["close"].shift(10) - 1
        dataframe["ema_8_slope"] = dataframe["ema_8"] / dataframe["ema_8"].shift(8) - 1
        dataframe["ema_21_slope"] = dataframe["ema_21"] / dataframe["ema_21"].shift(21) - 1

        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]
        dataframe["bb_width"] = (
            (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe["bb_middleband"]
        )

        dataframe["donchian_high"] = dataframe["high"].rolling(34).max().shift(1)
        dataframe["donchian_low"] = dataframe["low"].rolling(34).min().shift(1)
        dataframe["micro_range"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"]
        dataframe["body_pct"] = (dataframe["close"] - dataframe["open"]).abs() / dataframe["close"]
        return dataframe

    @staticmethod
    def _add_15m_indicators(dataframe: DataFrame) -> DataFrame:
        dataframe["ema_21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema_55"] = ta.EMA(dataframe, timeperiod=55)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["volume_mean_48"] = dataframe["volume"].rolling(48).mean()
        dataframe["roc_4"] = dataframe["close"] / dataframe["close"].shift(4) - 1
        dataframe["roc_16"] = dataframe["close"] / dataframe["close"].shift(16) - 1
        dataframe["roc_48"] = dataframe["close"] / dataframe["close"].shift(48) - 1
        dataframe["ema_55_slope"] = dataframe["ema_55"] / dataframe["ema_55"].shift(16) - 1

        dataframe["trend_score"] = 0
        dataframe.loc[dataframe["close"] > dataframe["ema_21"], "trend_score"] += 1
        dataframe.loc[dataframe["ema_21"] > dataframe["ema_55"], "trend_score"] += 1
        dataframe.loc[dataframe["ema_55"] > dataframe["ema_200"], "trend_score"] += 1
        dataframe.loc[dataframe["ema_55_slope"] > 0, "trend_score"] += 1
        dataframe.loc[dataframe["plus_di"] > dataframe["minus_di"], "trend_score"] += 1
        dataframe.loc[dataframe["close"] < dataframe["ema_21"], "trend_score"] -= 1
        dataframe.loc[dataframe["ema_21"] < dataframe["ema_55"], "trend_score"] -= 1
        dataframe.loc[dataframe["ema_55"] < dataframe["ema_200"], "trend_score"] -= 1
        dataframe.loc[dataframe["ema_55_slope"] < 0, "trend_score"] -= 1
        dataframe.loc[dataframe["minus_di"] > dataframe["plus_di"], "trend_score"] -= 1
        return dataframe

    @staticmethod
    def _add_1h_indicators(dataframe: DataFrame) -> DataFrame:
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["roc_6"] = dataframe["close"] / dataframe["close"].shift(6) - 1
        dataframe["roc_24"] = dataframe["close"] / dataframe["close"].shift(24) - 1
        dataframe["ema_50_slope"] = dataframe["ema_50"] / dataframe["ema_50"].shift(12) - 1

        dataframe["regime_score"] = 0
        dataframe.loc[dataframe["close"] > dataframe["ema_50"], "regime_score"] += 1
        dataframe.loc[dataframe["ema_50"] > dataframe["ema_200"], "regime_score"] += 1
        dataframe.loc[dataframe["ema_50_slope"] > 0, "regime_score"] += 1
        dataframe.loc[dataframe["plus_di"] > dataframe["minus_di"], "regime_score"] += 1
        dataframe.loc[dataframe["close"] < dataframe["ema_50"], "regime_score"] -= 1
        dataframe.loc[dataframe["ema_50"] < dataframe["ema_200"], "regime_score"] -= 1
        dataframe.loc[dataframe["ema_50_slope"] < 0, "regime_score"] -= 1
        dataframe.loc[dataframe["minus_di"] > dataframe["plus_di"], "regime_score"] -= 1
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self._add_main_indicators(dataframe)

        if self.dp:
            inf_15m = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe="15m")
            inf_15m = self._add_15m_indicators(inf_15m)
            dataframe = merge_informative_pair(dataframe, inf_15m, self.timeframe, "15m", ffill=True)

            inf_1h = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe="1h")
            inf_1h = self._add_1h_indicators(inf_1h)
            dataframe = merge_informative_pair(dataframe, inf_1h, self.timeframe, "1h", ffill=True)

        pair = metadata["pair"]
        high_beta = pair.startswith(("DOGE/", "APT/", "AVAX/", "OP/", "SUI/", "SOL/"))
        main_atr_ceiling = 0.026 if high_beta else 0.018
        info_atr_ceiling = 0.060 if high_beta else 0.045

        dataframe["liquidity_ok"] = (
            (dataframe["volume"] > dataframe["volume_mean_30"] * 0.35)
            & (dataframe["volume_mean_120"] > 0)
            & (dataframe["volume_15m"] > dataframe["volume_mean_48_15m"] * 0.45)
        )
        dataframe["volatility_ok"] = (
            (dataframe["atr_pct"] > 0.00035)
            & (dataframe["atr_pct"] < main_atr_ceiling)
            & (dataframe["atr_pct_15m"] > 0.0018)
            & (dataframe["atr_pct_15m"] < info_atr_ceiling)
            & (dataframe["bb_width"] > 0.0022)
        )
        dataframe["risk_ok"] = dataframe["liquidity_ok"] & dataframe["volatility_ok"]

        dataframe["long_regime"] = (
            (dataframe["trend_score_15m"] >= 1)
            & (dataframe["regime_score_1h"] >= 0)
            & (dataframe["roc_48_15m"] > -0.075)
            & (dataframe["roc_24_1h"] > -0.090)
            & (dataframe["rsi_15m"] > 38)
            & (dataframe["rsi_1h"] > 40)
        )
        dataframe["short_regime"] = (
            (dataframe["trend_score_15m"] <= -1)
            & (dataframe["regime_score_1h"] <= 0)
            & (dataframe["roc_48_15m"] < 0.075)
            & (dataframe["roc_24_1h"] < 0.090)
            & (dataframe["rsi_15m"] < 62)
            & (dataframe["rsi_1h"] < 60)
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        long_pullback = (
            self.trade_long
            & self.enable_pullback_entry
            & dataframe["long_regime"]
            & dataframe["risk_ok"]
            & (dataframe["ema_8"] > dataframe["ema_21"] * 0.998)
            & (dataframe["ema_21"] > dataframe["ema_55"] * 0.995)
            & (dataframe["low"] <= dataframe["bb_lowerband"] * 1.006)
            & qtpylib.crossed_above(dataframe["rsi_fast"], 34)
            & (dataframe["close"] > dataframe["ema_8"])
            & (dataframe["volume"] > 0)
        )
        long_breakout = (
            self.trade_long
            & self.enable_breakout_entry
            & dataframe["long_regime"]
            & dataframe["risk_ok"]
            & (dataframe["close"] > dataframe["donchian_high"])
            & (dataframe["ema_8_slope"] > 0)
            & (dataframe["rsi"] > 49)
            & (dataframe["rsi"] < 76)
            & (dataframe["adx"] > 11)
            & (dataframe["volume_ratio"] > 0.75)
            & (dataframe["volume"] > 0)
        )
        long_reclaim = (
            self.trade_long
            & self.enable_reclaim_entry
            & dataframe["long_regime"]
            & dataframe["risk_ok"]
            & qtpylib.crossed_above(dataframe["close"], dataframe["ema_21"])
            & (dataframe["roc_3"] > 0)
            & (dataframe["rsi_fast"] > 42)
            & (dataframe["rsi_fast"] < 70)
            & (dataframe["plus_di"] >= dataframe["minus_di"] * 0.78)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[long_pullback, ["enter_long", "enter_tag"]] = (1, "fusion_bb_pullback_long")
        dataframe.loc[long_breakout, ["enter_long", "enter_tag"]] = (1, "fusion_donchian_long")
        dataframe.loc[long_reclaim, ["enter_long", "enter_tag"]] = (1, "fusion_reclaim_long")

        short_rebound = (
            self.trade_short
            & self.enable_pullback_entry
            & dataframe["short_regime"]
            & dataframe["risk_ok"]
            & (dataframe["ema_8"] < dataframe["ema_21"] * 1.002)
            & (dataframe["ema_21"] < dataframe["ema_55"] * 1.005)
            & (dataframe["high"] >= dataframe["bb_upperband"] * 0.994)
            & qtpylib.crossed_below(dataframe["rsi_fast"], 66)
            & (dataframe["close"] < dataframe["ema_8"])
            & (dataframe["volume"] > 0)
        )
        short_breakdown = (
            self.trade_short
            & self.enable_breakout_entry
            & dataframe["short_regime"]
            & dataframe["risk_ok"]
            & (dataframe["close"] < dataframe["donchian_low"])
            & (dataframe["ema_8_slope"] < 0)
            & (dataframe["rsi"] < 51)
            & (dataframe["rsi"] > 24)
            & (dataframe["adx"] > 11)
            & (dataframe["volume_ratio"] > 0.75)
            & (dataframe["volume"] > 0)
        )
        short_reclaim = (
            self.trade_short
            & self.enable_reclaim_entry
            & dataframe["short_regime"]
            & dataframe["risk_ok"]
            & qtpylib.crossed_below(dataframe["close"], dataframe["ema_21"])
            & (dataframe["roc_3"] < 0)
            & (dataframe["rsi_fast"] < 58)
            & (dataframe["rsi_fast"] > 30)
            & (dataframe["minus_di"] >= dataframe["plus_di"] * 0.78)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[short_rebound, ["enter_short", "enter_tag"]] = (1, "fusion_bb_rebound_short")
        dataframe.loc[short_breakdown, ["enter_short", "enter_tag"]] = (1, "fusion_donchian_short")
        dataframe.loc[short_reclaim, ["enter_short", "enter_tag"]] = (1, "fusion_reclaim_short")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (
                    ((dataframe["rsi_fast"] > 78) & (dataframe["close"] > dataframe["bb_upperband"]))
                    | qtpylib.crossed_below(dataframe["close"], dataframe["ema_21"])
                    | (dataframe["trend_score_15m"] <= -2)
                )
                & (dataframe["volume"] > 0)
            ),
            ["exit_long", "exit_tag"],
        ] = (1, "fusion_long_reversal")

        dataframe.loc[
            (
                (
                    ((dataframe["rsi_fast"] < 22) & (dataframe["close"] < dataframe["bb_lowerband"]))
                    | qtpylib.crossed_above(dataframe["close"], dataframe["ema_21"])
                    | (dataframe["trend_score_15m"] >= 2)
                )
                & (dataframe["volume"] > 0)
            ),
            ["exit_short", "exit_tag"],
        ] = (1, "fusion_short_reversal")
        return dataframe

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        stake = proposed_stake / self.max_dca_multiplier
        for prefix, weight in self.pair_stake_weights.items():
            if pair.startswith(prefix):
                stake *= weight
                break
        if min_stake:
            stake = max(stake, min_stake)
        return min(stake, max_stake)

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: float | None,
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs,
    ) -> float | None | tuple[float | None, str | None]:
        if trade.has_open_orders or trade.nr_of_successful_entries > self.max_entry_position_adjustment:
            return None
        if current_profit > -0.014:
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe is None or len(dataframe) < 4:
            return None
        last_candle = dataframe.iloc[-1].squeeze()
        prev_candle = dataframe.iloc[-2].squeeze()

        if trade.is_short:
            regime_ok = last_candle["short_regime"] and last_candle["trend_score_15m"] <= 0
            stabilizing = last_candle["close"] <= prev_candle["close"] * 1.002
        else:
            regime_ok = last_candle["long_regime"] and last_candle["trend_score_15m"] >= 0
            stabilizing = last_candle["close"] >= prev_candle["close"] * 0.998

        if not regime_ok or not stabilizing or last_candle["atr_pct"] > 0.024:
            return None

        filled_entries = trade.select_filled_orders(trade.entry_side)
        if not filled_entries:
            return None
        stake = filled_entries[0].stake_amount_filled * 0.35
        if min_stake:
            stake = max(stake, min_stake)
        stake = min(stake, max_stake)
        if stake <= 0:
            return None
        return stake, "fusion_single_safety_order"

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
        if pair.startswith(("BTC/", "ETH/")):
            target = 3.0
        elif pair.startswith(("DOGE/", "APT/", "AVAX/", "OP/", "SUI/", "SOL/")):
            target = 4.0
        else:
            target = 3.5
        return min(target, max_leverage, 5.0)

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool | None:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None

        last_candle = dataframe.iloc[-1].squeeze()

        if trade.is_short:
            if current_profit > 0.018 and last_candle["rsi_fast"] < 24:
                return "fusion_short_fast_take_profit"
            if current_profit > 0.006 and last_candle["close"] > last_candle["ema_21"]:
                return "fusion_short_profit_protect"
            if current_profit < -0.026 and last_candle["trend_score_15m"] >= 3:
                return "fusion_short_regime_cut"
            return None

        if current_profit > 0.018 and last_candle["rsi_fast"] > 76:
            return "fusion_long_fast_take_profit"
        if current_profit > 0.006 and last_candle["close"] < last_candle["ema_21"]:
            return "fusion_long_profit_protect"
        if current_profit < -0.026 and last_candle["trend_score_15m"] <= -3:
            return "fusion_long_regime_cut"
        return None


class Intp20OpenFusionLongScalpStrategy(Intp20OpenFusionScalpStrategy):
    trade_long = True
    trade_short = False


class Intp20OpenFusionShortScalpStrategy(Intp20OpenFusionScalpStrategy):
    trade_long = False
    trade_short = True


class Intp20OpenFusionDonchianLongScalpStrategy(Intp20OpenFusionLongScalpStrategy):
    """
    Version 2 scalp research: keep only the highest-quality trend-continuation
    path from the first short-window test.
    """

    exit_profit_only = True
    stoploss = -0.030
    enable_pullback_entry = False
    enable_breakout_entry = True
    enable_reclaim_entry = False

    minimal_roi = {
        "60": 0.0018,
        "20": 0.0032,
        "6": 0.0060,
        "0": 0.0105,
    }

    trailing_stop_positive = 0.0028
    trailing_stop_positive_offset = 0.0090


class Intp20OpenFusionDonchianShortScalpStrategy(Intp20OpenFusionShortScalpStrategy):
    """
    Short-account version of the version 2 Donchian-only scalp profile.
    """

    exit_profit_only = True
    stoploss = -0.030
    enable_pullback_entry = False
    enable_breakout_entry = True
    enable_reclaim_entry = False

    minimal_roi = {
        "60": 0.0018,
        "20": 0.0032,
        "6": 0.0060,
        "0": 0.0105,
    }

    trailing_stop_positive = 0.0028
    trailing_stop_positive_offset = 0.0090


class Intp20OpenFusionTightLongScalpStrategy(Intp20OpenFusionDonchianLongScalpStrategy):
    """
    Version 3: no DCA, tighter loss budget, and smaller scalp target.

    The previous test had a high win rate but a loss/win imbalance. This profile
    tests whether a narrow invalidation point can make the same entry family
    usable after fees.
    """

    position_adjustment_enable = False
    max_entry_position_adjustment = 0
    max_dca_multiplier = 1.0
    stoploss = -0.010

    minimal_roi = {
        "45": 0.0012,
        "15": 0.0025,
        "4": 0.0045,
        "0": 0.0075,
    }

    trailing_stop_positive = 0.0018
    trailing_stop_positive_offset = 0.0055


class Intp20OpenFusionTightShortScalpStrategy(Intp20OpenFusionDonchianShortScalpStrategy):
    """
    Short-account version of the no-DCA tight-loss scalp profile.
    """

    position_adjustment_enable = False
    max_entry_position_adjustment = 0
    max_dca_multiplier = 1.0
    stoploss = -0.010

    minimal_roi = {
        "45": 0.0012,
        "15": 0.0025,
        "4": 0.0045,
        "0": 0.0075,
    }

    trailing_stop_positive = 0.0018
    trailing_stop_positive_offset = 0.0055
