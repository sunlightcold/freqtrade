from __future__ import annotations

from datetime import datetime

from Intp20Stage19AggressiveNewcoinStrategy import Intp20Stage19AggressiveNewcoinStrategy
from Intp20Stage20AdaptiveRegimeNewcoinStrategy import (
    Intp20Stage20AdaptiveRegimeNewcoinStrategy,
)
from pandas import DataFrame


class Intp20Stage21DualHfNewcoinStrategy(Intp20Stage20AdaptiveRegimeNewcoinStrategy):
    """
    Stage-21 dual-side high-frequency new-coin strategy.

    This variant keeps the causal Stage-20 regime/memory features but adds
    lower-latency long and short entries for active futures names. It is meant
    for dry-run observation first because the wider universe increases slippage
    and exchange data-load pressure.
    """

    startup_candle_count = 180
    stoploss = -0.24

    max_stake_multiplier = 2.20
    min_stake_multiplier = 0.28
    max_stage19_leverage = 6.5
    max_stage20_leverage = 6.5
    max_stage21_leverage = 6.5

    stage20_memory_window = 240
    stage20_slow_memory_window = 960
    stage20_memory_horizon = 8
    stage20_fee_drag = 0.00150
    stage20_enable_short_learning_entries = True
    stage20_enable_pull_learning_entries = True

    stage21_core_prefixes = ("BTC/", "ETH/", "BNB/", "TRX/")
    stage21_hotspot_prefixes = (
        "1000BONK/",
        "1000FLOKI/",
        "1000PEPE/",
        "1000SATS/",
        "1000SHIB/",
        "ACT/",
        "AIXBT/",
        "BERA/",
        "BOME/",
        "DEGEN/",
        "FARTCOIN/",
        "GOAT/",
        "GRASS/",
        "JUP/",
        "KAITO/",
        "MERL/",
        "MEW/",
        "MOODENG/",
        "PENGU/",
        "PNUT/",
        "POPCAT/",
        "PUMP/",
        "SHELL/",
        "TURBO/",
        "VIRTUAL/",
        "WIF/",
    )

    @staticmethod
    def _is_stage21_tag(entry_tag: str | None) -> bool:
        return bool(entry_tag and entry_tag.startswith("s21_"))

    @staticmethod
    def _is_stage20_tag(entry_tag: str | None) -> bool:
        return bool(entry_tag and entry_tag.startswith(("s20_", "s21_")))

    @staticmethod
    def _stage20_tag_family(entry_tag: str | None) -> str:
        if entry_tag and ("_momo_" in entry_tag or "_brk_" in entry_tag):
            return "momo"
        if entry_tag and ("_pull_" in entry_tag or "_rev_" in entry_tag):
            return "pull"
        return "blend"

    @classmethod
    def _stage20_pair_weight(cls, pair: str) -> float:
        if pair.startswith(cls.stage21_hotspot_prefixes):
            return 1.16
        if pair.startswith(cls.stage21_core_prefixes):
            return 0.78
        return 1.00

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)
        if "enter_long" not in dataframe:
            dataframe["enter_long"] = 0
        if "enter_short" not in dataframe:
            dataframe["enter_short"] = 0

        atr = dataframe["stage19_atr_pct"].fillna(0.0)
        volume_ratio = dataframe["stage19_volume_ratio"].fillna(1.0)
        hot = dataframe["stage19_hot_score"].fillna(0.0)
        risk = dataframe["stage19_overheat_score"].fillna(1.0)
        rsi_3 = dataframe["stage19_rsi_3"].fillna(50.0)
        rsi_7 = dataframe["stage19_rsi_7"].fillna(50.0)
        chop = dataframe["stage20_chop_risk"].fillna(1.0)
        btc_risk = dataframe["stage20_btc_risk"].fillna(0.5)
        close_pos = dataframe["stage20_close_pos"].fillna(0.5)

        tradable = (
            (atr > 0.00055)
            & (atr < 0.058)
            & (volume_ratio > 0.72)
            & (chop < 0.70)
            & (btc_risk < 0.93)
        )
        long_regime = (dataframe["stage20_btc_bias"] > -0.64) & (
            dataframe["stage20_btc_trend"] > -0.72
        )
        short_regime = (dataframe["stage20_btc_bias"] < 0.64) & (
            dataframe["stage20_btc_trend"] < 0.72
        )

        near_momo_long = (
            dataframe["stage20_momo_long_promoted"].fillna(False)
            | (
                (dataframe["stage20_momo_count_long"].fillna(0.0) >= 6)
                & (dataframe["stage20_momo_edge_long"].fillna(0.0) > 0.0006)
                & (dataframe["stage20_momo_win_long"].fillna(0.5) >= 0.52)
                & (
                    (dataframe["stage20_momo_count_long_slow"].fillna(0.0) < 12)
                    | (dataframe["stage20_momo_edge_long_slow"].fillna(0.0) > -0.00035)
                )
            )
        )
        near_momo_short = (
            dataframe["stage20_momo_short_promoted"].fillna(False)
            | (
                (dataframe["stage20_momo_count_short"].fillna(0.0) >= 9)
                & (dataframe["stage20_momo_edge_short"].fillna(0.0) > 0.0011)
                & (dataframe["stage20_momo_win_short"].fillna(0.5) >= 0.54)
                & (
                    (dataframe["stage20_momo_count_short_slow"].fillna(0.0) < 14)
                    | (dataframe["stage20_momo_edge_short_slow"].fillna(0.0) > -0.00010)
                )
            )
        )
        near_pull_long = (
            dataframe["stage20_pull_long_promoted"].fillna(False)
            | (
                (dataframe["stage20_pull_count_long"].fillna(0.0) >= 6)
                & (dataframe["stage20_pull_edge_long"].fillna(0.0) > 0.0005)
                & (dataframe["stage20_pull_win_long"].fillna(0.5) >= 0.51)
                & (
                    (dataframe["stage20_pull_count_long_slow"].fillna(0.0) < 12)
                    | (dataframe["stage20_pull_edge_long_slow"].fillna(0.0) > -0.00035)
                )
            )
        )
        near_pull_short = (
            dataframe["stage20_pull_short_promoted"].fillna(False)
            | (
                (dataframe["stage20_pull_count_short"].fillna(0.0) >= 9)
                & (dataframe["stage20_pull_edge_short"].fillna(0.0) > 0.0010)
                & (dataframe["stage20_pull_win_short"].fillna(0.5) >= 0.54)
                & (
                    (dataframe["stage20_pull_count_short_slow"].fillna(0.0) < 14)
                    | (dataframe["stage20_pull_edge_short_slow"].fillna(0.0) > -0.00010)
                )
            )
        )

        no_stage_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        momo_long = (
            no_stage_entry
            & tradable
            & long_regime
            & dataframe["stage20_raw_momo_long"].fillna(False)
            & near_momo_long
            & (dataframe["stage20_adaptive_long"] > 0.58)
            & (dataframe["stage20_trend_long"] > 0.56)
            & (risk < 0.80)
            & (hot > 0.40)
            & (volume_ratio > 1.00)
            & (dataframe["stage19_roc_3"] > 0.00070)
            & (dataframe["stage19_roc_8"] > 0.00155)
            & (rsi_7 > 50)
            & (rsi_7 < 80)
            & (close_pos > 0.44)
            & (dataframe["stage20_exhaustion_long"] < 0.78)
        )
        dataframe.loc[momo_long, ["enter_long", "enter_tag"]] = (1, "s21_momo_l_h8m_l5")

        no_stage_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        momo_short = (
            no_stage_entry
            & tradable
            & short_regime
            & dataframe["stage20_raw_momo_short"].fillna(False)
            & near_momo_short
            & (dataframe["stage20_adaptive_short"] > 0.62)
            & (dataframe["stage20_trend_short"] > 0.58)
            & (risk < 0.76)
            & (hot > 0.42)
            & (volume_ratio > 1.04)
            & (dataframe["stage19_roc_3"] < -0.00070)
            & (dataframe["stage19_roc_8"] < -0.00155)
            & (rsi_7 < 50)
            & (rsi_7 > 20)
            & (close_pos < 0.56)
            & (dataframe["stage20_exhaustion_short"] < 0.78)
        )
        dataframe.loc[momo_short, ["enter_short", "enter_tag"]] = (1, "s21_momo_s_h8m_l5")

        no_stage_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        pull_long = (
            no_stage_entry
            & tradable
            & long_regime
            & dataframe["stage20_raw_pull_long"].fillna(False)
            & near_pull_long
            & (dataframe["stage20_adaptive_long"] > 0.56)
            & (dataframe["stage20_trend_long"] > 0.56)
            & (risk < 0.76)
            & (hot > 0.34)
            & (volume_ratio > 0.80)
            & (dataframe["stage19_roc_60"] > -0.006)
            & (rsi_3.between(34, 66))
            & (rsi_7.between(38, 70))
            & (close_pos > 0.38)
            & (dataframe["stage20_exhaustion_long"] < 0.68)
        )
        dataframe.loc[pull_long, ["enter_long", "enter_tag"]] = (1, "s21_pull_l_h7m_l4")

        no_stage_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        pull_short = (
            no_stage_entry
            & tradable
            & short_regime
            & dataframe["stage20_raw_pull_short"].fillna(False)
            & near_pull_short
            & (dataframe["stage20_adaptive_short"] > 0.60)
            & (dataframe["stage20_trend_short"] > 0.56)
            & (risk < 0.74)
            & (hot > 0.36)
            & (volume_ratio > 0.84)
            & (dataframe["stage19_roc_60"] < 0.006)
            & (rsi_3.between(34, 66))
            & (rsi_7.between(30, 62))
            & (close_pos < 0.62)
            & (dataframe["stage20_exhaustion_short"] < 0.68)
        )
        dataframe.loc[pull_short, ["enter_short", "enter_tag"]] = (1, "s21_pull_s_h7m_l4")
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
        if not self._is_stage21_tag(entry_tag):
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
        if not Intp20Stage19AggressiveNewcoinStrategy.confirm_trade_entry(
            self,
            pair,
            order_type,
            amount,
            rate,
            time_in_force,
            current_time,
            entry_tag,
            side,
            **kwargs,
        ):
            return False

        scores = self._stage20_scores(pair, current_time, self._stage20_tag_family(entry_tag))
        side_score = scores["long"] if side == "long" else scores["short"]
        side_edge = scores["edge_long"] if side == "long" else scores["edge_short"]
        side_count = scores["count_long"] if side == "long" else scores["count_short"]
        side_edge_slow = scores["edge_long_slow"] if side == "long" else scores["edge_short_slow"]
        side_count_slow = (
            scores["count_long_slow"] if side == "long" else scores["count_short_slow"]
        )

        if scores["btc_risk"] > 0.98:
            return False
        if side_score < 0.42 and "_rev_" not in (entry_tag or ""):
            return False
        if side_count >= 6 and side_edge < -0.0026:
            return False
        if side_count_slow >= 12 and side_edge_slow < -0.0010:
            return False
        if scores["risk"] > 0.96 and scores["chop"] > 0.66:
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
        if not self._is_stage21_tag(entry_tag):
            return super().custom_stake_amount(
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

        stake = Intp20Stage19AggressiveNewcoinStrategy.custom_stake_amount(
            self,
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
        if stake is None:
            return stake

        scores = self._stage20_scores(pair, current_time, self._stage20_tag_family(entry_tag))
        side_score = scores["long"] if side == "long" else scores["short"]
        side_edge = scores["edge_long"] if side == "long" else scores["edge_short"]
        side_count = scores["count_long"] if side == "long" else scores["count_short"]

        tag_boost = 1.12
        if entry_tag and "_momo_" in entry_tag:
            tag_boost = 1.22
        elif entry_tag and "_brk_" in entry_tag:
            tag_boost = 1.14
        elif entry_tag and "_rev_" in entry_tag:
            tag_boost = 0.88

        multiplier = self._stage20_pair_weight(pair) * tag_boost
        multiplier *= 0.82 + side_score * 0.44
        multiplier *= 1.0 + max(side_edge, 0.0) * 12.0
        multiplier *= 0.92 + min(side_count / 10.0, 1.0) * 0.18
        multiplier *= 1.0 - max(scores["risk"] - 0.84, 0.0) * 0.55
        multiplier *= 1.0 - max(scores["chop"] - 0.60, 0.0) * 0.45
        multiplier = self._bounded(multiplier, 0.42, 1.28)

        adjusted = stake * multiplier
        if min_stake:
            adjusted = max(adjusted, min_stake)
        return min(adjusted, max_stake)

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
        if not self._is_stage21_tag(entry_tag):
            return super().leverage(
                pair,
                current_time,
                current_rate,
                proposed_leverage,
                max_leverage,
                entry_tag,
                side,
                **kwargs,
            )

        target = Intp20Stage19AggressiveNewcoinStrategy.leverage(
            self,
            pair,
            current_time,
            current_rate,
            proposed_leverage,
            max_leverage,
            entry_tag,
            side,
            **kwargs,
        )
        tag_leverage = self._stage20_tag_leverage(entry_tag)
        if tag_leverage is not None:
            target = max(target, tag_leverage)

        scores = self._stage20_scores(pair, current_time, self._stage20_tag_family(entry_tag))
        side_score = scores["long"] if side == "long" else scores["short"]
        side_edge = scores["edge_long"] if side == "long" else scores["edge_short"]
        side_count = scores["count_long"] if side == "long" else scores["count_short"]

        if side_score > 0.66 and side_edge > 0.0010 and side_count >= 4:
            target += 0.35
        if pair.startswith(self.stage21_hotspot_prefixes):
            target += 0.20
        if scores["risk"] > 0.90 or scores["btc_risk"] > 0.92:
            target -= 0.80
        if scores["chop"] > 0.70:
            target -= 0.40
        if pair.startswith(self.stage21_core_prefixes):
            target -= 0.45
        return max(1.0, min(target, max_leverage, self.max_stage21_leverage))

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool | None:
        if not self._is_stage21_tag(trade.enter_tag):
            return super().custom_exit(
                pair,
                trade,
                current_time,
                current_rate,
                current_profit,
                **kwargs,
            )

        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        hold_minutes = self._stage20_hold_minutes(trade.enter_tag)
        scores = self._stage20_scores(pair, current_time, self._stage20_tag_family(trade.enter_tag))
        side_score = scores["short"] if trade.is_short else scores["long"]
        side_edge = scores["edge_short"] if trade.is_short else scores["edge_long"]
        side_count = scores["count_short"] if trade.is_short else scores["count_long"]

        if current_profit >= 0.011:
            return "stage21_fast_profit_exit"
        if trade_minutes >= 2 and current_profit >= 0.006 and side_score < 0.48:
            return "stage21_score_take_profit"
        if trade_minutes >= 2 and current_profit <= -0.012:
            return "stage21_fast_loss_exit"
        if side_count >= 5 and side_edge < -0.0006 and current_profit <= -0.004:
            return "stage21_memory_decay_exit"
        if scores["risk"] > 0.91 and scores["chop"] > 0.62 and current_profit <= -0.005:
            return "stage21_regime_risk_exit"
        if trade_minutes >= hold_minutes:
            return "stage21_fixed_hold_exit"
        return super().custom_exit(
            pair,
            trade,
            current_time,
            current_rate,
            current_profit,
            **kwargs,
        )
