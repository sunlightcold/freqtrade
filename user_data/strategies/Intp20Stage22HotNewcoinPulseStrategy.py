from __future__ import annotations

from datetime import datetime

from Intp20Stage20AdaptiveRegimeNewcoinStrategy import (
    Intp20Stage20AdaptiveRegimeNewcoinStrategy,
)
from pandas import DataFrame


class Intp20Stage22HotNewcoinPulseStrategy(Intp20Stage20AdaptiveRegimeNewcoinStrategy):
    """
    Stage-22 high-conviction hot-newcoin pulse strategy.

    The first broad high-frequency prototypes produced many trades but were
    negative after 0.05% taker fees. This version keeps the strategy separate
    and focuses on signals with causal local edge: selected downside pulses
    plus rare, strong trend-continuation longs.
    """

    startup_candle_count = 180
    stoploss = -0.12

    max_stake_multiplier = 2.05
    min_stake_multiplier = 0.30
    max_stage19_leverage = 5.2
    max_stage20_leverage = 5.2
    max_stage22_leverage = 5.2

    stage20_memory_window = 240
    stage20_slow_memory_window = 960
    stage20_memory_horizon = 8
    stage20_fee_drag = 0.00150
    stage20_enable_short_learning_entries = True
    stage20_enable_pull_learning_entries = True

    stage22_core_prefixes = ("BTC/", "ETH/", "BNB/", "TRX/")
    stage22_hotspot_prefixes = (
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
    def _is_stage22_tag(entry_tag: str | None) -> bool:
        return bool(entry_tag and entry_tag.startswith("s22_"))

    @staticmethod
    def _stage22_hold_minutes(entry_tag: str | None) -> int:
        if entry_tag:
            for token in entry_tag.split("_"):
                if token.startswith("h") and token.endswith("m") and token[1:-1].isdigit():
                    return int(token[1:-1])
        return 6

    @staticmethod
    def _stage22_tag_leverage(entry_tag: str | None) -> float | None:
        if entry_tag:
            for token in entry_tag.split("_"):
                if token.startswith("l") and token[1:].isdigit():
                    return float(token[1:])
        return None

    @classmethod
    def _stage22_pair_weight(cls, pair: str) -> float:
        if pair.startswith(cls.stage22_hotspot_prefixes):
            return 1.18
        if pair.startswith(cls.stage22_core_prefixes):
            return 0.72
        return 1.00

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)

        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

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
            & (atr < 0.060)
            & (volume_ratio > 0.74)
            & (hot > 0.38)
            & (risk < 0.82)
            & (chop < 0.68)
            & (btc_risk < 0.92)
        )
        market_long_ok = (dataframe["stage20_btc_bias"] > -0.20) & (
            dataframe["stage20_btc_trend"] > -0.26
        )
        market_short_ok = (dataframe["stage20_btc_bias"] < 0.62) & (
            dataframe["stage20_btc_trend"] < 0.68
        )

        short_memory_ok = (
            (
                (dataframe["stage20_momo_count_short"].fillna(0.0) >= 9)
                & (dataframe["stage20_momo_edge_short"].fillna(0.0) > 0.0012)
                & (dataframe["stage20_momo_win_short"].fillna(0.5) >= 0.54)
            )
            | dataframe["stage20_momo_short_promoted"].fillna(False)
        ) & (
            (dataframe["stage20_momo_count_short_slow"].fillna(0.0) < 14)
            | (dataframe["stage20_momo_edge_short_slow"].fillna(0.0) > -0.00005)
        )
        pull_short_memory_ok = (
            (
                (dataframe["stage20_pull_count_short"].fillna(0.0) >= 10)
                & (dataframe["stage20_pull_edge_short"].fillna(0.0) > 0.0013)
                & (dataframe["stage20_pull_win_short"].fillna(0.5) >= 0.55)
            )
            | dataframe["stage20_pull_short_promoted"].fillna(False)
        ) & (
            (dataframe["stage20_pull_count_short_slow"].fillna(0.0) < 14)
            | (dataframe["stage20_pull_edge_short_slow"].fillna(0.0) > 0.00000)
        )

        no_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        pulse_long = (
            no_entry
            & tradable
            & market_long_ok
            & (hot > 0.62)
            & (risk < 0.62)
            & (dataframe["stage20_trend_long"] > 0.78)
            & (dataframe["stage20_adaptive_long"] > 0.68)
            & (dataframe["stage20_edge_long"].fillna(0.0) > 0.0015)
            & (dataframe["stage20_winrate_long"].fillna(0.5) >= 0.56)
            & (dataframe["stage19_roc_3"] > 0.0024)
            & (dataframe["stage19_roc_8"] > 0.0055)
            & (dataframe["stage19_roc_30"] > 0.0120)
            & (dataframe["stage19_roc_60"] > 0.0180)
            & (dataframe["close"] > dataframe["stage19_don_high_20"] * 1.0008)
            & (dataframe["stage19_ema_5"] > dataframe["stage19_ema_13"])
            & (volume_ratio > 1.35)
            & (rsi_7 > 55)
            & (rsi_7 < 74)
            & (close_pos > 0.64)
            & (dataframe["stage20_exhaustion_long"] < 0.52)
        )
        dataframe.loc[pulse_long, ["enter_long", "enter_tag"]] = (1, "s22_pulse_l_h6m_l3")

        no_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        pulse_short = (
            no_entry
            & tradable
            & market_short_ok
            & short_memory_ok
            & (dataframe["stage20_raw_momo_short"].fillna(False))
            & (dataframe["stage20_adaptive_short"] > 0.62)
            & (dataframe["stage20_trend_short"] > 0.58)
            & (hot > 0.40)
            & (risk < 0.76)
            & (volume_ratio > 1.04)
            & (dataframe["stage19_roc_3"] < -0.0007)
            & (dataframe["stage19_roc_8"] < -0.00155)
            & (dataframe["stage19_roc_30"] < 0.0040)
            & (dataframe["stage19_roc_60"] < 0.018)
            & (dataframe["close"] < dataframe["stage19_don_low_20"] * 0.9999)
            & (dataframe["stage19_ema_5"] < dataframe["stage19_ema_13"])
            & (rsi_7 < 52)
            & (rsi_7 > 20)
            & (close_pos < 0.56)
            & (dataframe["stage20_exhaustion_short"] < 0.78)
        )
        dataframe.loc[pulse_short, ["enter_short", "enter_tag"]] = (1, "s22_pulse_s_h8m_l4")

        no_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        pull_long = (
            no_entry
            & False
        )
        dataframe.loc[pull_long, ["enter_long", "enter_tag"]] = (1, "s22_pull_l_h5m_l3")

        no_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        pull_short = (
            no_entry
            & tradable
            & market_short_ok
            & pull_short_memory_ok
            & (dataframe["stage20_raw_pull_short"].fillna(False))
            & (risk < 0.74)
            & (dataframe["stage20_adaptive_short"] > 0.64)
            & (dataframe["stage20_trend_short"] > 0.62)
            & (dataframe["stage19_roc_30"] < -0.004)
            & (dataframe["stage19_roc_60"] < 0.010)
            & (dataframe["high"] > dataframe["stage19_ema_13"] * 0.9990)
            & (dataframe["close"] < dataframe["stage19_vwap_20"])
            & (dataframe["stage19_roc_3"] < -0.0004)
            & (rsi_3.between(28, 62))
            & (rsi_7.between(24, 60))
            & (close_pos < 0.56)
            & (dataframe["stage20_exhaustion_short"] < 0.70)
        )
        dataframe.loc[pull_short, ["enter_short", "enter_tag"]] = (1, "s22_pull_s_h7m_l3")

        return dataframe

    def _stage22_scores(self, pair: str, current_time: datetime | None) -> dict[str, float]:
        scores = {
            "hot": 0.5,
            "risk": 0.5,
            "bias": 0.0,
            "trend_long": 0.5,
            "trend_short": 0.5,
            "btc_risk": 0.5,
            "chop": 0.5,
        }
        if not self.dp:
            return scores
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            row = self._row_at_trade_time(dataframe, current_time)
        except (KeyError, ValueError, TypeError, AttributeError):
            row = None
        if row is None:
            return scores
        scores["hot"] = self._bounded(float(row.get("stage19_hot_score", 0.5)))
        scores["risk"] = self._bounded(float(row.get("stage19_overheat_score", 0.5)))
        scores["bias"] = self._bounded(float(row.get("stage19_side_bias", 0.0)), -1.0, 1.0)
        scores["trend_long"] = self._bounded(float(row.get("stage20_trend_long", 0.5)))
        scores["trend_short"] = self._bounded(float(row.get("stage20_trend_short", 0.5)))
        scores["btc_risk"] = self._bounded(float(row.get("stage20_btc_risk", 0.5)))
        scores["chop"] = self._bounded(float(row.get("stage20_chop_risk", 0.5)))
        return scores

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
        if not super().confirm_trade_entry(
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
        if not self._is_stage22_tag(entry_tag):
            return True

        scores = self._stage22_scores(pair, current_time)
        side_trend = scores["trend_long"] if side == "long" else scores["trend_short"]
        side_bias = scores["bias"] if side == "long" else -scores["bias"]
        if scores["btc_risk"] > 0.94 and side_trend < 0.62:
            return False
        if scores["risk"] > 0.90 and scores["hot"] < 0.50:
            return False
        if scores["chop"] > 0.76 and side_bias < 0.08:
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
        stake = super().custom_stake_amount(
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
        if stake is None or not self._is_stage22_tag(entry_tag):
            return stake

        scores = self._stage22_scores(pair, current_time)
        side_bias = scores["bias"] if side == "long" else -scores["bias"]
        side_trend = scores["trend_long"] if side == "long" else scores["trend_short"]

        tag_boost = 1.16 if entry_tag and "_pulse_" in entry_tag else 1.02
        multiplier = self._stage22_pair_weight(pair) * tag_boost
        multiplier *= 1.0 + max(scores["hot"] - 0.45, 0.0) * 0.32
        multiplier *= 1.0 + max(side_trend - 0.55, 0.0) * 0.24
        multiplier *= 1.0 + max(side_bias, 0.0) * 0.10
        multiplier *= 1.0 - max(scores["risk"] - 0.82, 0.0) * 0.82
        multiplier *= 1.0 - max(scores["chop"] - 0.68, 0.0) * 0.60
        multiplier = self._bounded(multiplier, 0.42, 1.38)

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
        if not self._is_stage22_tag(entry_tag):
            return max(1.0, min(target, max_leverage, self.max_stage22_leverage))

        tag_leverage = self._stage22_tag_leverage(entry_tag)
        if tag_leverage is not None:
            target = max(target, tag_leverage)
        scores = self._stage22_scores(pair, current_time)
        side_trend = scores["trend_long"] if side == "long" else scores["trend_short"]
        if scores["hot"] > 0.68 and side_trend > 0.66 and scores["risk"] < 0.78:
            target += 0.45
        if scores["risk"] > 0.88 or scores["btc_risk"] > 0.90:
            target -= 0.65
        if pair.startswith(self.stage22_core_prefixes):
            target -= 0.55
        return max(1.0, min(target, max_leverage, self.max_stage22_leverage))

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool | None:
        if not self._is_stage22_tag(trade.enter_tag):
            return super().custom_exit(
                pair,
                trade,
                current_time,
                current_rate,
                current_profit,
                **kwargs,
            )

        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        hold_minutes = self._stage22_hold_minutes(trade.enter_tag)
        scores = self._stage22_scores(pair, current_time)
        side_trend = scores["trend_short"] if trade.is_short else scores["trend_long"]
        adverse_bias = scores["bias"] > 0.20 if trade.is_short else scores["bias"] < -0.20

        if current_profit >= 0.010:
            return "stage22_fast_profit_exit"
        if trade_minutes >= 1 and current_profit >= 0.006 and side_trend < 0.56:
            return "stage22_trend_take_profit"
        if current_profit <= -0.012:
            return "stage22_fast_loss_exit"
        if trade_minutes >= 2 and current_profit <= -0.006 and adverse_bias:
            return "stage22_adverse_loss_exit"
        if scores["risk"] > 0.92 and scores["chop"] > 0.72 and current_profit <= -0.004:
            return "stage22_risk_exit"
        if trade_minutes >= hold_minutes:
            return "stage22_fixed_hold_exit"
        return super().custom_exit(
            pair,
            trade,
            current_time,
            current_rate,
            current_profit,
            **kwargs,
        )
