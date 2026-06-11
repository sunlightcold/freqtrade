from datetime import datetime

from freqtrade.persistence import Trade

from Intp20Stage15HighTurnoverScalpStrategy import Intp20Stage15AggressiveScalpStrategy


class Intp20Stage17AdaptiveScalpStrategy(Intp20Stage15AggressiveScalpStrategy):
    """
    Stage-17 adaptive scalp variant.

    Keeps the Stage-15 high-turnover entry set, drops only the weakest added
    MKR scalp streams, and adds faster loss exits for short reversion tags that
    were responsible for the 2026-05 giveback.
    """

    adaptive_blocked_tags = {
        "s15_06_mkr_vstretch_l_mc_h8m_l5",
        "s15_07_mkr_maoff_s_ma_h5m_l5",
    }
    blocked_tags = Intp20Stage15AggressiveScalpStrategy.blocked_tags | adaptive_blocked_tags

    pair_stake_weights = {
        **Intp20Stage15AggressiveScalpStrategy.pair_stake_weights,
        "AAVE/": 1.32,
        "XRP/": 1.18,
        "OP/": 1.04,
        "DOGE/": 0.86,
        "APT/": 0.70,
        "DOT/": 0.88,
        "XTZ/": 0.78,
        "UNI/": 0.72,
        "LTC/": 0.76,
    }

    tag_stake_weights = {
        **Intp20Stage15AggressiveScalpStrategy.tag_stake_weights,
        "s9_01_aave_panic_l_mc_h24_l4": 1.48,
        "s15_01_aave_vwap_s_lt_h30m_l5": 1.28,
        "s15_04_op_vwap_l_mchop_h30m_l5": 1.18,
        "s15_02_doge_vwap_l_mchop_h30m_l5": 1.10,
        "s15_03_xrp_vwap_l_mhv_h30m_l5": 1.10,
        "s15_05_apt_vwap_l_mc_h20m_l5": 0.96,
        "s13_02_dot_rsi_s_lc_h24_l4": 0.82,
        "s9_08_xtz_rsi_s_lc_h24_l4": 0.76,
        "s13_05_uni_rsi_s_lc_h24_l4": 0.72,
        "s9_16_ltc_vwap_s_lc_h18_l5": 0.72,
    }

    leverage_bonus_tags = set(Intp20Stage15AggressiveScalpStrategy.leverage_bonus_tags) | {
        "s15_04_op_vwap_l_mchop_h30m_l5",
    }
    guarded_short_tags = {
        "s13_02_dot_rsi_s_lc_h24_l4",
        "s9_08_xtz_rsi_s_lc_h24_l4",
        "s13_05_uni_rsi_s_lc_h24_l4",
        "s9_16_ltc_vwap_s_lc_h18_l5",
    }
    max_stake_multiplier = 2.15
    min_stake_multiplier = 0.42
    max_boost_leverage = 7.0

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool | None:
        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        if trade.enter_tag in self.guarded_short_tags and trade_minutes >= 18:
            if current_profit <= -0.035:
                return f"{trade.enter_tag}_adaptive_loss_exit"
        return super().custom_exit(
            pair,
            trade,
            current_time,
            current_rate,
            current_profit,
            **kwargs,
        )


class Intp20Stage17TurboAdaptiveScalpStrategy(Intp20Stage17AdaptiveScalpStrategy):
    """
    Higher-risk Stage-17 variant with extra concentration on strong scalp tags.
    """

    pair_stake_weights = {
        **Intp20Stage17AdaptiveScalpStrategy.pair_stake_weights,
        "AAVE/": 1.42,
        "XRP/": 1.24,
        "OP/": 1.12,
        "DOGE/": 0.92,
        "APT/": 0.78,
    }

    tag_stake_weights = {
        **Intp20Stage17AdaptiveScalpStrategy.tag_stake_weights,
        "s9_01_aave_panic_l_mc_h24_l4": 1.62,
        "s15_01_aave_vwap_s_lt_h30m_l5": 1.42,
        "s15_04_op_vwap_l_mchop_h30m_l5": 1.30,
        "s15_03_xrp_vwap_l_mhv_h30m_l5": 1.20,
        "s15_02_doge_vwap_l_mchop_h30m_l5": 1.18,
        "s15_05_apt_vwap_l_mc_h20m_l5": 1.02,
    }

    max_stake_multiplier = 2.55
    max_boost_leverage = 7.5
