from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from Intp20Stage18NoKeyHotspotStrategy import Intp20Stage18NoKeyHotspotStrategy
from pandas import DataFrame


class Intp20Stage19AggressiveNewcoinStrategy(Intp20Stage18NoKeyHotspotStrategy):
    """
    Stage-19 aggressive new-coin expansion.

    This keeps the Stage-18 baseline and adds generic 1m momentum / squeeze /
    snapback entries that only need short local OHLCV history.  It is meant for
    high-turnover dry-run research on a wider futures basket, not conservative
    capital deployment.
    """

    startup_candle_count = 240
    stoploss = -0.32

    max_stake_multiplier = 3.20
    min_stake_multiplier = 0.35
    max_boost_leverage = 8.5
    max_stage19_leverage = 8.5

    stage19_high_beta_prefixes = (
        "1000PEPE/",
        "1000SHIB/",
        "APT/",
        "ARB/",
        "DOGE/",
        "FET/",
        "FIL/",
        "GALA/",
        "HBAR/",
        "INJ/",
        "MANA/",
        "OP/",
        "RUNE/",
        "SAND/",
        "SUI/",
    )
    stage19_core_prefixes = ("BTC/", "ETH/", "BNB/", "TRX/")
    stage19_momentum_long_prefixes = (
        "XLM/",
        "ICP/",
        "SUI/",
        "LINK/",
    )
    stage19_momentum_short_prefixes: tuple[str, ...] = ()
    stage19_squeeze_prefixes: tuple[str, ...] = ()
    stage19_snap_prefixes: tuple[str, ...] = ()

    @staticmethod
    def _safe_div(numerator, denominator):
        return (numerator / denominator.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)

    @staticmethod
    def _rsi(close, period: int):
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _score(series, low: float, high: float):
        return ((series - low) / (high - low)).clip(0.0, 1.0)

    @classmethod
    def _stage19_pair_weight(cls, pair: str) -> float:
        if pair.startswith(cls.stage19_high_beta_prefixes):
            return 1.26
        if pair.startswith(cls.stage19_core_prefixes):
            return 0.78
        return 1.04

    @staticmethod
    def _is_stage19_tag(entry_tag: str | None) -> bool:
        return bool(entry_tag and entry_tag.startswith("s19_"))

    @staticmethod
    def _stage19_hold_minutes(entry_tag: str | None) -> int:
        if entry_tag:
            for token in entry_tag.split("_"):
                if token.startswith("h") and token.endswith("m") and token[1:-1].isdigit():
                    return int(token[1:-1])
        return 10

    @staticmethod
    def _stage19_tag_leverage(entry_tag: str | None) -> float | None:
        if entry_tag:
            for token in entry_tag.split("_"):
                if token.startswith("l") and token[1:].isdigit():
                    return float(token[1:])
        return None

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)

        close = dataframe["close"].replace(0, np.nan)
        high = dataframe["high"]
        low = dataframe["low"]
        volume = dataframe["volume"]
        typical = (high + low + close) / 3

        dataframe["stage19_ema_5"] = close.ewm(span=5, adjust=False, min_periods=5).mean()
        dataframe["stage19_ema_13"] = close.ewm(span=13, adjust=False, min_periods=13).mean()
        dataframe["stage19_ema_34"] = close.ewm(span=34, adjust=False, min_periods=20).mean()
        dataframe["stage19_rsi_3"] = self._rsi(close, 3)
        dataframe["stage19_rsi_7"] = self._rsi(close, 7)

        prev_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        dataframe["stage19_atr_pct"] = self._safe_div(
            true_range.rolling(14, min_periods=5).mean(),
            close,
        )
        dataframe["stage19_range_pct"] = self._safe_div(high - low, close)
        dataframe["stage19_body_pct"] = self._safe_div((close - dataframe["open"]).abs(), close)
        dataframe["stage19_upper_wick_pct"] = self._safe_div(
            high - dataframe[["open", "close"]].max(axis=1),
            close,
        )
        dataframe["stage19_lower_wick_pct"] = self._safe_div(
            dataframe[["open", "close"]].min(axis=1) - low,
            close,
        )

        dataframe["stage19_volume_mean_20"] = volume.rolling(20, min_periods=5).mean()
        dataframe["stage19_volume_mean_120"] = volume.rolling(120, min_periods=20).mean()
        dataframe["stage19_volume_ratio"] = self._safe_div(
            dataframe["stage19_volume_mean_20"],
            dataframe["stage19_volume_mean_120"],
        ).fillna(1.0)

        for period in (3, 8, 15, 30, 60):
            dataframe[f"stage19_roc_{period}"] = close / close.shift(period) - 1

        dataframe["stage19_don_high_20"] = high.rolling(20, min_periods=10).max().shift(1)
        dataframe["stage19_don_low_20"] = low.rolling(20, min_periods=10).min().shift(1)
        dataframe["stage19_don_high_60"] = high.rolling(60, min_periods=20).max().shift(1)
        dataframe["stage19_don_low_60"] = low.rolling(60, min_periods=20).min().shift(1)

        volume_20 = volume.rolling(20, min_periods=5).sum()
        volume_60 = volume.rolling(60, min_periods=15).sum()
        dataframe["stage19_vwap_20"] = self._safe_div(
            (typical * volume).rolling(20, min_periods=5).sum(), volume_20
        )
        dataframe["stage19_vwap_60"] = self._safe_div(
            (typical * volume).rolling(60, min_periods=15).sum(), volume_60
        )

        bb_mid = close.rolling(20, min_periods=10).mean()
        bb_std = close.rolling(20, min_periods=10).std()
        dataframe["stage19_bb_mid"] = bb_mid
        dataframe["stage19_bb_high"] = bb_mid + 2 * bb_std
        dataframe["stage19_bb_low"] = bb_mid - 2 * bb_std
        dataframe["stage19_bb_width"] = self._safe_div(
            dataframe["stage19_bb_high"] - dataframe["stage19_bb_low"], bb_mid
        )
        dataframe["stage19_bb_width_mean_120"] = (
            dataframe["stage19_bb_width"].rolling(120, min_periods=30).mean()
        )

        volume_score = self._score(dataframe["stage19_volume_ratio"].fillna(1.0), 0.85, 2.60)
        impulse_score = (dataframe["stage19_roc_8"].abs() / 0.020).clip(0.0, 1.0).fillna(0.0)
        trend_score = (dataframe["stage19_roc_30"].abs() / 0.050).clip(0.0, 1.0).fillna(0.0)
        atr_score = self._score(dataframe["stage19_atr_pct"].fillna(0.0), 0.0010, 0.035)
        width_score = self._score(dataframe["stage19_bb_width"].fillna(0.0), 0.004, 0.050)

        dataframe["stage19_hot_score"] = (
            0.30 * volume_score
            + 0.24 * impulse_score
            + 0.18 * trend_score
            + 0.16 * atr_score
            + 0.12 * width_score
        ).clip(0.0, 1.0)
        dataframe["stage19_overheat_score"] = (
            0.42 * (dataframe["stage19_roc_3"].abs() / 0.035).clip(0.0, 1.0).fillna(0.0)
            + 0.36 * (dataframe["stage19_roc_15"].abs() / 0.075).clip(0.0, 1.0).fillna(0.0)
            + 0.22 * self._score(dataframe["stage19_atr_pct"].fillna(0.0), 0.020, 0.065)
        ).clip(0.0, 1.0)
        dataframe["stage19_side_bias"] = (
            0.55 * (dataframe["stage19_roc_15"] / 0.032).clip(-1.0, 1.0).fillna(0.0)
            + 0.45 * (dataframe["stage19_roc_60"] / 0.070).clip(-1.0, 1.0).fillna(0.0)
        ).clip(-1.0, 1.0)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)
        if "enter_long" not in dataframe:
            dataframe["enter_long"] = 0
        if "enter_short" not in dataframe:
            dataframe["enter_short"] = 0

        hot = dataframe["stage19_hot_score"].fillna(0.0)
        risk = dataframe["stage19_overheat_score"].fillna(1.0)
        bias = dataframe["stage19_side_bias"].fillna(0.0)
        atr = dataframe["stage19_atr_pct"].fillna(0.0)
        volume_ratio = dataframe["stage19_volume_ratio"].fillna(1.0)
        rsi_3 = dataframe["stage19_rsi_3"].fillna(50.0)
        rsi_7 = dataframe["stage19_rsi_7"].fillna(50.0)
        range_pct = dataframe["stage19_range_pct"].fillna(0.0)
        pair = metadata["pair"]

        tradable_risk = (atr > 0.0005) & (atr < 0.075) & (volume_ratio > 0.65)
        no_stage_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        momentum_long_pair = pair.startswith(self.stage19_momentum_long_prefixes)
        momentum_short_pair = pair.startswith(self.stage19_momentum_short_prefixes)
        squeeze_pair = pair.startswith(self.stage19_squeeze_prefixes)
        snap_pair = pair.startswith(self.stage19_snap_prefixes)

        momo_long = (
            momentum_long_pair
            & no_stage_entry
            & tradable_risk
            & (hot > 0.48)
            & (risk < 0.86)
            & (bias > 0.18)
            & (volume_ratio > 1.18)
            & (dataframe["close"] > dataframe["stage19_don_high_20"] * 1.0005)
            & (dataframe["stage19_ema_5"] > dataframe["stage19_ema_13"])
            & (dataframe["stage19_ema_13"] > dataframe["stage19_ema_34"])
            & (dataframe["stage19_roc_3"] > 0.0015)
            & (dataframe["stage19_roc_8"] > 0.0028)
            & (dataframe["stage19_roc_60"] > -0.018)
            & (rsi_7 > 52)
            & (rsi_7 < 80)
            & (dataframe["stage19_upper_wick_pct"] < dataframe["stage19_body_pct"] * 1.45 + 0.0015)
        )
        dataframe.loc[momo_long, ["enter_long", "enter_tag"]] = (1, "s19_momo_l_h10m_l8")

        no_stage_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        momo_short = (
            momentum_short_pair
            & no_stage_entry
            & tradable_risk
            & (hot > 0.42)
            & (risk < 0.92)
            & (bias < -0.12)
            & (volume_ratio > 1.08)
            & (dataframe["close"] < dataframe["stage19_don_low_20"] * 0.9998)
            & (dataframe["stage19_ema_5"] < dataframe["stage19_ema_13"])
            & (dataframe["stage19_ema_13"] < dataframe["stage19_ema_34"] * 1.002)
            & (dataframe["stage19_roc_3"] < -0.0010)
            & (dataframe["stage19_roc_8"] < -0.0020)
            & (rsi_7 < 52)
            & (rsi_7 > 16)
            & (dataframe["stage19_lower_wick_pct"] < dataframe["stage19_body_pct"] * 1.9 + 0.002)
        )
        dataframe.loc[momo_short, ["enter_short", "enter_tag"]] = (1, "s19_momo_s_h10m_l8")

        squeeze_ready = (
            dataframe["stage19_bb_width"].shift(1)
            < dataframe["stage19_bb_width_mean_120"]
            .shift(1)
            .fillna(dataframe["stage19_bb_width"].shift(1))
            * 0.95
        )
        no_stage_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        squeeze_long = (
            squeeze_pair
            & no_stage_entry
            & tradable_risk
            & squeeze_ready
            & (hot > 0.36)
            & (risk < 0.88)
            & (bias > 0.05)
            & (volume_ratio > 1.00)
            & (range_pct > atr * 0.55)
            & (dataframe["close"] > dataframe["stage19_don_high_60"] * 1.0001)
            & (dataframe["close"] > dataframe["stage19_vwap_20"])
            & (rsi_7 > 45)
            & (rsi_7 < 82)
        )
        dataframe.loc[squeeze_long, ["enter_long", "enter_tag"]] = (1, "s19_sqz_l_h14m_l8")

        no_stage_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        squeeze_short = (
            squeeze_pair
            & no_stage_entry
            & tradable_risk
            & squeeze_ready
            & (hot > 0.36)
            & (risk < 0.88)
            & (bias < -0.05)
            & (volume_ratio > 1.00)
            & (range_pct > atr * 0.55)
            & (dataframe["close"] < dataframe["stage19_don_low_60"] * 0.9999)
            & (dataframe["close"] < dataframe["stage19_vwap_20"])
            & (rsi_7 < 55)
            & (rsi_7 > 18)
        )
        dataframe.loc[squeeze_short, ["enter_short", "enter_tag"]] = (1, "s19_sqz_s_h14m_l8")

        close_pos = self._safe_div(
            dataframe["close"] - dataframe["low"], dataframe["high"] - dataframe["low"]
        ).fillna(0.5)
        no_stage_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        snap_long = (
            snap_pair
            & no_stage_entry
            & tradable_risk
            & (hot > 0.38)
            & (risk < 0.97)
            & (dataframe["stage19_roc_3"] < -0.0055)
            & (dataframe["low"] < dataframe["stage19_don_low_20"] * 0.9995)
            & (dataframe["stage19_lower_wick_pct"] > dataframe["stage19_body_pct"] * 1.15)
            & (close_pos > 0.45)
            & (rsi_3 < 34)
        )
        dataframe.loc[snap_long, ["enter_long", "enter_tag"]] = (1, "s19_snap_l_h8m_l7")

        no_stage_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        snap_short = (
            snap_pair
            & no_stage_entry
            & tradable_risk
            & (hot > 0.38)
            & (risk < 0.97)
            & (dataframe["stage19_roc_3"] > 0.0055)
            & (dataframe["high"] > dataframe["stage19_don_high_20"] * 1.0005)
            & (dataframe["stage19_upper_wick_pct"] > dataframe["stage19_body_pct"] * 1.15)
            & (close_pos < 0.55)
            & (rsi_3 > 66)
        )
        dataframe.loc[snap_short, ["enter_short", "enter_tag"]] = (1, "s19_snap_s_h8m_l7")
        return dataframe

    @staticmethod
    def _row_at_trade_time(dataframe: DataFrame, current_time: datetime | None):
        return Intp20Stage18NoKeyHotspotStrategy._row_at_time(dataframe, current_time)

    def _stage19_scores(self, pair: str, current_time: datetime | None) -> dict[str, float]:
        scores = {
            "hot": 0.5,
            "risk": 0.5,
            "bias": 0.0,
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

        if not self._is_stage19_tag(entry_tag):
            return True
        scores = self._stage19_scores(pair, current_time)
        side_bias = scores["bias"] if side == "long" else -scores["bias"]
        if scores["risk"] > 0.96 and scores["hot"] < 0.62:
            return False
        if side_bias < -0.55 and scores["risk"] > 0.82:
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
        if stake is None or not self._is_stage19_tag(entry_tag):
            return stake

        scores = self._stage19_scores(pair, current_time)
        side_bias = scores["bias"] if side == "long" else -scores["bias"]
        tag_boost = 1.22
        if entry_tag and "_momo_" in entry_tag:
            tag_boost = 1.36
        elif entry_tag and "_sqz_" in entry_tag:
            tag_boost = 1.28
        elif entry_tag and "_snap_" in entry_tag:
            tag_boost = 1.08

        multiplier = self._stage19_pair_weight(pair) * tag_boost
        multiplier *= 1.0 + max(scores["hot"] - 0.50, 0.0) * 0.35
        multiplier *= 1.0 + max(side_bias, 0.0) * 0.16
        multiplier *= 1.0 - max(scores["risk"] - 0.82, 0.0) * 0.62
        multiplier = self._bounded(multiplier, 0.58, 1.78)

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
        if not self._is_stage19_tag(entry_tag):
            return max(1.0, min(target, max_leverage, self.max_stage19_leverage))

        tag_leverage = self._stage19_tag_leverage(entry_tag)
        if tag_leverage is not None:
            target = max(target, tag_leverage)
        scores = self._stage19_scores(pair, current_time)
        if scores["hot"] > 0.72 and scores["risk"] < 0.75:
            target += 0.35
        if scores["risk"] > 0.90:
            target -= 0.85
        if pair.startswith(self.stage19_core_prefixes):
            target -= 0.50
        return max(1.0, min(target, max_leverage, self.max_stage19_leverage))

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool | None:
        if not self._is_stage19_tag(trade.enter_tag):
            return super().custom_exit(
                pair, trade, current_time, current_rate, current_profit, **kwargs
            )

        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        hold_minutes = self._stage19_hold_minutes(trade.enter_tag)
        scores = self._stage19_scores(pair, current_time)
        adverse_bias = scores["bias"] < -0.30 if not trade.is_short else scores["bias"] > 0.30

        if current_profit >= 0.018:
            return "stage19_fast_profit_exit"
        if trade_minutes >= 4 and current_profit >= 0.010 and adverse_bias:
            return "stage19_bias_take_profit"
        if trade_minutes >= 4 and current_profit <= -0.026:
            return "stage19_fast_loss_exit"
        if scores["risk"] > 0.88 and adverse_bias and current_profit <= -0.010:
            return "stage19_adverse_risk_exit"
        if trade_minutes >= hold_minutes:
            return "stage19_fixed_hold_exit"
        return super().custom_exit(
            pair, trade, current_time, current_rate, current_profit, **kwargs
        )
