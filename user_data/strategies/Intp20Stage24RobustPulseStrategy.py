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

    protected_legacy_prefixes = (
        "s7_",
        "s8_",
        "s9_",
        "s10_",
        "s11_",
        "s12_",
        "s13_",
        "s14_",
        "s15_",
    )

    @classmethod
    def _is_stage24_legacy_tag(cls, entry_tag: str | None) -> bool:
        if not entry_tag:
            return False
        if entry_tag.startswith(("s19_", "s20_", "s21_", "s22_")):
            return False
        return entry_tag.startswith(cls.protected_legacy_prefixes) or "_h" in entry_tag

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool | None:
        if self._is_stage24_legacy_tag(trade.enter_tag):
            trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
            if current_profit >= 0.035:
                return "stage24_legacy_fast_profit_exit"
            if trade_minutes >= 8 and current_profit >= 0.020:
                return "stage24_legacy_take_profit_exit"
            if trade_minutes >= 20 and current_profit >= 0.008:
                return "stage24_legacy_time_profit_exit"
            if trade_minutes >= 3 and current_profit <= -0.055:
                return "stage24_legacy_fast_loss_exit"
            if trade_minutes >= 10 and current_profit <= -0.035:
                return "stage24_legacy_adverse_loss_exit"
            if trade_minutes >= 45:
                return "stage24_legacy_max_hold_exit"
        return super().custom_exit(
            pair,
            trade,
            current_time,
            current_rate,
            current_profit,
            **kwargs,
        )
