from pandas import DataFrame

from Intp20Stage14CommunityBoostStrategy import Intp20Stage14AggressiveBoostStrategy
from Intp20Stage7AggressivePortfolioStrategy import (
    Intp20Stage9AggressiveBlendStrategy,
    Intp20Stage10MaOffsetHybridStrategy,
    Intp20Stage11VwapStretchHybridStrategy,
)


class Intp20Stage15HighTurnoverScalpStrategy(Intp20Stage14AggressiveBoostStrategy):
    """
    Stage-15 high-turnover overlay for the validated 20-pair futures basket.

    This keeps the Stage-14 aggressive signal engine and adds short 1m scalp
    streams mined from community-style ideas: VWAP reclaim, VWAP stretch
    reversion, and MA-offset reversion. The new streams are only used when the
    existing Stage-14 stack has no entry on that candle.
    """

    stage15_rules = [
        (
            "AAVE",
            "vwap_reclaim",
            "short",
            "local_trend",
            30,
            5.0,
            {
                "atr_ceiling": 0.018,
                "atr_floor": 0.0025,
                "macro_pullback": 0.045,
                "range_mult": 0.8,
                "rsi_reset": 38,
                "volume_mult": 1.0,
                "vwap_pad": 0.0008,
            },
        ),
        (
            "DOGE",
            "vwap_reclaim",
            "long",
            "market_chop",
            30,
            5.0,
            {
                "atr_ceiling": 0.018,
                "atr_floor": 0.0015,
                "macro_pullback": 0.045,
                "range_mult": 0.8,
                "rsi_reset": 38,
                "volume_mult": 1.0,
                "vwap_pad": 0.0008,
            },
        ),
        (
            "XRP",
            "vwap_reclaim",
            "long",
            "market_high_vol",
            30,
            5.0,
            {
                "atr_ceiling": 0.018,
                "atr_floor": 0.0025,
                "macro_pullback": 0.045,
                "range_mult": 0.8,
                "rsi_reset": 38,
                "volume_mult": 1.0,
                "vwap_pad": 0.0008,
            },
        ),
        (
            "OP",
            "vwap_reclaim",
            "long",
            "market_chop",
            30,
            5.0,
            {
                "atr_ceiling": 0.018,
                "atr_floor": 0.0025,
                "macro_pullback": 0.045,
                "range_mult": 0.8,
                "rsi_reset": 38,
                "volume_mult": 1.0,
                "vwap_pad": 0.0008,
            },
        ),
    ]

    _stage15_tag_weights = {
        "s15_01_aave_vwap_s_lt_h30m_l5": 1.16,
        "s15_02_doge_vwap_l_mchop_h30m_l5": 1.08,
        "s15_03_xrp_vwap_l_mhv_h30m_l5": 1.10,
        "s15_04_op_vwap_l_mchop_h30m_l5": 1.06,
    }
    tag_stake_weights = {
        **Intp20Stage14AggressiveBoostStrategy.tag_stake_weights,
        **_stage15_tag_weights,
    }
    leverage_bonus_tags = set(Intp20Stage14AggressiveBoostStrategy.leverage_bonus_tags) | {
        "s15_01_aave_vwap_s_lt_h30m_l5",
        "s15_03_xrp_vwap_l_mhv_h30m_l5",
    }

    @staticmethod
    def _stage15_tag(
        index: int,
        base: str,
        template: str,
        side: str,
        regime: str,
        hold: int,
        leverage: float,
    ) -> str:
        template_alias = {
            "vwap_reclaim": "vwap",
            "vwap_stretch_reversion": "vstretch",
            "ma_offset_reversion": "maoff",
        }[template]
        regime_alias = {
            "local_trend": "lt",
            "local_chop": "lc",
            "market_aligned": "ma",
            "market_contra": "mc",
            "market_chop": "mchop",
            "market_high_vol": "mhv",
        }[regime]
        return f"s15_{index:02d}_{base.lower()}_{template_alias}_{side[0]}_{regime_alias}_h{hold}m_l{int(leverage)}"

    @staticmethod
    def _signal_for_stage15_rule(dataframe: DataFrame, template: str, side: str, params: dict) -> DataFrame:
        if template == "vwap_reclaim":
            return Intp20Stage9AggressiveBlendStrategy._vwap_reclaim(dataframe, side, params)
        if template == "vwap_stretch_reversion":
            return Intp20Stage11VwapStretchHybridStrategy._vwap_stretch_reversion(
                dataframe,
                side,
                params,
            )
        if template == "ma_offset_reversion":
            return Intp20Stage10MaOffsetHybridStrategy._ma_offset_reversion(dataframe, side, params)
        raise ValueError(f"Unsupported Stage-15 template: {template}")

    @classmethod
    def _build_stage15_signals(cls, dataframe: DataFrame, pair: str) -> DataFrame:
        dataframe = dataframe.copy()
        dataframe["stage15_enter_long"] = False
        dataframe["stage15_enter_short"] = False
        dataframe["stage15_enter_tag"] = None
        base = pair.split("/")[0]

        for index, (rule_base, template, side, regime, hold, leverage, params) in enumerate(
            cls.stage15_rules,
            start=1,
        ):
            if base != rule_base:
                continue
            mask = cls._signal_for_stage15_rule(dataframe, template, side, params)
            mask &= Intp20Stage9AggressiveBlendStrategy._regime_filter(dataframe, regime, side)
            mask &= dataframe["stage15_enter_tag"].isna()
            tag = cls._stage15_tag(index, base, template, side, regime, hold, leverage)
            if side == "long":
                dataframe.loc[mask, ["stage15_enter_long", "stage15_enter_tag"]] = (True, tag)
            else:
                dataframe.loc[mask, ["stage15_enter_short", "stage15_enter_tag"]] = (True, tag)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        pair = metadata["pair"]

        pair_1m = self._add_5m_indicators(dataframe)
        btc_1m = self._btc_1m_regime()
        if not btc_1m.empty:
            pair_1m = pair_1m.merge(btc_1m, on="date", how="left")
            btc_columns = [column for column in pair_1m.columns if column.startswith("btc_")]
            pair_1m[btc_columns] = pair_1m[btc_columns].ffill().fillna(False)
        else:
            for column in (
                "btc_market_bull",
                "btc_market_bear",
                "btc_market_high_vol",
                "btc_market_chop",
                "btc_market_panic_down",
                "btc_market_euphoria_up",
            ):
                pair_1m[column] = False

        signals = self._build_stage15_signals(pair_1m, pair)[
            ["date", "stage15_enter_long", "stage15_enter_short", "stage15_enter_tag"]
        ]
        dataframe = dataframe.merge(signals, on="date", how="left")
        dataframe["stage15_enter_long"] = dataframe["stage15_enter_long"].fillna(False)
        dataframe["stage15_enter_short"] = dataframe["stage15_enter_short"].fillna(False)

        free_slot = ~dataframe["stage7_enter_long"] & ~dataframe["stage7_enter_short"]
        long_mask = free_slot & dataframe["stage15_enter_long"]
        dataframe.loc[long_mask, "stage7_enter_long"] = True
        dataframe.loc[long_mask, "stage7_enter_tag"] = dataframe.loc[
            long_mask,
            "stage15_enter_tag",
        ]
        short_mask = free_slot & dataframe["stage15_enter_short"]
        dataframe.loc[short_mask, "stage7_enter_short"] = True
        dataframe.loc[short_mask, "stage7_enter_tag"] = dataframe.loc[
            short_mask,
            "stage15_enter_tag",
        ]
        return dataframe


