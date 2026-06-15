from __future__ import annotations

from datetime import datetime

from pandas import DataFrame

from Intp20Stage15HighTurnoverScalpStrategy import Intp20Stage15AggressiveScalpStrategy


class Intp20Stage25RiskExitMixin:
    """
    Shared high-turnover exit layer for the Stage-25/26/27 candidates.

    The inherited Stage-15 engine exits mainly by fixed hold time. That leaves
    too much room for a good 1m scalp to give back profit, so these variants add
    explicit profit locks and fast loss exits before falling back to the parent
    fixed-hold logic.
    """

    scalp_profit_take = 0.080

    @staticmethod
    def _stage25_trade_minutes(trade, current_time: datetime) -> float:
        return (current_time - trade.open_date_utc).total_seconds() / 60

    @classmethod
    def _stage25_tag_family(cls, enter_tag: str | None) -> str:
        tag = enter_tag or ""
        if any(token in tag for token in ("_panic_", "_rsi_", "_stoch_")):
            return "reversion"
        if any(token in tag for token in ("_micro_", "_range_")):
            return "breakout"
        if any(token in tag for token in ("_vwap_", "_maoff_", "_vstretch_")):
            return "vwap"
        return "composite"

    def _stage25_profit_exit(
        self,
        trade,
        current_time: datetime,
        current_profit: float,
    ) -> str | None:
        trade_minutes = self._stage25_trade_minutes(trade, current_time)
        hold_minutes = self._hold_minutes_from_tag(trade.enter_tag)
        profit_lock_minutes = max(8, min(30, hold_minutes * 0.50))
        if trade_minutes >= profit_lock_minutes and current_profit >= self.scalp_profit_take:
            return "stage25_profit_take"
        return None

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool | None:
        exit_reason = self._stage25_profit_exit(trade, current_time, current_profit)
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


class Intp20Stage25CompositeScalpStrategy(
    Intp20Stage25RiskExitMixin,
    Intp20Stage15AggressiveScalpStrategy,
):
    """
    Stage-25 candidate A: composite high-turnover scalp.

    This restores the Stage-15 high-turnover engine that actually reached the
    user's return/trade-count target in long validation windows. It keeps the
    mixed panic, RSI, VWAP, MA-offset, VWAP-stretch, and micro-momentum stack.
    """

    stoploss = -0.28


class Intp20Stage25FilteredFamilyMixin:
    allowed_tag_parts: tuple[str, ...] = ()
    allowed_entry_tags: frozenset[str] = frozenset()
    blocked_entry_tags: frozenset[str] = frozenset()

    @classmethod
    def _is_stage25_allowed_entry(cls, entry_tag: str | None) -> bool:
        if not entry_tag:
            return False
        if entry_tag in cls.blocked_entry_tags:
            return False
        if cls.allowed_entry_tags and entry_tag not in cls.allowed_entry_tags:
            return False
        if not cls.allowed_tag_parts:
            return True
        return any(part in entry_tag for part in cls.allowed_tag_parts)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)
        if "enter_tag" not in dataframe:
            return dataframe
        allowed = dataframe["enter_tag"].fillna("").map(self._is_stage25_allowed_entry)
        blocked = ~allowed
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
        if not self._is_stage25_allowed_entry(entry_tag):
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


class Intp20Stage26ReversionShockStrategy(
    Intp20Stage25FilteredFamilyMixin,
    Intp20Stage25RiskExitMixin,
    Intp20Stage15AggressiveScalpStrategy,
):
    """
    Stage-26 candidate B: mean-reversion and shock snapback only.

    Keeps panic snapback, RSI reversion, and stochastic-turn entries. This is a
    different algorithmic family from Stage25's full composite stack: it trades
    exhaustion and liquidity shock normalization instead of VWAP reclaim or
    micro trend continuation.
    """

    allowed_tag_parts = ("_panic_", "_rsi_", "_stoch_")
    stoploss = -0.22
    scalp_profit_take = 10.0

    max_stake_multiplier = 2.45
    min_stake_multiplier = 0.50
    max_boost_leverage = 7.2

    reversion_bonus_tags = {
        "s9_01_aave_panic_l_mc_h24_l4",
        "s13_02_dot_rsi_s_lc_h24_l4",
        "s13_01_near_rsi_s_lc_h24_l4",
        "s9_04_xlm_panic_l_mc_h12_l4",
        "s9_10_xrp_rsi_s_mx_h24_l4",
        "s9_08_xtz_rsi_s_lc_h24_l4",
        "s13_03_icp_rsi_s_lc_h24_l4",
    }

    tag_stake_weights = {
        **Intp20Stage15AggressiveScalpStrategy.tag_stake_weights,
        "s9_01_aave_panic_l_mc_h24_l4": 1.62,
        "s13_02_dot_rsi_s_lc_h24_l4": 1.42,
        "s13_01_near_rsi_s_lc_h24_l4": 1.24,
        "s9_04_xlm_panic_l_mc_h12_l4": 1.34,
        "s9_10_xrp_rsi_s_mx_h24_l4": 1.34,
        "s9_08_xtz_rsi_s_lc_h24_l4": 1.30,
        "s13_03_icp_rsi_s_lc_h24_l4": 1.16,
        "s13_05_uni_rsi_s_lc_h24_l4": 0.84,
        "s13_04_fet_rsi_l_lc_h24_l4": 0.66,
        "s13_06_mana_stoch_s_lt_h24_l4": 0.54,
    }

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
        if entry_tag in self.reversion_bonus_tags:
            target += 0.35
        return max(1.0, min(target, max_leverage, self.max_boost_leverage))


