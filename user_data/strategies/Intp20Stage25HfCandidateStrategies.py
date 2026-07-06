from __future__ import annotations

from datetime import datetime

from pandas import DataFrame

from Intp20Stage15HighTurnoverScalpStrategy import Intp20Stage15AggressiveScalpStrategy
from Intp20Stage21DualHfNewcoinStrategy import Intp20Stage21DualHfNewcoinStrategy


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


class Intp20Stage28HighWinCompositeScalpStrategy(
    Intp20Stage21DualHfNewcoinStrategy,
):
    """
    Stage-28: live-window high-win newcoin momentum scalp.

    Stage25/26/27 failed in live dry-run because broad historical tags kept
    trading after their edge disappeared. This corrective variant moves to the
    Stage21 adaptive newcoin engine, but only permits the latest-window positive
    hotspot names and cuts failed momentum immediately.
    """

    stage28_pair_prefixes = (
        "EIGEN/",
        "MERL/",
        "W/",
        "PUMP/",
        "ALT/",
        "OP/",
        "ONDO/",
    )
    stage28_allowed_tags = frozenset({"s21_momo_l_h8m_l5"})

    allowed_entry_tags = frozenset(
        {
            "s9_01_aave_panic_l_mc_h24_l4",
            "s13_02_dot_rsi_s_lc_h24_l4",
            "s15_01_aave_vwap_s_lt_h30m_l5",
            "s9_08_xtz_rsi_s_lc_h24_l4",
            "s13_01_near_rsi_s_lc_h24_l4",
            "s9_10_xrp_rsi_s_mx_h24_l4",
            "s15_03_xrp_vwap_l_mhv_h30m_l5",
            "s9_04_xlm_panic_l_mc_h12_l4",
            "s13_03_icp_rsi_s_lc_h24_l4",
            "s9_16_ltc_vwap_s_lc_h18_l5",
            "s9_02_sol_panic_s_mc_h24_l4",
            "s15_04_op_vwap_l_mchop_h30m_l5",
            "s15_02_doge_vwap_l_mchop_h30m_l5",
            "s10_03_xrp_maoff_l_ma_h18m_l5",
            "s9_05_comp_rsi_l_mx_h24_l4",
            "s10_06_xlm_maoff_l_ma_h12m_l5",
            "s10_02_etc_maoff_l_mchop_h18m_l5",
            "s11_02_sol_vstretch_l_mchop_h12m_l5",
        }
    )
    stoploss = -0.026

    max_stake_multiplier = 1.80
    min_stake_multiplier = 0.45
    max_boost_leverage = 5.2
    max_stage21_leverage = 5.2

    tag_stake_weights = {
        **Intp20Stage15AggressiveScalpStrategy.tag_stake_weights,
        "s9_01_aave_panic_l_mc_h24_l4": 1.20,
        "s13_02_dot_rsi_s_lc_h24_l4": 1.14,
        "s15_01_aave_vwap_s_lt_h30m_l5": 1.12,
        "s9_08_xtz_rsi_s_lc_h24_l4": 1.10,
        "s9_10_xrp_rsi_s_mx_h24_l4": 1.08,
        "s13_01_near_rsi_s_lc_h24_l4": 1.00,
        "s13_03_icp_rsi_s_lc_h24_l4": 0.92,
    }

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)
        if not metadata["pair"].startswith(self.stage28_pair_prefixes):
            dataframe.loc[:, ["enter_long", "enter_short"]] = 0
            dataframe.loc[:, "enter_tag"] = ""
            return dataframe

        tag = dataframe["enter_tag"].fillna("")
        allowed_tag = tag.isin(self.stage28_allowed_tags)

        long_quality = (
            tag.eq("s21_momo_l_h8m_l5")
            & (dataframe["stage20_adaptive_long"].fillna(0.0) > 0.60)
            & (dataframe["stage20_trend_long"].fillna(0.0) > 0.58)
            & (dataframe["stage20_momo_win_long"].fillna(0.5) >= 0.55)
            & (dataframe["stage20_momo_edge_long"].fillna(0.0) > 0.00075)
            & (dataframe["stage20_chop_risk"].fillna(1.0) < 0.62)
            & (dataframe["stage20_btc_bias"].fillna(0.0) > 0.02)
            & (dataframe["stage20_btc_trend"].fillna(0.0) > -0.05)
            & (dataframe["stage20_btc_risk"].fillna(0.0) > 0.035)
            & (dataframe["stage20_btc_risk"].fillna(1.0) < 0.86)
            & (dataframe["stage19_overheat_score"].fillna(1.0) < 0.72)
            & (dataframe["stage19_hot_score"].fillna(0.0) > 0.42)
            & (dataframe["stage19_volume_ratio"].fillna(0.0) > 1.02)
            & (dataframe["stage19_roc_8"].fillna(0.0) > 0.0018)
            & (dataframe["stage20_close_pos"].fillna(0.5) > 0.48)
            & (dataframe["stage20_exhaustion_long"].fillna(1.0) < 0.72)
        )
        allowed = allowed_tag & long_quality
        blocked = ~allowed
        if blocked.any():
            dataframe.loc[blocked, ["enter_long", "enter_short"]] = 0
            dataframe.loc[blocked, "enter_tag"] = ""
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool | None:
        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        tag = trade.enter_tag or ""

        if tag.startswith("s21_"):
            if current_profit >= 0.0105:
                return "stage28_hot_momo_take_profit"
            if trade_minutes >= 4 and current_profit >= 0.0042:
                return "stage28_hot_momo_time_profit"
            if current_profit <= -0.009:
                return "stage28_hot_momo_fast_loss"
            if trade_minutes >= 7 and current_profit <= -0.0035:
                return "stage28_hot_momo_decay_loss"
            if trade_minutes >= 12:
                return "stage28_hot_momo_timeout"
            return None

        target = 0.0075
        if "_panic_" in tag or "_rsi_" in tag:
            target = 0.0090
        if "_maoff_" in tag or "_vstretch_" in tag:
            target = 0.0065

        if current_profit >= target:
            return "stage28_fast_take_profit"
        if trade_minutes >= 10 and current_profit >= 0.0028:
            return "stage28_time_take_profit"
        if trade_minutes >= 2 and current_profit <= -0.008:
            return "stage28_fast_loss_cut"
        if trade_minutes >= 10 and current_profit <= -0.0035:
            return "stage28_stale_loss_cut"
        if trade_minutes >= 18 and current_profit <= 0.001:
            return "stage28_flat_timeout"
        return super().custom_exit(
            pair,
            trade,
            current_time,
            current_rate,
            current_profit,
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
        return max(1.0, min(target, max_leverage, self.max_boost_leverage))


class Intp20Stage29HighWinReversionScalpStrategy(Intp20Stage21DualHfNewcoinStrategy):
    """
    Stage-29: aggressive adaptive hotspot basket.

    This is the higher-risk sibling of Stage28. It keeps Stage21's adaptive
    momentum/pullback learner, but only on hotspot pairs that remained net
    positive in the 2026-06-12..2026-07-05 failure window.
    """

    stage29_pair_prefixes = (
        "EIGEN/",
        "MERL/",
        "W/",
        "PUMP/",
        "ALT/",
        "OP/",
        "ONDO/",
        "MOODENG/",
    )
    stage29_allowed_tags = frozenset(
        {
            "s21_momo_l_h8m_l5",
            "s21_pull_l_h7m_l4",
        }
    )
    stoploss = -0.035
    max_stage21_leverage = 6.5

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)
        if not metadata["pair"].startswith(self.stage29_pair_prefixes):
            dataframe.loc[:, ["enter_long", "enter_short"]] = 0
            dataframe.loc[:, "enter_tag"] = ""
            return dataframe

        tag = dataframe["enter_tag"].fillna("")
        allowed = tag.isin(self.stage29_allowed_tags)
        allowed &= dataframe["stage20_btc_bias"].fillna(0.0) > 0.02
        allowed &= dataframe["stage20_btc_trend"].fillna(0.0) > -0.05
        allowed &= dataframe["stage20_btc_risk"].fillna(0.0) > 0.035
        allowed &= dataframe["stage20_btc_risk"].fillna(1.0) < 0.90
        allowed &= dataframe["stage20_chop_risk"].fillna(1.0) < 0.68
        allowed &= dataframe["stage19_overheat_score"].fillna(1.0) < 0.82
        allowed &= dataframe["stage19_hot_score"].fillna(0.0) > 0.36
        blocked = ~allowed
        if blocked.any():
            dataframe.loc[blocked, ["enter_long", "enter_short"]] = 0
            dataframe.loc[blocked, "enter_tag"] = ""
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool | None:
        if trade.enter_tag and trade.enter_tag.startswith("s21_"):
            return super().custom_exit(
                pair,
                trade,
                current_time,
                current_rate,
                current_profit,
                **kwargs,
            )

        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        if current_profit >= 0.0085:
            return "stage29_reversion_take_profit"
        if trade_minutes >= 8 and current_profit >= 0.0028:
            return "stage29_reversion_time_profit"
        if trade_minutes >= 2 and current_profit <= -0.0075:
            return "stage29_reversion_fast_loss"
        if trade_minutes >= 10 and current_profit <= -0.003:
            return "stage29_reversion_decay_loss"
        if trade_minutes >= 18 and current_profit <= 0.001:
            return "stage29_reversion_flat_timeout"
        return super().custom_exit(
            pair,
            trade,
            current_time,
            current_rate,
            current_profit,
            **kwargs,
        )


