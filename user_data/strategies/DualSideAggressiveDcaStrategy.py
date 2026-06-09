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


class Intp20LongOnlyDcaStrategy(DualSideIntp20DcaStrategy):
    """
    Long-account research slice for Binance subaccount A.
    """

    weak_long_pairs = ()
    weak_short_pairs = (
        "AAVE/",
        "APT/",
        "AVAX/",
        "BCH/",
        "BNB/",
        "BTC/",
        "COMP/",
        "DOGE/",
        "ETC/",
        "ETH/",
        "LINK/",
        "LTC/",
        "MKR/",
        "OP/",
        "SOL/",
        "SUI/",
        "TRX/",
        "XLM/",
        "XRP/",
        "XTZ/",
    )


class Intp20ShortOnlyDcaStrategy(DualSideIntp20DcaStrategy):
    """
    Short-account research slice for Binance subaccount B.
    """

    weak_long_pairs = (
        "AAVE/",
        "APT/",
        "AVAX/",
        "BCH/",
        "BNB/",
        "BTC/",
        "COMP/",
        "DOGE/",
        "ETC/",
        "ETH/",
        "LINK/",
        "LTC/",
        "MKR/",
        "OP/",
        "SOL/",
        "SUI/",
        "TRX/",
        "XLM/",
        "XRP/",
        "XTZ/",
    )
    weak_short_pairs = ()


class Intp20LongCoreDcaStrategy(Intp20LongOnlyDcaStrategy):
    """
    Long-account core pool after first-pass pair attribution.
    """

    weak_long_pairs = (
        "AAVE/",
        "BCH/",
        "BNB/",
        "COMP/",
        "LINK/",
        "TRX/",
        "XRP/",
    )


class Intp20ShortCoreDcaStrategy(Intp20ShortOnlyDcaStrategy):
    """
    Short-account core pool after first-pass pair attribution.
    """

    weak_short_pairs = (
        "AAVE/",
        "AVAX/",
        "BNB/",
        "BTC/",
        "ETC/",
        "ETH/",
        "LTC/",
        "MKR/",
        "OP/",
        "SOL/",
        "XLM/",
    )


class Intp20LongFocusDcaStrategy(Intp20LongCoreDcaStrategy):
    """
    Focused long-account pool after removing weak OP/SUI contribution.
    """

    weak_long_pairs = (
        "AAVE/",
        "BCH/",
        "BNB/",
        "COMP/",
        "LINK/",
        "OP/",
        "SUI/",
        "TRX/",
        "XRP/",
    )


class Intp20ShortFocusDcaStrategy(Intp20ShortCoreDcaStrategy):
    """
    Focused short-account pool keeping only positive first-pass shorts.
    """

    weak_short_pairs = (
        "AAVE/",
        "AVAX/",
        "BNB/",
        "BTC/",
        "COMP/",
        "ETC/",
        "ETH/",
        "LINK/",
        "LTC/",
        "MKR/",
        "OP/",
        "SOL/",
        "SUI/",
        "TRX/",
        "XLM/",
    )


class Intp20LongRobustDcaStrategy(Intp20LongOnlyDcaStrategy):
    """
    Walk-forward robust long pool.

    Pairs must be positive in both the 2023-06..2024-12 training window and the
    2025 validation window before being admitted to this research slice.
    """

    weak_long_pairs = (
        "AAVE/",
        "APT/",
        "BCH/",
        "BNB/",
        "COMP/",
        "LINK/",
        "OP/",
        "SOL/",
        "SUI/",
        "TRX/",
        "XRP/",
        "XTZ/",
    )


class Intp20ShortRobustDcaStrategy(Intp20ShortOnlyDcaStrategy):
    """
    Walk-forward robust short pool.

    This remains a hedge candidate only: validation improved, but the 2026
    holdout was effectively flat.
    """

    weak_short_pairs = (
        "APT/",
        "AVAX/",
        "BNB/",
        "BTC/",
        "ETC/",
        "ETH/",
        "LINK/",
        "LTC/",
        "MKR/",
        "OP/",
        "SOL/",
        "SUI/",
        "XLM/",
        "XRP/",
    )


