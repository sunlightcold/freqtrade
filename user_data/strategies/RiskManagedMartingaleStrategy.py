from datetime import datetime

import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy


class RiskManagedMartingaleStrategy(IStrategy):
    """
    Trend-filtered long/short DCA strategy for isolated futures.

    This is intentionally not an infinite martingale. It caps safety orders,
    reserves capital for them, and refuses to average down during clear trend breaks.
    """

    INTERFACE_VERSION = 3

    timeframe = "1h"
    startup_candle_count = 240
    can_short = True

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    position_adjustment_enable = True
    max_entry_position_adjustment = 3
    max_dca_multiplier = 4.45

    minimal_roi = {
        "720": 0.01,
        "240": 0.02,
        "60": 0.03,
        "0": 0.05,
    }

    stoploss = -0.16
    trailing_stop = True
    trailing_stop_positive = 0.012
    trailing_stop_positive_offset = 0.04
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
                "stop_duration_candles": 3,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 48,
                "trade_limit": 2,
                "stop_duration_candles": 24,
                "only_per_pair": False,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 168,
                "trade_limit": 20,
                "stop_duration_candles": 48,
                "max_allowed_drawdown": 0.18,
            },
        ]

    plot_config = {
        "main_plot": {
            "ema_50": {"color": "orange"},
            "ema_200": {"color": "blue"},
            "bb_lowerband": {"color": "grey"},
            "bb_upperband": {"color": "grey"},
        },
        "subplots": {
            "Momentum": {
                "rsi": {"color": "purple"},
            },
            "Risk": {
                "atr_pct": {"color": "red"},
            },
        },
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["volume_mean_24"] = dataframe["volume"].rolling(24).mean()

        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]
        dataframe["bb_width"] = (
            (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe["bb_middleband"]
        )

        dataframe["trend_ok"] = (
            (dataframe["ema_50"] > dataframe["ema_200"])
            & (dataframe["close"] > dataframe["ema_200"] * 0.97)
        )
        dataframe["short_trend_ok"] = (
            (dataframe["ema_50"] < dataframe["ema_200"])
            & (dataframe["close"] < dataframe["ema_200"] * 1.03)
        )

        dataframe["pullback_ok"] = (
            (dataframe["close"] < dataframe["bb_lowerband"] * 1.015)
            | qtpylib.crossed_above(dataframe["rsi"], 32)
        )
        dataframe["short_rebound_ok"] = (
            (dataframe["close"] > dataframe["bb_upperband"] * 0.985)
            | qtpylib.crossed_below(dataframe["rsi"], 68)
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                dataframe["trend_ok"]
                & dataframe["pullback_ok"]
                & (dataframe["rsi"] > 28)
                & (dataframe["rsi"] < 46)
                & (dataframe["bb_width"] > 0.025)
                & (dataframe["atr_pct"] < 0.08)
                & (dataframe["volume"] > 0)
                & (dataframe["volume"] > dataframe["volume_mean_24"] * 0.6)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "trend_pullback")

        dataframe.loc[
            (
                dataframe["short_trend_ok"]
                & dataframe["short_rebound_ok"]
                & (dataframe["rsi"] > 54)
                & (dataframe["rsi"] < 76)
                & (dataframe["bb_width"] > 0.025)
                & (dataframe["atr_pct"] < 0.08)
                & (dataframe["volume"] > 0)
                & (dataframe["volume"] > dataframe["volume_mean_24"] * 0.6)
            ),
            ["enter_short", "enter_tag"],
        ] = (1, "short_trend_rebound")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (
                    (dataframe["rsi"] > 68)
                    & (dataframe["close"] > dataframe["bb_upperband"])
                )
                | (
                    (dataframe["close"] < dataframe["ema_50"])
                    & (dataframe["rsi"] < 42)
                    & (dataframe["ema_50"] < dataframe["ema_200"])
                )
            )
            & (dataframe["volume"] > 0),
            ["exit_long", "exit_tag"],
        ] = (1, "momentum_or_trend_exit")

        dataframe.loc[
            (
                (
                    (dataframe["rsi"] < 32)
                    & (dataframe["close"] < dataframe["bb_lowerband"])
                )
                | (
                    (dataframe["close"] > dataframe["ema_50"])
                    & (dataframe["rsi"] > 58)
                    & (dataframe["ema_50"] > dataframe["ema_200"])
                )
            )
            & (dataframe["volume"] > 0),
            ["exit_short", "exit_tag"],
        ] = (1, "short_momentum_or_trend_exit")

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

        dca_profit_triggers = [-0.025, -0.05, -0.085]
        dca_multipliers = [1.10, 1.45, 1.90]

        trigger_index = count - 1
        if trigger_index >= len(dca_profit_triggers):
            return None
        if current_profit > dca_profit_triggers[trigger_index]:
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe is None or len(dataframe) < 3:
            return None

        last_candle = dataframe.iloc[-1].squeeze()
        prev_candle = dataframe.iloc[-2].squeeze()

        if trade.is_short:
            trend_broken = (
                (last_candle["close"] > last_candle["ema_200"] * 1.06)
                or (
                    last_candle["ema_50"] > last_candle["ema_200"]
                    and last_candle["close"] > last_candle["ema_200"]
                )
            )
            stabilizing = (
                (last_candle["close"] <= prev_candle["close"] * 1.005)
                or (last_candle["rsi"] < prev_candle["rsi"])
            )
        else:
            trend_broken = (
                (last_candle["close"] < last_candle["ema_200"] * 0.94)
                or (
                    last_candle["ema_50"] < last_candle["ema_200"]
                    and last_candle["close"] < last_candle["ema_200"]
                )
            )
            stabilizing = (
                (last_candle["close"] >= prev_candle["close"] * 0.995)
                or (last_candle["rsi"] > prev_candle["rsi"])
            )
        if trend_broken:
            return None

        if not stabilizing:
            return None

        if last_candle["atr_pct"] > 0.10:
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
        target = 2.0 if pair.startswith(("BTC/", "ETH/")) else 1.5
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
            if current_profit > 0.055 and last_candle["rsi"] < 34:
                return "take_profit_short_rsi"

            if current_profit > 0.03 and last_candle["close"] < last_candle["bb_lowerband"]:
                return "take_profit_short_band"

            if (
                current_profit < -0.12
                and last_candle["close"] > last_candle["ema_200"] * 1.06
                and last_candle["ema_50"] > last_candle["ema_200"]
            ):
                return "short_trend_break_loss"

            return None

        if current_profit > 0.055 and last_candle["rsi"] > 66:
            return "take_profit_long_rsi"

        if current_profit > 0.03 and last_candle["close"] > last_candle["bb_upperband"]:
            return "take_profit_long_band"

        if (
            current_profit < -0.12
            and last_candle["close"] < last_candle["ema_200"] * 0.94
            and last_candle["ema_50"] < last_candle["ema_200"]
        ):
            return "long_trend_break_loss"

        return None
