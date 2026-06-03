from datetime import datetime

import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair


class DualSideTrendDcaStrategy(IStrategy):
    """
    Dual-side futures strategy using 1h regime filters and 15m entries.

    The strategy deliberately keeps DCA finite. It uses the downloaded 1m candles
    as backtest detail data instead of treating 1m noise as the primary signal.
    """

    INTERFACE_VERSION = 3

    timeframe = "15m"
    startup_candle_count = 320
    can_short = True

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = True
    ignore_roi_if_entry_signal = False

    position_adjustment_enable = True
    max_entry_position_adjustment = 3
    max_dca_multiplier = 4.6

    minimal_roi = {
        "240": 0.004,
        "90": 0.007,
        "30": 0.011,
        "0": 0.022,
    }

    stoploss = -0.055
    trailing_stop = True
    trailing_stop_positive = 0.008
    trailing_stop_positive_offset = 0.026
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
                "stop_duration_candles": 4,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 96,
                "trade_limit": 3,
                "stop_duration_candles": 48,
                "only_per_side": True,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 384,
                "trade_limit": 24,
                "stop_duration_candles": 96,
                "max_allowed_drawdown": 0.16,
            },
        ]

    plot_config = {
        "main_plot": {
            "ema_8": {"color": "yellow"},
            "ema_21": {"color": "orange"},
            "ema_55": {"color": "blue"},
            "bb_lowerband": {"color": "grey"},
            "bb_upperband": {"color": "grey"},
        },
        "subplots": {
            "Momentum": {
                "rsi": {"color": "purple"},
                "adx": {"color": "green"},
            },
            "Risk": {
                "atr_pct": {"color": "red"},
                "regime_score_1h": {"color": "blue"},
            },
        },
    }

    def informative_pairs(self):
        if not self.dp:
            return []
        return [(pair, "1h") for pair in self.dp.current_whitelist()]

    @staticmethod
    def _add_main_indicators(dataframe: DataFrame) -> DataFrame:
        dataframe["ema_8"] = ta.EMA(dataframe, timeperiod=8)
        dataframe["ema_21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema_55"] = ta.EMA(dataframe, timeperiod=55)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_fast"] = ta.RSI(dataframe, timeperiod=6)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["volume_mean_48"] = dataframe["volume"].rolling(48).mean()
        dataframe["ema_8_slope"] = dataframe["ema_8"] / dataframe["ema_8"].shift(6) - 1
        dataframe["ema_21_slope"] = dataframe["ema_21"] / dataframe["ema_21"].shift(12) - 1

        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]
        dataframe["bb_width"] = (
            (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe["bb_middleband"]
        )

        dataframe["near_ema_long"] = (
            (dataframe["low"] < dataframe["ema_21"] * 1.006)
            & (dataframe["close"] > dataframe["ema_21"] * 0.994)
        )
        dataframe["near_ema_short"] = (
            (dataframe["high"] > dataframe["ema_21"] * 0.994)
            & (dataframe["close"] < dataframe["ema_21"] * 1.006)
        )

        dataframe["long_trigger"] = (
            qtpylib.crossed_above(dataframe["rsi_fast"], 38)
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["close"] > dataframe["ema_8"])
        )
        dataframe["short_trigger"] = (
            qtpylib.crossed_below(dataframe["rsi_fast"], 62)
            & (dataframe["close"] < dataframe["open"])
            & (dataframe["close"] < dataframe["ema_8"])
        )

        return dataframe

    @staticmethod
    def _add_informative_indicators(informative: DataFrame) -> DataFrame:
        informative["ema_50"] = ta.EMA(informative, timeperiod=50)
        informative["ema_100"] = ta.EMA(informative, timeperiod=100)
        informative["ema_200"] = ta.EMA(informative, timeperiod=200)
        informative["rsi"] = ta.RSI(informative, timeperiod=14)
        informative["adx"] = ta.ADX(informative, timeperiod=14)
        informative["plus_di"] = ta.PLUS_DI(informative, timeperiod=14)
        informative["minus_di"] = ta.MINUS_DI(informative, timeperiod=14)
        informative["atr"] = ta.ATR(informative, timeperiod=14)
        informative["atr_pct"] = informative["atr"] / informative["close"]
        informative["volume_mean_24"] = informative["volume"].rolling(24).mean()
        informative["ema_50_slope"] = informative["ema_50"] / informative["ema_50"].shift(12) - 1
        informative["ema_200_slope"] = informative["ema_200"] / informative["ema_200"].shift(24) - 1
        informative["roc_6"] = informative["close"] / informative["close"].shift(6) - 1
        informative["roc_24"] = informative["close"] / informative["close"].shift(24) - 1
        informative["roc_72"] = informative["close"] / informative["close"].shift(72) - 1
        informative["regime_score"] = 0
        informative.loc[informative["close"] > informative["ema_50"], "regime_score"] += 1
        informative.loc[informative["ema_50"] > informative["ema_100"], "regime_score"] += 1
        informative.loc[informative["ema_100"] > informative["ema_200"], "regime_score"] += 1
        informative.loc[informative["ema_50_slope"] > 0, "regime_score"] += 1
        informative.loc[informative["plus_di"] > informative["minus_di"], "regime_score"] += 1
        informative.loc[informative["close"] < informative["ema_50"], "regime_score"] -= 1
        informative.loc[informative["ema_50"] < informative["ema_100"], "regime_score"] -= 1
        informative.loc[informative["ema_100"] < informative["ema_200"], "regime_score"] -= 1
        informative.loc[informative["ema_50_slope"] < 0, "regime_score"] -= 1
        informative.loc[informative["minus_di"] > informative["plus_di"], "regime_score"] -= 1
        return informative

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self._add_main_indicators(dataframe)

        if self.dp:
            informative = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe="1h")
            informative = self._add_informative_indicators(informative)
            dataframe = merge_informative_pair(
                dataframe,
                informative,
                self.timeframe,
                "1h",
                ffill=True,
            )

        pair = metadata["pair"]
        high_beta = pair.startswith(("SOL/", "AVAX/", "MKR/", "BCH/"))
        atr_ceiling = 0.055 if high_beta else 0.042
        dataframe["risk_ok"] = (
            (dataframe["atr_pct"] > 0.0025)
            & (dataframe["atr_pct"] < 0.028)
            & (dataframe["atr_pct_1h"] > 0.005)
            & (dataframe["atr_pct_1h"] < atr_ceiling)
            & (dataframe["bb_width"] > 0.012)
            & (dataframe["volume"] > dataframe["volume_mean_48"] * 0.60)
            & (dataframe["volume_1h"] > dataframe["volume_mean_24_1h"] * 0.65)
        )

        dataframe["long_regime"] = (
            (dataframe["regime_score_1h"] >= 4)
            & (dataframe["close_1h"] > dataframe["ema_50_1h"] * 0.995)
            & (dataframe["ema_50_slope_1h"] > -0.001)
            & (dataframe["roc_6_1h"] > -0.018)
            & (dataframe["roc_24_1h"] > -0.035)
            & (dataframe["roc_72_1h"] > -0.07)
            & (dataframe["rsi_1h"] > 46)
            & (dataframe["adx_1h"] > 15)
        )
        dataframe["short_regime"] = (
            (dataframe["regime_score_1h"] <= -4)
            & (dataframe["close_1h"] < dataframe["ema_100_1h"] * 0.995)
            & (dataframe["ema_50_slope_1h"] < -0.001)
            & (dataframe["roc_24_1h"] < 0.025)
            & (dataframe["roc_72_1h"] < 0.035)
            & (dataframe["adx_1h"] > 17)
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                dataframe["long_regime"]
                & dataframe["risk_ok"]
                & (dataframe["ema_8"] > dataframe["ema_21"] * 1.0005)
                & (dataframe["ema_21_slope"] > -0.0015)
                & (dataframe["close"] > dataframe["ema_55"] * 0.996)
                & dataframe["near_ema_long"]
                & dataframe["long_trigger"]
                & (dataframe["rsi"] > 41)
                & (dataframe["rsi"] < 60)
                & (dataframe["plus_di"] >= dataframe["minus_di"] * 0.82)
                & (dataframe["volume"] > 0)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "trend_pullback_long")

        dataframe.loc[
            (
                dataframe["short_regime"]
                & dataframe["risk_ok"]
                & (dataframe["ema_8"] < dataframe["ema_21"] * 0.9995)
                & (dataframe["ema_21_slope"] < 0.0015)
                & (dataframe["close"] < dataframe["ema_55"] * 1.004)
                & dataframe["near_ema_short"]
                & dataframe["short_trigger"]
                & (dataframe["rsi"] > 40)
                & (dataframe["rsi"] < 59)
                & (dataframe["minus_di"] >= dataframe["plus_di"] * 0.82)
                & (dataframe["volume"] > 0)
            ),
            ["enter_short", "enter_tag"],
        ] = (1, "trend_rebound_short")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (
                    (dataframe["rsi"] > 70)
                    & (dataframe["close"] > dataframe["bb_upperband"])
                )
            )
            & (dataframe["volume"] > 0),
            ["exit_long", "exit_tag"],
        ] = (1, "long_exhaustion_or_break")

        dataframe.loc[
            (
                (
                    (dataframe["rsi"] < 30)
                    & (dataframe["close"] < dataframe["bb_lowerband"])
                )
            )
            & (dataframe["volume"] > 0),
            ["exit_short", "exit_tag"],
        ] = (1, "short_exhaustion_or_break")

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
        if trade.has_open_orders:
            return None

        count = trade.nr_of_successful_entries
        if count > self.max_entry_position_adjustment:
            return None

        dca_profit_triggers = [-0.012, -0.026, -0.041]
        dca_multipliers = [0.85, 1.05, 1.30]

        trigger_index = count - 1
        if trigger_index >= len(dca_profit_triggers):
            return None
        if current_profit > dca_profit_triggers[trigger_index]:
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe is None or len(dataframe) < 4:
            return None

        last_candle = dataframe.iloc[-1].squeeze()
        prev_candle = dataframe.iloc[-2].squeeze()

        if trade.is_short:
            trend_broken = (
                last_candle["regime_score_1h"] >= 2
                or last_candle["close_1h"] > last_candle["ema_100_1h"] * 1.045
            )
            stabilizing = (
                (last_candle["close"] <= prev_candle["close"] * 1.004)
                or (last_candle["rsi_fast"] < prev_candle["rsi_fast"])
            )
        else:
            trend_broken = (
                last_candle["regime_score_1h"] <= -2
                or last_candle["close_1h"] < last_candle["ema_100_1h"] * 0.955
            )
            stabilizing = (
                (last_candle["close"] >= prev_candle["close"] * 0.996)
                or (last_candle["rsi_fast"] > prev_candle["rsi_fast"])
            )

        if trend_broken or not stabilizing or last_candle["atr_pct"] > 0.035:
            return None

        filled_entries = trade.select_filled_orders(trade.entry_side)
        if not filled_entries:
            return None

        base_stake = filled_entries[0].stake_amount_filled
        stake = base_stake * dca_multipliers[trigger_index]
        if min_stake:
            stake = max(stake, min_stake)
        stake = min(stake, max_stake)

        if stake <= 0:
            return None

        return stake, f"dca_{count + 1}"

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
            target = 2.0
        elif pair.startswith(("MKR/", "SOL/", "AVAX/", "BCH/")):
            target = 1.6
        else:
            target = 1.8
        return min(target, max_leverage)

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
            if current_profit > 0.045 and last_candle["rsi"] < 33:
                return "take_profit_short_rsi"

            if current_profit > 0.024 and last_candle["close"] < last_candle["bb_lowerband"]:
                return "take_profit_short_band"

            if (
                current_profit > 0.012
                and last_candle["close"] > last_candle["ema_21"]
                and last_candle["rsi_fast"] > 58
            ):
                return "protect_short_profit"

            if current_profit < -0.047 and last_candle["regime_score_1h"] >= 3:
                return "short_regime_flip_loss"

            return None

        if current_profit > 0.045 and last_candle["rsi"] > 67:
            return "take_profit_long_rsi"

        if current_profit > 0.024 and last_candle["close"] > last_candle["bb_upperband"]:
            return "take_profit_long_band"

        if (
            current_profit > 0.012
            and last_candle["close"] < last_candle["ema_21"]
            and last_candle["rsi_fast"] < 42
        ):
            return "protect_long_profit"

        if current_profit < -0.047 and last_candle["regime_score_1h"] <= -3:
            return "long_regime_flip_loss"

        return None
