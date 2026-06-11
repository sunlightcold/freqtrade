from datetime import datetime

from Intp20Stage7AggressivePortfolioStrategy import Intp20Stage13Validated20Strategy


class Intp20Stage14CommunityBoostStrategy(Intp20Stage13Validated20Strategy):
    """
    Stage-14 exposure boost for the validated Stage-13 portfolio.

    The signal model is unchanged. This class applies the community playbook
    used by many high-return Freqtrade strategies: keep diversified signal
    streams, cut recurring weak tags, and push more capital into tags that
    survived multiple walk-forward windows.
    """

    blocked_tags = {
        "s10_07_ltc_maoff_l_mc_h3m_l5",
        "s11_05_xtz_vstretch_l_mchop_h8m_l5",
    }

    pair_stake_weights = {
        "AAVE/": 1.16,
        "SOL/": 1.12,
        "ICP/": 1.12,
        "XLM/": 1.10,
        "XRP/": 1.08,
        "ETH/": 1.06,
        "MKR/": 1.04,
        "XTZ/": 1.02,
        "DOT/": 1.00,
        "NEAR/": 0.96,
        "FET/": 0.94,
        "OP/": 0.92,
        "LTC/": 0.90,
        "UNI/": 0.86,
        "SUI/": 0.84,
        "DOGE/": 0.82,
        "APT/": 0.80,
        "COMP/": 0.78,
        "MANA/": 0.72,
    }

    tag_stake_weights = {
        "s9_01_aave_panic_l_mc_h24_l4": 1.26,
        "s9_02_sol_panic_s_mc_h24_l4": 1.20,
        "s13_03_icp_rsi_s_lc_h24_l4": 1.18,
        "s9_11_mkr_micro_l_mchop_h18_l5": 1.16,
        "s9_08_xtz_rsi_s_lc_h24_l4": 1.14,
        "s13_02_dot_rsi_s_lc_h24_l4": 1.12,
        "s9_04_xlm_panic_l_mc_h12_l4": 1.12,
        "s13_01_near_rsi_s_lc_h24_l4": 1.08,
        "s9_10_xrp_rsi_s_mx_h24_l4": 1.08,
        "s13_04_fet_rsi_l_lc_h24_l4": 1.04,
        "s9_15_eth_micro_l_mc_h18_l5": 1.04,
        "s10_02_etc_maoff_l_mchop_h18m_l5": 1.04,
        "s10_01_op_maoff_l_mc_h12m_l5": 0.96,
        "s9_16_ltc_vwap_s_lc_h18_l5": 0.94,
        "s13_05_uni_rsi_s_lc_h24_l4": 0.90,
        "s9_25_sui_vwap_l_lc_h18_l5": 0.88,
        "s13_06_mana_stoch_s_lt_h24_l4": 0.78,
        "s11_06_apt_vstretch_l_mchop_h12m_l5": 0.78,
        "s11_01_apt_vstretch_l_ma_h12m_l5": 0.82,
        "s11_03_etc_vstretch_l_mchop_h12m_l5": 0.82,
        "s10_08_xrp_maoff_l_ma_h12m_l5": 0.70,
    }

    max_stake_multiplier = 1.70
    min_stake_multiplier = 0.55
    leverage_bonus_tags = {
        "s9_01_aave_panic_l_mc_h24_l4",
        "s9_02_sol_panic_s_mc_h24_l4",
        "s13_03_icp_rsi_s_lc_h24_l4",
        "s9_08_xtz_rsi_s_lc_h24_l4",
        "s9_04_xlm_panic_l_mc_h12_l4",
        "s9_10_xrp_rsi_s_mx_h24_l4",
    }
    max_boost_leverage = 6.0

    @classmethod
    def _tag_weight(cls, entry_tag: str | None) -> float:
        if not entry_tag:
            return 1.0
        return cls.tag_stake_weights.get(entry_tag, 1.0)

    @classmethod
    def _pair_weight(cls, pair: str) -> float:
        for prefix, weight in cls.pair_stake_weights.items():
            if pair.startswith(prefix):
                return weight
        return 1.0

    @classmethod
    def _is_blocked_tag(cls, entry_tag: str | None) -> bool:
        return bool(entry_tag and entry_tag in cls.blocked_tags)

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
        if self._is_blocked_tag(entry_tag):
            return False
        return True

    def custom_stake_amount(  # type: ignore[override]
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
    ) -> float | None:
        if self._is_blocked_tag(entry_tag):
            return None

        multiplier = self._pair_weight(pair) * self._tag_weight(entry_tag)
        multiplier = max(self.min_stake_multiplier, min(multiplier, self.max_stake_multiplier))
        stake = proposed_stake * multiplier
        if min_stake:
            stake = max(stake, min_stake)
        return min(stake, max_stake)

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
        if entry_tag in self.leverage_bonus_tags:
            target += 0.75
        if entry_tag and self._tag_weight(entry_tag) < 0.85:
            target -= 0.50
        return max(1.0, min(target, max_leverage, self.max_boost_leverage))


class Intp20Stage14AggressiveBoostStrategy(Intp20Stage14CommunityBoostStrategy):
    """
    Higher-risk Stage-14 variant.

    This keeps the same entries and blocked tags, but allows larger stake and
    leverage concentration on the strongest cross-window tags. Use for research
    and dry-run comparison before considering live capital.
    """

    pair_stake_weights = {
        **Intp20Stage14CommunityBoostStrategy.pair_stake_weights,
        "AAVE/": 1.28,
        "SOL/": 1.22,
        "ICP/": 1.20,
        "XLM/": 1.18,
        "XRP/": 1.14,
        "ETH/": 1.10,
        "UNI/": 0.80,
        "SUI/": 0.78,
        "APT/": 0.74,
        "COMP/": 0.72,
        "MANA/": 0.66,
    }

    tag_stake_weights = {
        **Intp20Stage14CommunityBoostStrategy.tag_stake_weights,
        "s9_01_aave_panic_l_mc_h24_l4": 1.42,
        "s9_02_sol_panic_s_mc_h24_l4": 1.34,
        "s13_03_icp_rsi_s_lc_h24_l4": 1.30,
        "s9_11_mkr_micro_l_mchop_h18_l5": 1.24,
        "s9_08_xtz_rsi_s_lc_h24_l4": 1.22,
        "s13_02_dot_rsi_s_lc_h24_l4": 1.20,
        "s9_04_xlm_panic_l_mc_h12_l4": 1.20,
        "s13_01_near_rsi_s_lc_h24_l4": 1.12,
        "s9_10_xrp_rsi_s_mx_h24_l4": 1.14,
        "s13_05_uni_rsi_s_lc_h24_l4": 0.82,
        "s9_25_sui_vwap_l_lc_h18_l5": 0.78,
        "s13_06_mana_stoch_s_lt_h24_l4": 0.68,
    }

    max_stake_multiplier = 2.10
    min_stake_multiplier = 0.45
    max_boost_leverage = 7.0

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
        if entry_tag in self.leverage_bonus_tags:
            target += 0.75
        return max(1.0, min(target, max_leverage, self.max_boost_leverage))
