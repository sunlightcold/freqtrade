from datetime import datetime

import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair


class Intp20CommunityMomentumStrategy(IStrategy):
    """
    1m execution / 5m signal research profile.

    This is a compact, original synthesis of common open strategy motifs:
    multi-timeframe trend filters, RSI/MFI/CCI pullbacks, EWO-style momentum,
    Bollinger location, and bounded safety orders.
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
    max_dca_multiplier = 1.45

    trade_long = True
    trade_short = True

    minimal_roi = {
        "360": 0.0020,
        "90": 0.0040,
        "25": 0.0080,
        "0": 0.0180,
    }

    stoploss = -0.060
    trailing_stop = True
    trailing_stop_positive = 0.006
    trailing_stop_positive_offset = 0.018
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

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 10,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 720,
                "trade_limit": 4,
                "stop_duration_candles": 240,
                "only_per_side": True,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 2880,
                "trade_limit": 50,
                "stop_duration_candles": 480,
                "max_allowed_drawdown": 0.18,
            },
        ]

    def informative_pairs(self):
        if not self.dp:
            return []
        pairs = self.dp.current_whitelist()
        return [(pair, "15m") for pair in pairs] + [(pair, "1h") for pair in pairs]

    @staticmethod
    def _ewo(dataframe: DataFrame, fast: int = 12, slow: int = 50) -> DataFrame:
        ema_fast = ta.EMA(dataframe, timeperiod=fast)
        ema_slow = ta.EMA(dataframe, timeperiod=slow)
        return (ema_fast - ema_slow) / dataframe["close"] * 100

    @staticmethod
    def _add_main_indicators(dataframe: DataFrame) -> DataFrame:
        dataframe["ema_8"] = ta.EMA(dataframe, timeperiod=8)
        dataframe["ema_12"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["ema_26"] = ta.EMA(dataframe, timeperiod=26)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_fast"] = ta.RSI(dataframe, timeperiod=4)
        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)
        dataframe["cci"] = ta.CCI(dataframe, timeperiod=20)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["ewo"] = Intp20CommunityMomentumStrategy._ewo(dataframe, 12, 50)
        dataframe["volume_mean_60"] = dataframe["volume"].rolling(60).mean()
        dataframe["volume_mean_240"] = dataframe["volume"].rolling(240).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_mean_60"]

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

        dataframe["roc_5"] = dataframe["close"] / dataframe["close"].shift(5) - 1
        dataframe["roc_20"] = dataframe["close"] / dataframe["close"].shift(20) - 1
        dataframe["is_5m_signal"] = dataframe["date"].dt.minute.mod(5).eq(4)
        return dataframe

    @staticmethod
    def _add_informative_indicators(dataframe: DataFrame) -> DataFrame:
        dataframe["ema_12"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)
        dataframe["ewo"] = Intp20CommunityMomentumStrategy._ewo(dataframe, 12, 50)
        dataframe["roc_4"] = dataframe["close"] / dataframe["close"].shift(4) - 1
        dataframe["roc_16"] = dataframe["close"] / dataframe["close"].shift(16) - 1
        dataframe["ema_50_slope"] = dataframe["ema_50"] / dataframe["ema_50"].shift(12) - 1
        dataframe["trend_score"] = 0
        dataframe.loc[dataframe["close"] > dataframe["ema_50"], "trend_score"] += 1
        dataframe.loc[dataframe["ema_12"] > dataframe["ema_50"], "trend_score"] += 1
        dataframe.loc[dataframe["ema_50"] > dataframe["ema_200"], "trend_score"] += 1
        dataframe.loc[dataframe["ema_50_slope"] > 0, "trend_score"] += 1
        dataframe.loc[dataframe["ewo"] > 0, "trend_score"] += 1
        dataframe.loc[dataframe["close"] < dataframe["ema_50"], "trend_score"] -= 1
        dataframe.loc[dataframe["ema_12"] < dataframe["ema_50"], "trend_score"] -= 1
        dataframe.loc[dataframe["ema_50"] < dataframe["ema_200"], "trend_score"] -= 1
        dataframe.loc[dataframe["ema_50_slope"] < 0, "trend_score"] -= 1
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
        high_beta = pair.startswith(("DOGE/", "APT/", "AVAX/", "OP/", "SUI/", "SOL/"))
        dataframe["liquidity_ok"] = (
            (dataframe["volume"] > dataframe["volume_mean_60"] * 0.35)
            & (dataframe["volume_mean_240"] > 0)
        )
        dataframe["volatility_ok"] = (
            (dataframe["atr_pct"] > 0.00045)
            & (dataframe["atr_pct"] < (0.018 if high_beta else 0.014))
            & (dataframe["atr_pct_15m"] > 0.0018)
            & (dataframe["atr_pct_15m"] < (0.055 if high_beta else 0.040))
            & (dataframe["bb_width"] > 0.0025)
        )
        dataframe["long_regime"] = (
            (dataframe["trend_score_15m"] >= 2)
            & (dataframe["trend_score_1h"] >= 0)
            & (dataframe["roc_16_15m"] > -0.055)
            & (dataframe["rsi_15m"] > 39)
            & (dataframe["rsi_1h"] > 40)
        )
        dataframe["short_regime"] = (
            (dataframe["trend_score_15m"] <= -2)
            & (dataframe["trend_score_1h"] <= 0)
            & (dataframe["roc_16_15m"] < 0.055)
            & (dataframe["rsi_15m"] < 61)
            & (dataframe["rsi_1h"] < 60)
        )
        dataframe["risk_ok"] = dataframe["liquidity_ok"] & dataframe["volatility_ok"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        long_deep_pullback = (
            self.trade_long
            & dataframe["is_5m_signal"]
            & dataframe["long_regime"]
            & dataframe["risk_ok"]
            & (dataframe["close"] < dataframe["bb_lowerband"] * 1.010)
            & (dataframe["rsi"] < 38)
            & (dataframe["mfi"] < 42)
            & (dataframe["cci"] < -80)
            & (dataframe["ewo_15m"] > -1.8)
            & (dataframe["fastk"] < 35)
            & qtpylib.crossed_above(dataframe["fastk"], dataframe["fastd"])
            & (dataframe["volume"] > 0)
        )
        long_momentum_pullback = (
            self.trade_long
            & dataframe["is_5m_signal"]
            & dataframe["long_regime"]
            & dataframe["risk_ok"]
            & (dataframe["ewo"] > 0.10)
            & (dataframe["close"] < dataframe["ema_50"] * 0.992)
            & (dataframe["rsi_fast"] < 38)
            & (dataframe["mfi"] < 55)
            & (dataframe["roc_20"] > -0.018)
            & qtpylib.crossed_above(dataframe["rsi_fast"], 28)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[long_deep_pullback, ["enter_long", "enter_tag"]] = (
            1,
            "community_deep_pullback_long",
        )
        dataframe.loc[long_momentum_pullback, ["enter_long", "enter_tag"]] = (
            1,
            "community_momentum_pullback_long",
        )

        short_deep_rebound = (
            self.trade_short
            & dataframe["is_5m_signal"]
            & dataframe["short_regime"]
            & dataframe["risk_ok"]
            & (dataframe["close"] > dataframe["bb_upperband"] * 0.990)
            & (dataframe["rsi"] > 62)
            & (dataframe["mfi"] > 58)
            & (dataframe["cci"] > 80)
            & (dataframe["ewo_15m"] < 1.8)
            & (dataframe["fastk"] > 65)
            & qtpylib.crossed_below(dataframe["fastk"], dataframe["fastd"])
            & (dataframe["volume"] > 0)
        )
        short_momentum_rebound = (
            self.trade_short
            & dataframe["is_5m_signal"]
            & dataframe["short_regime"]
            & dataframe["risk_ok"]
            & (dataframe["ewo"] < -0.10)
            & (dataframe["close"] > dataframe["ema_50"] * 1.008)
            & (dataframe["rsi_fast"] > 62)
            & (dataframe["mfi"] > 45)
            & (dataframe["roc_20"] < 0.018)
            & qtpylib.crossed_below(dataframe["rsi_fast"], 72)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[short_deep_rebound, ["enter_short", "enter_tag"]] = (
            1,
            "community_deep_rebound_short",
        )
        dataframe.loc[short_momentum_rebound, ["enter_short", "enter_tag"]] = (
            1,
            "community_momentum_rebound_short",
        )
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (
                    ((dataframe["rsi_fast"] > 78) & (dataframe["close"] > dataframe["bb_upperband"]))
                    | ((dataframe["close"] > dataframe["ema_50"]) & (dataframe["rsi"] > 58))
                    | (dataframe["trend_score_15m"] <= -3)
                )
                & (dataframe["volume"] > 0)
            ),
            ["exit_long", "exit_tag"],
        ] = (1, "community_long_profit_or_flip")

        dataframe.loc[
            (
                (
                    ((dataframe["rsi_fast"] < 22) & (dataframe["close"] < dataframe["bb_lowerband"]))
                    | ((dataframe["close"] < dataframe["ema_50"]) & (dataframe["rsi"] < 42))
                    | (dataframe["trend_score_15m"] >= 3)
                )
                & (dataframe["volume"] > 0)
            ),
            ["exit_short", "exit_tag"],
        ] = (1, "community_short_profit_or_flip")
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
        if current_profit > -0.020:
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe is None or len(dataframe) < 4:
            return None
        last_candle = dataframe.iloc[-1].squeeze()
        if trade.is_short:
            if not last_candle["short_regime"] or last_candle["rsi_fast"] < 50:
                return None
        else:
            if not last_candle["long_regime"] or last_candle["rsi_fast"] > 50:
                return None

        filled_entries = trade.select_filled_orders(trade.entry_side)
        if not filled_entries:
            return None
        stake = filled_entries[0].stake_amount_filled * 0.45
        if min_stake:
            stake = max(stake, min_stake)
        stake = min(stake, max_stake)
        if stake <= 0:
            return None
        return stake, "community_single_safety_order"

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
            if current_profit > 0.030 and last_candle["rsi_fast"] < 25:
                return "community_short_fast_take_profit"
            if current_profit > 0.012 and last_candle["close"] < last_candle["bb_lowerband"]:
                return "community_short_band_take_profit"
            if current_profit < -0.045 and last_candle["trend_score_15m"] >= 3:
                return "community_short_regime_cut"
            return None

        if current_profit > 0.030 and last_candle["rsi_fast"] > 75:
            return "community_long_fast_take_profit"
        if current_profit > 0.012 and last_candle["close"] > last_candle["bb_upperband"]:
            return "community_long_band_take_profit"
        if current_profit < -0.045 and last_candle["trend_score_15m"] <= -3:
            return "community_long_regime_cut"
        return None


class Intp20CommunityMomentumLongStrategy(Intp20CommunityMomentumStrategy):
    trade_long = True
    trade_short = False


class Intp20CommunityMomentumShortStrategy(Intp20CommunityMomentumStrategy):
    trade_long = False
    trade_short = True


class Intp20CommunityRiskCutLongStrategy(Intp20CommunityMomentumLongStrategy):
    """
    No-DCA risk-cut version after the first community test showed good hit-rate
    but unacceptable stop-loss drag.
    """

    position_adjustment_enable = False
    max_entry_position_adjustment = 0
    max_dca_multiplier = 1.0
    stoploss = -0.025

    minimal_roi = {
        "240": 0.0018,
        "70": 0.0036,
        "20": 0.0075,
        "0": 0.0160,
    }

    trailing_stop_positive = 0.0045
    trailing_stop_positive_offset = 0.014


class Intp20CommunityRiskCutShortStrategy(Intp20CommunityMomentumShortStrategy):
    """
    Short-account no-DCA risk-cut profile.
    """

    position_adjustment_enable = False
    max_entry_position_adjustment = 0
    max_dca_multiplier = 1.0
    stoploss = -0.025

    minimal_roi = {
        "240": 0.0018,
        "70": 0.0036,
        "20": 0.0075,
        "0": 0.0160,
    }

    trailing_stop_positive = 0.0045
    trailing_stop_positive_offset = 0.014


class Intp20CommunityMacroShortStrategy(Intp20CommunityMomentumShortStrategy):
    """
    Bear-regime short profile.

    The first positive AAVE/SUI short window was not stable across 2024/2025.
    This variant keeps the same entry trigger, but only enables it when the
    pair is already in a cleaner 15m/1h downtrend.
    """

    stoploss = -0.052
    max_dca_multiplier = 1.35

    minimal_roi = {
        "300": 0.0018,
        "80": 0.0040,
        "20": 0.0080,
        "0": 0.0170,
    }

    trailing_stop_positive = 0.0055
    trailing_stop_positive_offset = 0.017

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 12,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 720,
                "trade_limit": 3,
                "stop_duration_candles": 360,
                "only_per_side": True,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 2880,
                "trade_limit": 45,
                "stop_duration_candles": 720,
                "max_allowed_drawdown": 0.12,
            },
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        dataframe["short_regime"] = (
            (dataframe["trend_score_15m"] <= -3)
            & (dataframe["trend_score_1h"] <= -2)
            & (dataframe["close_1h"] < dataframe["ema_50_1h"] * 1.004)
            & (dataframe["ema_50_slope_1h"] < 0)
            & (dataframe["ewo_1h"] < 0)
            & (dataframe["roc_4_15m"] < 0.025)
            & (dataframe["roc_16_15m"] < 0.040)
            & (dataframe["roc_16_15m"] > -0.120)
            & (dataframe["rsi_15m"] < 56)
            & (dataframe["rsi_1h"] < 56)
            & dataframe["risk_ok"]
        )
        return dataframe


class Intp20CommunityBtcGuardShortStrategy(Intp20CommunityMomentumShortStrategy):
    """
    Short profile with a BTC market guard.

    Shorting alt rebounds during a BTC expansion trend produced the largest
    long-window failures. This variant keeps the active short trigger, but
    requires BTC itself to be weak or at least not expanding upward on 1h.
    """

    stoploss = -0.055
    max_dca_multiplier = 1.45

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 10,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 720,
                "trade_limit": 3,
                "stop_duration_candles": 360,
                "only_per_side": True,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 2880,
                "trade_limit": 45,
                "stop_duration_candles": 720,
                "max_allowed_drawdown": 0.14,
            },
        ]

    def informative_pairs(self):
        pairs = super().informative_pairs()
        btc_pair = "BTC/USDT:USDT"
        if (btc_pair, "1h") not in pairs:
            pairs.append((btc_pair, "1h"))
        return pairs

    def _merge_btc_guard(self, dataframe: DataFrame) -> DataFrame:
        if not self.dp:
            return dataframe

        btc = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe="1h")
        btc = self._add_informative_indicators(btc)
        btc = btc[
            [
                "date",
                "close",
                "ema_50",
                "ema_200",
                "ema_50_slope",
                "rsi",
                "trend_score",
                "roc_4",
                "roc_16",
            ]
        ].copy()
        btc.columns = [
            "date",
            "btc_close_1h",
            "btc_ema_50_1h",
            "btc_ema_200_1h",
            "btc_ema_50_slope_1h",
            "btc_rsi_1h",
            "btc_trend_score_1h",
            "btc_roc_4_1h",
            "btc_roc_16_1h",
        ]
        dataframe = dataframe.merge(btc, on="date", how="left")
        btc_columns = [column for column in dataframe.columns if column.startswith("btc_")]
        dataframe[btc_columns] = dataframe[btc_columns].ffill()
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        dataframe = self._merge_btc_guard(dataframe)
        btc_not_expanding = (
            (dataframe["btc_trend_score_1h"] <= 2)
            & (dataframe["btc_close_1h"] < dataframe["btc_ema_50_1h"] * 1.018)
            & (dataframe["btc_ema_50_slope_1h"] < 0.0025)
            & (dataframe["btc_rsi_1h"] < 62)
            & (dataframe["btc_roc_16_1h"] < 0.050)
        )
        btc_bearish = (
            (dataframe["btc_trend_score_1h"] <= -1)
            | (dataframe["btc_close_1h"] < dataframe["btc_ema_200_1h"])
            | (dataframe["btc_roc_4_1h"] < -0.012)
        )
        dataframe["short_regime"] = dataframe["short_regime"] & btc_not_expanding & btc_bearish
        return dataframe


class Intp20CommunityBrakeShortStrategy(Intp20CommunityBtcGuardShortStrategy):
    """
    BTC-guarded short profile with a hard circuit breaker.

    This is a defensive research variant for the 2024 failure case. It accepts
    lower activity to prevent repeated stoploss clusters from compounding.
    """

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 20,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 720,
                "trade_limit": 1,
                "stop_duration_candles": 1440,
                "only_per_side": True,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 4320,
                "trade_limit": 12,
                "stop_duration_candles": 10080,
                "max_allowed_drawdown": 0.055,
            },
        ]