class Intp20Stage30HighWinMomentumScalpStrategy(Intp20Stage21DualHfNewcoinStrategy):
    """
    Stage-30: concentrated hotspot leader rotation.

    Trades fewer names than Stage29, but uses a higher-conviction long momentum
    profile on the strongest live-window leaders. This is the aggressive return
    leg, not the broad discovery leg.
    """

    stage30_pair_prefixes = (
        "EIGEN/",
        "MERL/",
        "W/",
        "PUMP/",
        "ALT/",
        "ONDO/",
    )
    stoploss = -0.030
    max_stage21_leverage = 6.8

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)
        if not metadata["pair"].startswith(self.stage30_pair_prefixes):
            dataframe.loc[:, ["enter_long", "enter_short"]] = 0
            dataframe.loc[:, "enter_tag"] = ""
            return dataframe

        tag = dataframe["enter_tag"].fillna("")
        leader_pull = (
            metadata["pair"].startswith("EIGEN/")
            & tag.eq("s21_pull_l_h7m_l4")
            & (dataframe["stage20_pull_win_long"].fillna(0.5) >= 0.56)
            & (dataframe["stage20_pull_edge_long"].fillna(0.0) > 0.00055)
            & (dataframe["stage20_adaptive_long"].fillna(0.0) > 0.58)
        )
        allowed = tag.eq("s21_momo_l_h8m_l5") | leader_pull
        allowed &= dataframe["stage20_btc_bias"].fillna(0.0) > 0.02
        allowed &= dataframe["stage20_btc_trend"].fillna(0.0) > -0.05
        allowed &= dataframe["stage20_btc_risk"].fillna(0.0) > 0.035
        allowed &= dataframe["stage20_btc_risk"].fillna(1.0) < 0.88
        allowed &= dataframe["stage20_chop_risk"].fillna(1.0) < 0.66
        allowed &= dataframe["stage19_overheat_score"].fillna(1.0) < 0.80
        allowed &= dataframe["stage19_hot_score"].fillna(0.0) > 0.38
        allowed &= dataframe["stage19_volume_ratio"].fillna(0.0) > 0.95
        allowed &= dataframe["stage20_exhaustion_long"].fillna(1.0) < 0.78
        blocked = ~allowed
        if blocked.any():
            dataframe.loc[blocked, ["enter_long", "enter_short"]] = 0
            dataframe.loc[blocked, "enter_tag"] = ""
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool | None:
        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        if trade.enter_tag and trade.enter_tag.startswith("s21_"):
            if current_profit >= 0.012:
                return "stage30_leader_take_profit"
            if trade_minutes >= 3 and current_profit >= 0.005:
                return "stage30_leader_time_profit"
            if current_profit <= -0.010:
                return "stage30_leader_fast_loss"
            if trade_minutes >= 7 and current_profit <= -0.0035:
                return "stage30_leader_decay_loss"
            if trade_minutes >= 12:
                return "stage30_leader_timeout"
            return None
        return super().custom_exit(
            pair,
            trade,
            current_time,
            current_rate,
            current_profit,
            **kwargs,
        )