class Intp20LongMoonshotDcaStrategy(Intp20LongFocusDcaStrategy):
    """
    High-risk long-account research profile for aggressive CAGR exploration.

    This intentionally spends more margin and accepts deeper account swings than
    the robust profile. It is a research candidate, not a default deployment.
    """

    stoploss = -0.20
    max_dca_multiplier = 1.6
    dca_profit_triggers = [-0.024, -0.052, -0.085]
    dca_multipliers = [0.25, 0.25, 0.10]
    dca_label = "long_moonshot_dca"

    minimal_roi = {
        "360": 0.010,
        "120": 0.018,
        "45": 0.030,
        "0": 0.055,
    }

    trailing_stop_positive = 0.018
    trailing_stop_positive_offset = 0.060

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 2,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 96,
                "trade_limit": 5,
                "stop_duration_candles": 24,
                "only_per_side": True,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 384,
                "trade_limit": 30,
                "stop_duration_candles": 48,
                "max_allowed_drawdown": 0.45,
            },
        ]

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
        if pair.startswith(("DOGE/", "APT/", "AVAX/", "SOL/", "XLM/", "XTZ/")):
            target = 8.0
        elif pair.startswith(("LTC/", "ETC/", "MKR/")):
            target = 7.0
        else:
            target = 6.0
        return min(target, max_leverage, 10.0)


class Intp20ShortMoonshotDcaStrategy(Intp20ShortFocusDcaStrategy):
    """
    High-risk short-account research profile for aggressive CAGR exploration.
    """

    stoploss = -0.18
    max_dca_multiplier = 1.8
    dca_profit_triggers = [-0.022, -0.050, -0.080]
    dca_multipliers = [0.30, 0.30, 0.20]
    dca_label = "short_moonshot_dca"

    minimal_roi = {
        "360": 0.008,
        "120": 0.015,
        "45": 0.026,
        "0": 0.050,
    }

    trailing_stop_positive = 0.016
    trailing_stop_positive_offset = 0.055

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 2,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 96,
                "trade_limit": 5,
                "stop_duration_candles": 24,
                "only_per_side": True,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 384,
                "trade_limit": 30,
                "stop_duration_candles": 48,
                "max_allowed_drawdown": 0.45,
            },
        ]

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
        if pair.startswith(("DOGE/", "APT/", "XTZ/")):
            target = 7.0
        elif pair.startswith(("BCH/", "XRP/")):
            target = 6.0
        else:
            target = 5.0
        return min(target, max_leverage, 9.0)


class Intp20LongNextGenDcaStrategy(Intp20LongMoonshotDcaStrategy):
    """
    Next-stage long research profile.

    The first improvement is structural: keep the moonshot mechanics, but trade
    only the seven-pair core that improved validation return and drawdown.
    """

    weak_long_pairs = (
        "AAVE/",
        "APT/",
        "BCH/",
        "BNB/",
        "COMP/",
        "ETC/",
        "ETH/",
        "LINK/",
        "OP/",
        "SUI/",
        "TRX/",
        "XRP/",
        "XTZ/",
    )


class Intp20ShortRiskAdjustedDcaStrategy(Intp20ShortMoonshotDcaStrategy):
    """
    Lower-drawdown short-account profile.

    This removes XTZ from the focused short pool after the next-stage screen
    showed a better profit factor and lower drawdown without it.
    """

    weak_short_pairs = (
        "AAVE/",
        "AVAX/",
        "BNB/",
        "BTC/",
        "COMP/",
        "ETC/",
        "ETH/",
        "LINK/",
        "LTC/",
        "MKR/",
        "OP/",
        "SOL/",
        "SUI/",
        "TRX/",
        "XLM/",
        "XTZ/",
    )


class Intp20LongNextGenWeightedDcaStrategy(Intp20LongNextGenDcaStrategy):
    """
    Capital-weighted next-stage long research profile.

    The signal rules stay identical to NextGen. Only per-pair capital sizing is
    changed so stronger contributors receive more exposure while noisier pairs
    keep their diversification role at lower risk.
    """

    pair_stake_weights = {
        "MKR/": 1.14,
        "AVAX/": 1.10,
        "LTC/": 1.10,
        "DOGE/": 1.02,
        "BTC/": 0.94,
        "XLM/": 0.72,
        "SOL/": 0.70,
    }

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
        stake = super().custom_stake_amount(
            pair,
            current_time,
            current_rate,
            proposed_stake,
            min_stake,
            max_stake,
            leverage,
            entry_tag,
            side,
            **kwargs,
        )
        for prefix, weight in self.pair_stake_weights.items():
            if pair.startswith(prefix):
                stake *= weight
                break
        if min_stake:
            stake = max(stake, min_stake)
        return min(stake, max_stake)
