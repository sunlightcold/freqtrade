from datetime import datetime

from freqtrade.persistence import Trade

from DualSideTrendDcaStrategy import DualSideTrendDcaStrategy


class DualSideAggressiveDcaStrategy(DualSideTrendDcaStrategy):
    """
    Higher-risk variant of DualSideTrendDcaStrategy.

    This keeps the same 15m/1h signal model but reserves less capital for
    safety orders and uses more leverage. It is meant for aggressive backtests,
    not as the default conservative profile.
    """

    stoploss = -0.075
    max_dca_multiplier = 3.4
    dca_profit_triggers = [-0.016, -0.034, -0.056]
    dca_multipliers = [0.65, 0.80, 0.95]
    dca_label = "aggressive_dca"

    minimal_roi = {
        "240": 0.005,
        "90": 0.009,
        "30": 0.014,
        "0": 0.026,
    }

    trailing_stop_positive = 0.010
    trailing_stop_positive_offset = 0.032

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 3,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 96,
                "trade_limit": 4,
                "stop_duration_candles": 36,
                "only_per_side": True,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 384,
                "trade_limit": 24,
                "stop_duration_candles": 72,
                "max_allowed_drawdown": 0.24,
            },
        ]

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

        trigger_index = count - 1
        if trigger_index >= len(self.dca_profit_triggers):
            return None
        if current_profit > self.dca_profit_triggers[trigger_index]:
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe is None or len(dataframe) < 4:
            return None

        last_candle = dataframe.iloc[-1].squeeze()
        prev_candle = dataframe.iloc[-2].squeeze()

        if trade.is_short:
            trend_broken = (
                last_candle["regime_score_1h"] >= 3
                or last_candle["close_1h"] > last_candle["ema_100_1h"] * 1.055
            )
            stabilizing = (
                (last_candle["close"] <= prev_candle["close"] * 1.005)
                or (last_candle["rsi_fast"] < prev_candle["rsi_fast"])
            )
        else:
            trend_broken = (
                last_candle["regime_score_1h"] <= -3
                or last_candle["close_1h"] < last_candle["ema_100_1h"] * 0.945
            )
            stabilizing = (
                (last_candle["close"] >= prev_candle["close"] * 0.995)
                or (last_candle["rsi_fast"] > prev_candle["rsi_fast"])
            )

        if trend_broken or not stabilizing or last_candle["atr_pct"] > 0.042:
            return None

        filled_entries = trade.select_filled_orders(trade.entry_side)
        if not filled_entries:
            return None

        stake = filled_entries[0].stake_amount_filled * self.dca_multipliers[trigger_index]
        if min_stake:
            stake = max(stake, min_stake)
        stake = min(stake, max_stake)

        if stake <= 0:
            return None

        return stake, f"{self.dca_label}_{count + 1}"

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
        elif pair.startswith(("DOGE/", "APT/", "AVAX/", "OP/")):
            target = 2.5
        else:
            target = 2.7
        return min(target, max_leverage)


class DualSideFilteredWider26DcaStrategy(DualSideAggressiveDcaStrategy):
    """
    Best high-return research profile from the 2023-06 to 2026-05 screen.

    It keeps the proven aggressive exits, uses a 2.6x DCA reserve, disables weak
    pair-side combinations, and gives trades enough stop distance to recover
    from common futures wicks without moving into the failed deep-stop profile.
    """

    stoploss = -0.12
    max_dca_multiplier = 2.6
    dca_profit_triggers = [-0.019, -0.040, -0.063]
    dca_multipliers = [0.45, 0.55, 0.60]
    dca_label = "filtered_wider_26_dca"

    weak_long_pairs = ("ETH/", "OP/", "XRP/")
    weak_short_pairs = ("AVAX/", "OP/", "ETH/", "LTC/", "ETC/", "XTZ/")

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 3,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 96,
                "trade_limit": 4,
                "stop_duration_candles": 36,
                "only_per_side": True,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 384,
                "trade_limit": 24,
                "stop_duration_candles": 72,
                "max_allowed_drawdown": 0.30,
            },
        ]


class DualSideIntp20DcaStrategy(DualSideFilteredWider26DcaStrategy):
    """
    20-pair INTP-style futures research profile.

    The rule set treats pair selection as a falsifiable hypothesis: every pair
    is admitted to the universe, but each side gets filtered by observed
    long/short expectancy tiers instead of assuming symmetry.
    """

    weak_long_pairs = (
        "APT/",
        "BCH/",
        "BNB/",
        "ETH/",
        "LINK/",
        "MKR/",
        "OP/",
        "SOL/",
        "SUI/",
        "TRX/",
        "XLM/",
    )
    weak_short_pairs = (
        "AVAX/",
        "BNB/",
        "BTC/",
        "COMP/",
        "DOGE/",
        "ETC/",
        "LINK/",
        "LTC/",
        "MKR/",
        "OP/",
    )

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
        high_conviction = ("AAVE/", "AVAX/", "DOGE/", "LTC/", "XTZ/")
        tactical = ("APT/", "BCH/", "COMP/", "SOL/", "SUI/", "XLM/", "XRP/")

        if pair.startswith(high_conviction):
            target = 4.0
        elif pair.startswith(tactical):
            target = 3.5
        else:
            target = 3.0

        return min(target, max_leverage, 5.0)