class Intp20Stage15AggressiveScalpStrategy(Intp20Stage15HighTurnoverScalpStrategy):
    """
    Higher-risk Stage-15 variant.

    Adds the highest-turnover candidates from the coarse 1m scans. These rules
    improve short-window activity, but they carry visibly larger path risk than
    the base Stage-15 overlay.
    """

    stage15_rules = [
        *Intp20Stage15HighTurnoverScalpStrategy.stage15_rules,
        (
            "APT",
            "vwap_reclaim",
            "long",
            "market_contra",
            20,
            5.0,
            {
                "atr_ceiling": 0.018,
                "atr_floor": 0.0015,
                "macro_pullback": 0.045,
                "range_mult": 0.8,
                "rsi_reset": 38,
                "volume_mult": 1.0,
                "vwap_pad": 0.0008,
            },
        ),
        (
            "MKR",
            "vwap_stretch_reversion",
            "long",
            "market_contra",
            8,
            5.0,
            {
                "atr_ceiling": 0.018,
                "atr_floor": 0.0012,
                "bb_width": 0.0025,
                "close_pos": 0.35,
                "macro_limit": 0.055,
                "min_dist": 0.0035,
                "rsi_2": 10,
                "volume_mult": 0.7,
                "z_entry": 2.4,
            },
        ),
        (
            "MKR",
            "ma_offset_reversion",
            "short",
            "market_aligned",
            5,
            5.0,
            {
                "atr_ceiling": 0.018,
                "atr_floor": 0.0012,
                "bb_width": 0.0025,
                "ema20_offset": 0.0020,
                "ema50_guard": 0.020,
                "macro_limit": 0.055,
                "range_mult": 0.60,
                "rsi_2": 10,
                "slope_guard": 0.0030,
                "volume_mult": 0.7,
            },
        ),
    ]

    _stage15_aggressive_tag_weights = {
        **Intp20Stage15HighTurnoverScalpStrategy._stage15_tag_weights,
        "s15_05_apt_vwap_l_mc_h20m_l5": 1.10,
        "s15_06_mkr_vstretch_l_mc_h8m_l5": 0.96,
        "s15_07_mkr_maoff_s_ma_h5m_l5": 0.88,
    }
    tag_stake_weights = {
        **Intp20Stage14AggressiveBoostStrategy.tag_stake_weights,
        **_stage15_aggressive_tag_weights,
    }
    leverage_bonus_tags = set(Intp20Stage15HighTurnoverScalpStrategy.leverage_bonus_tags) | {
        "s15_05_apt_vwap_l_mc_h20m_l5",
    }
