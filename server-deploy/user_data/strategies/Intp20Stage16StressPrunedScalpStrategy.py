from datetime import datetime

from Intp20Stage15HighTurnoverScalpStrategy import Intp20Stage15AggressiveScalpStrategy


class Intp20Stage16StressPrunedScalpStrategy(Intp20Stage15AggressiveScalpStrategy):
    """
    Stage-16 cost-stressed pruning pass for the Stage-15 1m scalp stack.

    The rule engine is unchanged. This class blocks tags that failed a 0.10%
    one-side fee stress test across 2024, 2025, and 2026 YTD, then concentrates
    stake and leverage on tags that kept positive net contribution after costs.
    """

    cost_drag_blocked_tags = {
        "s10_01_op_maoff_l_mc_h12m_l5",
        "s10_04_doge_maoff_l_ma_h12m_l5",
        "s10_08_xrp_maoff_l_ma_h12m_l5",
        "s11_01_apt_vstretch_l_ma_h12m_l5",
        "s11_04_doge_vstretch_s_mchop_h12m_l5",
        "s11_06_apt_vstretch_l_mchop_h12m_l5",
        "s11_07_apt_vstretch_l_ma_h12m_l5",
        "s13_04_fet_rsi_l_lc_h24_l4",
        "s13_06_mana_stoch_s_lt_h24_l4",
        "s15_05_apt_vwap_l_mc_h20m_l5",
        "s15_06_mkr_vstretch_l_mc_h8m_l5",
        "s15_07_mkr_maoff_s_ma_h5m_l5",
        "s9_16_ltc_vwap_s_lc_h18_l5",
    }

    blocked_tags = Intp20Stage15AggressiveScalpStrategy.blocked_tags | cost_drag_blocked_tags

    pair_stake_weights = {
        **Intp20Stage15AggressiveScalpStrategy.pair_stake_weights,
        "AAVE/": 1.36,
        "DOT/": 1.18,
        "XRP/": 1.18,
        "XTZ/": 1.12,
        "OP/": 1.08,
        "DOGE/": 0.90,
        "SOL/": 1.10,
        "ICP/": 1.08,
        "XLM/": 1.02,
        "SUI/": 0.72,
        "UNI/": 0.74,
        "APT/": 0.54,
        "LTC/": 0.58,
        "FET/": 0.52,
        "MANA/": 0.48,
    }

    tag_stake_weights = {
        **Intp20Stage15AggressiveScalpStrategy.tag_stake_weights,
        "s9_01_aave_panic_l_mc_h24_l4": 1.54,
        "s15_01_aave_vwap_s_lt_h30m_l5": 1.34,
        "s13_02_dot_rsi_s_lc_h24_l4": 1.34,
        "s9_08_xtz_rsi_s_lc_h24_l4": 1.30,
        "s9_10_xrp_rsi_s_mx_h24_l4": 1.26,
        "s15_04_op_vwap_l_mchop_h30m_l5": 1.24,
        "s15_02_doge_vwap_l_mchop_h30m_l5": 1.12,
        "s15_03_xrp_vwap_l_mhv_h30m_l5": 1.04,
        "s13_03_icp_rsi_s_lc_h24_l4": 1.12,
        "s9_02_sol_panic_s_mc_h24_l4": 1.10,
        "s9_04_xlm_panic_l_mc_h12_l4": 1.04,
        "s13_05_uni_rsi_s_lc_h24_l4": 0.68,
        "s9_25_sui_vwap_l_lc_h18_l5": 0.66,
    }

    leverage_bonus_tags = {
        "s9_01_aave_panic_l_mc_h24_l4",
        "s15_01_aave_vwap_s_lt_h30m_l5",
        "s13_02_dot_rsi_s_lc_h24_l4",
        "s9_08_xtz_rsi_s_lc_h24_l4",
        "s9_10_xrp_rsi_s_mx_h24_l4",
        "s15_04_op_vwap_l_mchop_h30m_l5",
    }
    max_stake_multiplier = 2.35
    min_stake_multiplier = 0.42
    max_boost_leverage = 7.0


class Intp20Stage16TurboPrunedScalpStrategy(Intp20Stage16StressPrunedScalpStrategy):
    """
    Higher-risk Stage-16 variant.

    Keeps the same cost-pruned entry set, but pushes more stake and a small
    extra leverage step into the strongest stress-surviving tags.
    """

    pair_stake_weights = {
        **Intp20Stage16StressPrunedScalpStrategy.pair_stake_weights,
        "AAVE/": 1.48,
        "DOT/": 1.28,
        "XRP/": 1.26,
        "XTZ/": 1.20,
        "OP/": 1.16,
        "SOL/": 1.08,
        "ICP/": 1.06,
        "XLM/": 1.00,
    }

    tag_stake_weights = {
        **Intp20Stage16StressPrunedScalpStrategy.tag_stake_weights,
        "s9_01_aave_panic_l_mc_h24_l4": 1.72,
        "s15_01_aave_vwap_s_lt_h30m_l5": 1.48,
        "s13_02_dot_rsi_s_lc_h24_l4": 1.48,
        "s9_08_xtz_rsi_s_lc_h24_l4": 1.42,
        "s9_10_xrp_rsi_s_mx_h24_l4": 1.38,
        "s15_04_op_vwap_l_mchop_h30m_l5": 1.34,
        "s15_02_doge_vwap_l_mchop_h30m_l5": 1.18,
        "s15_03_xrp_vwap_l_mhv_h30m_l5": 1.08,
    }

    turbo_leverage_tags = {
        "s9_01_aave_panic_l_mc_h24_l4",
        "s15_01_aave_vwap_s_lt_h30m_l5",
        "s13_02_dot_rsi_s_lc_h24_l4",
        "s9_08_xtz_rsi_s_lc_h24_l4",
        "s9_10_xrp_rsi_s_mx_h24_l4",
        "s15_04_op_vwap_l_mchop_h30m_l5",
    }
    max_stake_multiplier = 2.80
    max_boost_leverage = 8.0

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
        if entry_tag in self.turbo_leverage_tags:
            target += 0.50
        return max(1.0, min(target, max_leverage, self.max_boost_leverage))
