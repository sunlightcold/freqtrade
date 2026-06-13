from __future__ import annotations

from datetime import datetime

from Intp20Stage21DualHfNewcoinStrategy import Intp20Stage21DualHfNewcoinStrategy
from pandas import DataFrame


class Intp20Stage23AggressiveGenericPulseStrategy(Intp20Stage21DualHfNewcoinStrategy):
    """
    Stage-23 aggressive high-turnover portfolio guard.

    Stage-21 proved that high trade-count dry-run is possible after 0.05%
    taker fees, but its broad generic long/pull entries were the largest drag.
    This variant keeps the diversified portfolio and generic short momentum,
    while blocking non-pair-specific high-frequency long chasing and loose pull
    entries that are structurally fee-sensitive on 1m futures.
    """

    startup_candle_count = 180
    stoploss = -0.22

    max_stake_multiplier = 2.20
    min_stake_multiplier = 0.28
    max_stage19_leverage = 6.5
    max_stage20_leverage = 6.5
    max_stage21_leverage = 6.5
    max_stage23_leverage = 6.5

    blocked_entry_prefixes = (
        "s20_momo_l_",
        "s21_momo_l_",
        "s21_pull_l_",
        "s21_pull_s_",
    )

    @classmethod
    def _is_blocked_stage23_entry(cls, entry_tag: str | None) -> bool:
        return bool(entry_tag and entry_tag.startswith(cls.blocked_entry_prefixes))

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)
        blocked = dataframe["enter_tag"].fillna("").map(self._is_blocked_stage23_entry)
        if blocked.any():
            dataframe.loc[blocked, ["enter_long", "enter_short"]] = 0
            dataframe.loc[blocked, "enter_tag"] = ""
        return dataframe

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> bool:
        if self._is_blocked_stage23_entry(entry_tag):
            return False
        return super().confirm_trade_entry(
            pair,
            order_type,
            amount,
            rate,
            time_in_force,
            current_time,
            entry_tag,
            side,
            **kwargs,
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
        target = super().leverage(
            pair,
            current_time,
            current_rate,
            proposed_leverage,
            max_leverage,
            entry_tag,
            side,
            **kwargs,
        )
        if entry_tag and entry_tag.startswith("s21_momo_s_"):
            target += 0.20
        return max(1.0, min(target, max_leverage, self.max_stage23_leverage))