class Intp20Stage27VwapMomentumStrategy(
    Intp20Stage25FilteredFamilyMixin,
    Intp20Stage25RiskExitMixin,
    Intp20Stage15AggressiveScalpStrategy,
):
    """
    Stage-27 candidate C: VWAP, MA-offset, stretch, and micro-momentum only.

    This is intentionally separated from Stage26. It trades reclaim/continuation
    and short fixed-hold VWAP dislocations rather than panic or RSI exhaustion.
    """

    allowed_tag_parts = ("_vwap_", "_maoff_", "_vstretch_", "_micro_", "_range_")
    stoploss = -0.24

    max_stake_multiplier = 3.25
    min_stake_multiplier = 0.45
    max_boost_leverage = 8.0

    tag_stake_weights = {
        **Intp20Stage15AggressiveScalpStrategy.tag_stake_weights,
        "s15_01_aave_vwap_s_lt_h30m_l5": 1.62,
        "s15_04_op_vwap_l_mchop_h30m_l5": 1.48,
        "s15_02_doge_vwap_l_mchop_h30m_l5": 1.34,
        "s15_03_xrp_vwap_l_mhv_h30m_l5": 1.24,
        "s9_25_sui_vwap_l_lc_h18_l5": 1.08,
        "s9_16_ltc_vwap_s_lc_h18_l5": 1.02,
        "s10_03_xrp_maoff_l_ma_h18m_l5": 1.36,
        "s10_06_xlm_maoff_l_ma_h12m_l5": 1.30,
        "s10_02_etc_maoff_l_mchop_h18m_l5": 1.18,
        "s11_02_sol_vstretch_l_mchop_h12m_l5": 1.12,
        "s11_03_etc_vstretch_l_mchop_h12m_l5": 0.50,
        "s15_05_apt_vwap_l_mc_h20m_l5": 0.40,
    }

    momentum_bonus_tags = {
        "s15_01_aave_vwap_s_lt_h30m_l5",
        "s15_04_op_vwap_l_mchop_h30m_l5",
        "s15_02_doge_vwap_l_mchop_h30m_l5",
        "s10_03_xrp_maoff_l_ma_h18m_l5",
        "s10_06_xlm_maoff_l_ma_h12m_l5",
    }

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
        if entry_tag in self.momentum_bonus_tags:
            target += 0.75
        return max(1.0, min(target, max_leverage, self.max_boost_leverage))


class Intp20Stage27QualityRotationScalpStrategy(
    Intp20Stage25FilteredFamilyMixin,
    Intp20Stage25RiskExitMixin,
    Intp20Stage15AggressiveScalpStrategy,
):
    """
    Stage-27 candidate C: quality-rotation scalp.

    This keeps multiple long/short signal families, but its portfolio
    construction is different from Stage25's full composite and Stage26's
    reversion-only model. It removes the current cross-window drag tags and
    pushes capital toward the higher-quality rotating set.
    """

    allowed_tag_parts = ()
    blocked_entry_tags = frozenset(
        {
            "s11_03_etc_vstretch_l_mchop_h12m_l5",
            "s15_05_apt_vwap_l_mc_h20m_l5",
        }
    )
    stoploss = -0.22

    max_stake_multiplier = 2.55
    min_stake_multiplier = 0.48
    max_boost_leverage = 7.6

    tag_stake_weights = {
        **Intp20Stage15AggressiveScalpStrategy.tag_stake_weights,
        "s9_01_aave_panic_l_mc_h24_l4": 1.38,
        "s13_02_dot_rsi_s_lc_h24_l4": 1.30,
        "s15_01_aave_vwap_s_lt_h30m_l5": 1.24,
        "s9_08_xtz_rsi_s_lc_h24_l4": 1.22,
        "s13_01_near_rsi_s_lc_h24_l4": 1.10,
        "s9_10_xrp_rsi_s_mx_h24_l4": 1.16,
        "s15_03_xrp_vwap_l_mhv_h30m_l5": 1.12,
        "s13_04_fet_rsi_l_lc_h24_l4": 0.96,
        "s13_03_icp_rsi_s_lc_h24_l4": 0.94,
        "s13_06_mana_stoch_s_lt_h24_l4": 0.74,
    }

    rotation_bonus_tags = {
        "s9_01_aave_panic_l_mc_h24_l4",
        "s13_02_dot_rsi_s_lc_h24_l4",
        "s15_01_aave_vwap_s_lt_h30m_l5",
        "s9_08_xtz_rsi_s_lc_h24_l4",
        "s9_10_xrp_rsi_s_mx_h24_l4",
    }

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
        if entry_tag in self.rotation_bonus_tags:
            target += 0.45
        return max(1.0, min(target, max_leverage, self.max_boost_leverage))
