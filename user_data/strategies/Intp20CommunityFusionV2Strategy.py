from datetime import datetime

import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair


class Intp20CommunityFusionV2Strategy(IStrategy):
    """
    Community-fusion futures research profile.

    This strategy is an original synthesis of common open strategy motifs:
    trend-state stacking, SmoothScalp-style oscillator turns, volatility
    expansion entries, and bounded DCA with strict invalidation checks.
    """

    INTERFACE_VERSION = 3

    timeframe = "1m"
    startup_candle_count = 2400
    can_short = True

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = True
    ignore_roi_if_entry_signal = False

    position_adjustment_enable = True
    max_entry_position_adjustment = 1
    max_dca_multiplier = 1.35

    trade_long = True
    trade_short = True
    enable_pullback = True
    enable_breakout = True
    enable_smooth = True

    minimal_roi = {
        "180": 0.0015,
        "45": 0.0035,
        "12": 0.0070,
        "0": 0.0150,
    }

    stoploss = -0.038
    trailing_stop = True
    trailing_stop_positive = 0.0035
    trailing_stop_positive_offset = 0.0110
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
        "AAVE/": 1.16,
        "AVAX/": 1.14,
        "BCH/": 1.10,
        "DOGE/": 1.08,
        "LTC/": 1.07,
        "MKR/": 1.06,
        "SOL/": 1.06,
        "SUI/": 1.04,
        "APT/": 1.02,
        "BTC/": 0.96,
        "ETH/": 0.92,
        "BNB/": 0.82,
        "TRX/": 0.78,
    }

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 5,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 720,
                "trade_limit": 4,
                "stop_duration_candles": 180,
                "only_per_side": True,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 2880,
                "trade_limit": 80,
                "stop_duration_candles": 360,
                "max_allowed_drawdown": 0.22,
            },
        ]

    plot_config = {
        "main_plot": {
            "ema_8": {"color": "yellow"},
            "ema_21": {"color": "orange"},
            "ema_55": {"color": "blue"},
            "vwap_60": {"color": "black"},
            "bb_lowerband": {"color": "grey"},
            "bb_upperband": {"color": "grey"},
        },
        "subplots": {
            "Momentum": {
                "rsi": {"color": "purple"},
                "fastk": {"color": "green"},
                "cci": {"color": "red"},
            },
            "Regime": {
                "trend_score_15m": {"color": "blue"},
                "trend_score_1h": {"color": "black"},
            },
        },
    }

    def informative_pairs(self):
        if not self.dp:
            return []
        pairs = self.dp.current_whitelist()
        return [(pair, "15m") for pair in pairs] + [(pair, "1h") for pair in pairs]

    @staticmethod
    def _ewo(dataframe: DataFrame, fast: int = 5, slow: int = 35):
        ema_fast = ta.EMA(dataframe, timeperiod=fast)
        ema_slow = ta.EMA(dataframe, timeperiod=slow)
        return (ema_fast - ema_slow) / dataframe["close"] * 100

    @staticmethod
    def _add_main_indicators(dataframe: DataFrame) -> DataFrame:
        dataframe["ema_5"] = ta.EMA(dataframe, timeperiod=5)
        dataframe["ema_8"] = ta.EMA(dataframe, timeperiod=8)
        dataframe["ema_13"] = ta.EMA(dataframe, timeperiod=13)
        dataframe["ema_21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema_55"] = ta.EMA(dataframe, timeperiod=55)
        dataframe["ema_144"] = ta.EMA(dataframe, timeperiod=144)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_fast"] = ta.RSI(dataframe, timeperiod=4)
        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)
        dataframe["cci"] = ta.CCI(dataframe, timeperiod=20)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["ewo"] = Intp20CommunityFusionV2Strategy._ewo(dataframe)

        stoch_fast = ta.STOCHF(dataframe, 5, 3, 0, 3, 0)
        dataframe["fastk"] = stoch_fast["fastk"]
        dataframe["fastd"] = stoch_fast["fastd"]

        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]
        dataframe["bb_width"] = (
            (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe["bb_middleband"]
        )
        dataframe["bb_pct"] = (
            (dataframe["close"] - dataframe["bb_lowerband"])
            / (dataframe["bb_upperband"] - dataframe["bb_lowerband"])
        )

        tpv = qtpylib.typical_price(dataframe) * dataframe["volume"]
        volume_60 = dataframe["volume"].rolling(60).sum()
        dataframe["vwap_60"] = tpv.rolling(60).sum() / volume_60
        dataframe["volume_mean_30"] = dataframe["volume"].rolling(30).mean()
        dataframe["volume_mean_120"] = dataframe["volume"].rolling(120).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_mean_30"]

        dataframe["range_high_34"] = dataframe["high"].rolling(34).max().shift(1)
        dataframe["range_low_34"] = dataframe["low"].rolling(34).min().shift(1)
        dataframe["range_high_89"] = dataframe["high"].rolling(89).max().shift(1)
        dataframe["range_low_89"] = dataframe["low"].rolling(89).min().shift(1)
        dataframe["roc_5"] = dataframe["close"] / dataframe["close"].shift(5) - 1
        dataframe["roc_20"] = dataframe["close"] / dataframe["close"].shift(20) - 1
        dataframe["roc_60"] = dataframe["close"] / dataframe["close"].shift(60) - 1
        dataframe["ema_21_slope"] = dataframe["ema_21"] / dataframe["ema_21"].shift(21) - 1
        dataframe["ema_55_slope"] = dataframe["ema_55"] / dataframe["ema_55"].shift(55) - 1
        dataframe["body_pct"] = (dataframe["close"] - dataframe["open"]).abs() / dataframe["close"]
        dataframe["wick_pct"] = (
            (dataframe["high"] - dataframe["low"])
            - (dataframe["close"] - dataframe["open"]).abs()
        ) / dataframe["close"]
        dataframe["signal_tick"] = dataframe["date"].dt.minute.mod(3).eq(2)
        return dataframe

    @staticmethod
    def _add_informative_indicators(dataframe: DataFrame) -> DataFrame:
        dataframe["ema_12"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["ema_26"] = ta.EMA(dataframe, timeperiod=26)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_100"] = ta.EMA(dataframe, timeperiod=100)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["ewo"] = Intp20CommunityFusionV2Strategy._ewo(dataframe, 12, 50)
        dataframe["roc_4"] = dataframe["close"] / dataframe["close"].shift(4) - 1
        dataframe["roc_12"] = dataframe["close"] / dataframe["close"].shift(12) - 1
        dataframe["roc_24"] = dataframe["close"] / dataframe["close"].shift(24) - 1
        dataframe["ema_50_slope"] = dataframe["ema_50"] / dataframe["ema_50"].shift(12) - 1
        dataframe["ema_100_slope"] = dataframe["ema_100"] / dataframe["ema_100"].shift(24) - 1
        dataframe["volume_mean_24"] = dataframe["volume"].rolling(24).mean()

        dataframe["trend_score"] = 0
        dataframe.loc[dataframe["close"] > dataframe["ema_50"], "trend_score"] += 1
        dataframe.loc[dataframe["ema_12"] > dataframe["ema_26"], "trend_score"] += 1
        dataframe.loc[dataframe["ema_26"] > dataframe["ema_50"], "trend_score"] += 1
        dataframe.loc[dataframe["ema_50"] > dataframe["ema_100"], "trend_score"] += 1
        dataframe.loc[dataframe["ema_100"] > dataframe["ema_200"], "trend_score"] += 1
        dataframe.loc[dataframe["ema_50_slope"] > 0, "trend_score"] += 1
        dataframe.loc[dataframe["plus_di"] > dataframe["minus_di"], "trend_score"] += 1
        dataframe.loc[dataframe["ewo"] > 0, "trend_score"] += 1
        dataframe.loc[dataframe["close"] < dataframe["ema_50"], "trend_score"] -= 1
        dataframe.loc[dataframe["ema_12"] < dataframe["ema_26"], "trend_score"] -= 1
        dataframe.loc[dataframe["ema_26"] < dataframe["ema_50"], "trend_score"] -= 1
        dataframe.loc[dataframe["ema_50"] < dataframe["ema_100"], "trend_score"] -= 1
        dataframe.loc[dataframe["ema_100"] < dataframe["ema_200"], "trend_score"] -= 1
        dataframe.loc[dataframe["ema_50_slope"] < 0, "trend_score"] -= 1
        dataframe.loc[dataframe["minus_di"] > dataframe["plus_di"], "trend_score"] -= 1
        dataframe.loc[dataframe["ewo"] < 0, "trend_score"] -= 1
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self._add_main_indicators(dataframe)

        if self.dp:
            inf_15m = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe="15m")
            inf_15m = self._add_informative_indicators(inf_15m)
            dataframe = merge_informative_pair(dataframe, inf_15m, self.timeframe, "15m", ffill=True)

            inf_1h = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe="1h")
            inf_1h = self._add_informative_indicators(inf_1h)
            dataframe = merge_informative_pair(dataframe, inf_1h, self.timeframe, "1h", ffill=True)

        pair = metadata["pair"]
        high_beta = pair.startswith(("APT/", "AVAX/", "DOGE/", "OP/", "SOL/", "SUI/"))
        atr_ceiling = 0.022 if high_beta else 0.016
        info_atr_ceiling = 0.055 if high_beta else 0.042
        dataframe["liquidity_ok"] = (
            (dataframe["volume"] > dataframe["volume_mean_30"] * 0.45)
            & (dataframe["volume_mean_120"] > 0)
            & (dataframe["volume_15m"] > dataframe["volume_mean_24_15m"] * 0.50)
        )
        dataframe["volatility_ok"] = (
            (dataframe["atr_pct"] > 0.00045)
            & (dataframe["atr_pct"] < atr_ceiling)
            & (dataframe["atr_pct_15m"] > 0.0018)
            & (dataframe["atr_pct_15m"] < info_atr_ceiling)
            & (dataframe["bb_width"] > 0.0025)
        )
        dataframe["risk_ok"] = dataframe["liquidity_ok"] & dataframe["volatility_ok"]

        dataframe["long_regime"] = (
            (dataframe["trend_score_15m"] >= 3)
            & (dataframe["trend_score_1h"] >= 0)
            & (dataframe["rsi_15m"] > 42)
            & (dataframe["rsi_1h"] > 40)
            & (dataframe["roc_24_15m"] > -0.060)
            & (dataframe["roc_24_1h"] > -0.090)
            & (dataframe["atr_pct_1h"] < info_atr_ceiling)
        )
        dataframe["short_regime"] = (
            (dataframe["trend_score_15m"] <= -3)
            & (dataframe["trend_score_1h"] <= 0)
            & (dataframe["rsi_15m"] < 58)
            & (dataframe["rsi_1h"] < 60)
            & (dataframe["roc_24_15m"] < 0.060)
            & (dataframe["roc_24_1h"] < 0.090)
            & (dataframe["atr_pct_1h"] < info_atr_ceiling)
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        long_pullback = (
            self.trade_long
            & self.enable_pullback
            & dataframe["signal_tick"]
            & dataframe["long_regime"]
            & dataframe["risk_ok"]
            & (dataframe["close"] > dataframe["ema_55"] * 0.992)
            & (dataframe["ema_21"] > dataframe["ema_55"] * 0.996)
            & (dataframe["low"] < dataframe["vwap_60"] * 1.004)
            & (dataframe["close"] > dataframe["ema_8"])
            & (dataframe["rsi_fast"] > 30)
            & (dataframe["rsi_fast"] < 56)
            & qtpylib.crossed_above(dataframe["rsi_fast"], 34)
            & (dataframe["mfi"] < 62)
            & (dataframe["roc_20"] > -0.018)
            & (dataframe["volume"] > 0)
        )
        long_breakout = (
            self.trade_long
            & self.enable_breakout
            & dataframe["signal_tick"]
            & dataframe["long_regime"]
            & dataframe["risk_ok"]
            & qtpylib.crossed_above(dataframe["close"], dataframe["range_high_34"])
            & (dataframe["close"] < dataframe["range_high_89"] * 1.020)
            & (dataframe["ema_21_slope"] > 0)
            & (dataframe["volume_ratio"] > 1.10)
            & (dataframe["rsi"] > 48)
            & (dataframe["rsi"] < 72)
            & (dataframe["adx"] > 12)
            & (dataframe["body_pct"] > dataframe["atr_pct"] * 0.20)
            & (dataframe["volume"] > 0)
        )
        long_smooth = (
            self.trade_long
            & self.enable_smooth
            & dataframe["signal_tick"]
            & dataframe["long_regime"]
            & dataframe["risk_ok"]
            & (dataframe["low"] <= dataframe["bb_lowerband"] * 1.008)
            & (dataframe["cci"] < -110)
            & (dataframe["mfi"] < 36)
            & (dataframe["fastk"] < 35)
            & qtpylib.crossed_above(dataframe["fastk"], dataframe["fastd"])
            & (dataframe["ewo_15m"] > -2.2)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[long_pullback, ["enter_long", "enter_tag"]] = (1, "fusion_v2_pullback_long")
        dataframe.loc[long_breakout, ["enter_long", "enter_tag"]] = (1, "fusion_v2_breakout_long")
        dataframe.loc[long_smooth, ["enter_long", "enter_tag"]] = (1, "fusion_v2_smooth_long")

        short_rebound = (
            self.trade_short
            & self.enable_pullback
            & dataframe["signal_tick"]
            & dataframe["short_regime"]
            & dataframe["risk_ok"]
            & (dataframe["close"] < dataframe["ema_55"] * 1.008)
            & (dataframe["ema_21"] < dataframe["ema_55"] * 1.004)
            & (dataframe["high"] > dataframe["vwap_60"] * 0.996)
            & (dataframe["close"] < dataframe["ema_8"])
            & (dataframe["rsi_fast"] < 70)
            & (dataframe["rsi_fast"] > 44)
            & qtpylib.crossed_below(dataframe["rsi_fast"], 66)
            & (dataframe["mfi"] > 38)
            & (dataframe["roc_20"] < 0.018)
            & (dataframe["volume"] > 0)
        )
        short_breakout = (
            self.trade_short
            & self.enable_breakout
            & dataframe["signal_tick"]
            & dataframe["short_regime"]
            & dataframe["risk_ok"]
            & qtpylib.crossed_below(dataframe["close"], dataframe["range_low_34"])
            & (dataframe["close"] > dataframe["range_low_89"] * 0.980)
            & (dataframe["ema_21_slope"] < 0)
            & (dataframe["volume_ratio"] > 1.10)
            & (dataframe["rsi"] < 52)
            & (dataframe["rsi"] > 28)
            & (dataframe["adx"] > 12)
            & (dataframe["body_pct"] > dataframe["atr_pct"] * 0.20)
            & (dataframe["volume"] > 0)
        )
        short_smooth = (
            self.trade_short
            & self.enable_smooth
            & dataframe["signal_tick"]
            & dataframe["short_regime"]
            & dataframe["risk_ok"]
            & (dataframe["high"] >= dataframe["bb_upperband"] * 0.992)
            & (dataframe["cci"] > 110)
            & (dataframe["mfi"] > 64)
            & (dataframe["fastk"] > 65)
            & qtpylib.crossed_below(dataframe["fastk"], dataframe["fastd"])
            & (dataframe["ewo_15m"] < 2.2)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[short_rebound, ["enter_short", "enter_tag"]] = (1, "fusion_v2_rebound_short")
        dataframe.loc[short_breakout, ["enter_short", "enter_tag"]] = (1, "fusion_v2_breakdown_short")
        dataframe.loc[short_smooth, ["enter_short", "enter_tag"]] = (1, "fusion_v2_smooth_short")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                self.trade_long
                & (
                    ((dataframe["rsi_fast"] > 76) & (dataframe["close"] > dataframe["bb_upperband"]))
                    | ((dataframe["close"] < dataframe["ema_21"]) & (dataframe["rsi_fast"] < 38))
                    | (dataframe["trend_score_15m"] <= -2)
                )
                & (dataframe["volume"] > 0)
            ),
            ["exit_long", "exit_tag"],
        ] = (1, "fusion_v2_long_exit")

        dataframe.loc[
            (
                self.trade_short
                & (
                    ((dataframe["rsi_fast"] < 24) & (dataframe["close"] < dataframe["bb_lowerband"]))
                    | ((dataframe["close"] > dataframe["ema_21"]) & (dataframe["rsi_fast"] > 62))
                    | (dataframe["trend_score_15m"] >= 2)
                )
                & (dataframe["volume"] > 0)
            ),
            ["exit_short", "exit_tag"],
        ] = (1, "fusion_v2_short_exit")
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
        if current_profit > -0.016:
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe is None or len(dataframe) < 4:
            return None

        last_candle = dataframe.iloc[-1].squeeze()
        prev_candle = dataframe.iloc[-2].squeeze()
        if trade.is_short:
            if (
                not last_candle["short_regime"]
                or last_candle["trend_score_15m"] > -1
                or last_candle["close"] > prev_candle["close"] * 1.004
            ):
                return None
        else:
            if (
                not last_candle["long_regime"]
                or last_candle["trend_score_15m"] < 1
                or last_candle["close"] < prev_candle["close"] * 0.996
            ):
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
        return stake, "fusion_v2_single_safety_order"

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
        elif pair.startswith(("APT/", "AVAX/", "DOGE/", "OP/", "SOL/", "SUI/")):
            target = 5.0
        else:
            target = 4.0
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
            if current_profit > 0.020 and last_candle["rsi_fast"] < 24:
                return "fusion_v2_short_fast_take_profit"
            if current_profit > 0.008 and last_candle["close"] < last_candle["bb_lowerband"]:
                return "fusion_v2_short_band_take_profit"
            if current_profit > 0.004 and last_candle["close"] > last_candle["ema_21"]:
                return "fusion_v2_short_profit_guard"
            if current_profit < -0.022 and last_candle["trend_score_15m"] >= 2:
                return "fusion_v2_short_regime_cut"
            if current_profit < -0.030 and last_candle["close"] > last_candle["ema_55"]:
                return "fusion_v2_short_structure_cut"
            return None

        if current_profit > 0.020 and last_candle["rsi_fast"] > 76:
            return "fusion_v2_long_fast_take_profit"
        if current_profit > 0.008 and last_candle["close"] > last_candle["bb_upperband"]:
            return "fusion_v2_long_band_take_profit"
        if current_profit > 0.004 and last_candle["close"] < last_candle["ema_21"]:
            return "fusion_v2_long_profit_guard"
        if current_profit < -0.022 and last_candle["trend_score_15m"] <= -2:
            return "fusion_v2_long_regime_cut"
        if current_profit < -0.030 and last_candle["close"] < last_candle["ema_55"]:
            return "fusion_v2_long_structure_cut"
        return None


class Intp20CommunityFusionV2LongStrategy(Intp20CommunityFusionV2Strategy):
    trade_long = True
    trade_short = False


class Intp20CommunityFusionV2ShortStrategy(Intp20CommunityFusionV2Strategy):
    trade_long = False
    trade_short = True


class Intp20CommunityFusionV2NoDcaLongStrategy(Intp20CommunityFusionV2LongStrategy):
    position_adjustment_enable = False
    max_entry_position_adjustment = 0
    max_dca_multiplier = 1.0
    stoploss = -0.026

    minimal_roi = {
        "150": 0.0012,
        "35": 0.0030,
        "10": 0.0060,
        "0": 0.0130,
    }


class Intp20CommunityFusionV2NoDcaShortStrategy(Intp20CommunityFusionV2ShortStrategy):
    position_adjustment_enable = False
    max_entry_position_adjustment = 0
    max_dca_multiplier = 1.0
    stoploss = -0.026

    minimal_roi = {
        "150": 0.0012,
        "35": 0.0030,
        "10": 0.0060,
        "0": 0.0130,
    }
