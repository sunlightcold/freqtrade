from __future__ import annotations

from datetime import datetime

from Intp20Stage23AggressiveGenericPulseStrategy import (
    Intp20Stage23AggressiveGenericPulseStrategy,
)


class Intp20Stage24RobustPulseStrategy(Intp20Stage23AggressiveGenericPulseStrategy):
    """
    Stage-24 robust high-turnover pulse.

    Long-window split backtests from 2023-06 through 2026-06 showed that the
    generic Stage-21 short momentum layer was the main structural drag across
    regimes.  This variant keeps the 93-pair portfolio and pair-specific long/
    short stack, but removes the broad generic learning entries that did not
    survive the extended walk-forward check after 0.05% taker fees.
    """

    max_stage24_leverage = 6.5
    stoploss = -0.12

    order_types = {
        "entry": "limit",
        "exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    blocked_entry_prefixes = Intp20Stage23AggressiveGenericPulseStrategy.blocked_entry_prefixes + (
        "s20_momo_s_",
        "s20_pull_l_",
        "s21_momo_s_",
    )

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool | None:
        if self._is_protected_legacy_tag(trade.enter_tag):
            exit_reason = self._legacy_stage_exit_reason(
                trade,
                current_time,
                current_profit,
                "stage24",
            )
            if exit_reason:
                return exit_reason
        return super().custom_exit(
            pair,
            trade,
            current_time,
            current_rate,
            current_profit,
            **kwargs,
        )
