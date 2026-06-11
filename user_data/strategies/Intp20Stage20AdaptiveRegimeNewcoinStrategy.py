from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from Intp20Stage19AggressiveNewcoinStrategy import Intp20Stage19AggressiveNewcoinStrategy
from pandas import DataFrame


class Intp20Stage20AdaptiveRegimeNewcoinStrategy(Intp20Stage19AggressiveNewcoinStrategy):
    """
    Stage-20 adaptive regime/new-coin strategy.

    Stage-20 keeps the Stage-18/19 base stack but disables the narrow
    pair-prefix Stage-19 add-on.  Its new high-frequency layer is gated by
    current OHLCV regime quality plus a causal rolling memory of how the same
    generic signal family has recently behaved after fees.
    """

    startup_candle_count = 240
    stoploss = -0.30

    max_stake_multiplier = 3.00
    min_stake_multiplier = 0.32
    max_stage19_leverage = 7.2
    max_stage20_leverage = 7.2

    stage19_momentum_long_prefixes: tuple[str, ...] = ()
    stage19_momentum_short_prefixes: tuple[str, ...] = ()
    stage19_squeeze_prefixes: tuple[str, ...] = ()
    stage19_snap_prefixes: tuple[str, ...] = ()

    stage20_core_prefixes = ("BTC/", "ETH/", "BNB/", "TRX/")
    stage20_high_beta_prefixes = (
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

    stage20_memory_window = 360
    stage20_slow_memory_window = 1440
    stage20_memory_horizon = 12
    stage20_fee_drag = 0.00150
    stage20_enable_short_learning_entries = False
    stage20_enable_pull_learning_entries = False

    @staticmethod
    def _is_stage20_tag(entry_tag: str | None) -> bool:
        return bool(entry_tag and entry_tag.startswith("s20_"))

    @staticmethod
    def _stage20_hold_minutes(entry_tag: str | None) -> int:
        if entry_tag:
            for token in entry_tag.split("_"):
                if token.startswith("h") and token.endswith("m") and token[1:-1].isdigit():
                    return int(token[1:-1])
        return 12

    @staticmethod
    def _stage20_tag_leverage(entry_tag: str | None) -> float | None:
        if entry_tag:
            for token in entry_tag.split("_"):
                if token.startswith("l") and token[1:].isdigit():
                    return float(token[1:])
        return None

    @staticmethod
    def _stage20_tag_family(entry_tag: str | None) -> str:
        if entry_tag and "_momo_" in entry_tag:
            return "momo"
        if entry_tag and "_pull_" in entry_tag:
            return "pull"
        return "blend"

    @classmethod
    def _stage20_pair_weight(cls, pair: str) -> float:
        if pair.startswith(cls.stage20_high_beta_prefixes):
            return 1.12
        if pair.startswith(cls.stage20_core_prefixes):
            return 0.84
        return 1.00

    @staticmethod
    def _rolling_mean_when(value, mask, window: int, min_periods: int = 1):
        weighted = value.where(mask, 0.0).rolling(window, min_periods=min_periods).sum()
        count = mask.astype(float).rolling(window, min_periods=min_periods).sum()
        return weighted / count.replace(0, np.nan), count

    def _stage20_btc_context(self) -> DataFrame:
        if not self.dp:
            return DataFrame()
        try:
            btc = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe=self.timeframe)
        except (KeyError, ValueError, TypeError, AttributeError):
            return DataFrame()
        if btc.empty:
            return DataFrame()

        btc = btc.copy()
        close = btc["close"].replace(0, np.nan)
        prev_close = close.shift(1)
        true_range = pd.concat(
            [
                btc["high"] - btc["low"],
                (btc["high"] - prev_close).abs(),
                (btc["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr_pct = self._safe_div(true_range.rolling(14, min_periods=5).mean(), close)
        roc_15 = close / close.shift(15) - 1
        roc_60 = close / close.shift(60) - 1
        ema_34 = close.ewm(span=34, adjust=False, min_periods=20).mean()
        ema_120 = close.ewm(span=120, adjust=False, min_periods=60).mean()
        bb_mid = close.rolling(20, min_periods=10).mean()
        bb_std = close.rolling(20, min_periods=10).std()
        bb_width = self._safe_div(4 * bb_std, bb_mid)

        context = DataFrame(
            {
                "date": btc["date"],
                "stage20_btc_bias": (
                    0.58 * (roc_60 / 0.055).clip(-1.0, 1.0).fillna(0.0)
                    + 0.42 * (roc_15 / 0.024).clip(-1.0, 1.0).fillna(0.0)
                ).clip(-1.0, 1.0),
                "stage20_btc_trend": (
                    ((ema_34 / ema_120 - 1) / 0.030).clip(-1.0, 1.0).fillna(0.0)
                ),
                "stage20_btc_risk": (
                    0.45 * (roc_15.abs() / 0.035).clip(0.0, 1.0).fillna(0.0)
                    + 0.35 * (atr_pct / 0.028).clip(0.0, 1.0).fillna(0.0)
                    + 0.20 * (bb_width / 0.060).clip(0.0, 1.0).fillna(0.0)
                ).clip(0.0, 1.0),
            }
        )
        return context

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)

        close = dataframe["close"].replace(0, np.nan)
        high = dataframe["high"]
        low = dataframe["low"]
        open_ = dataframe["open"]
        dataframe["stage20_history_bars"] = np.arange(len(dataframe)) + 1
        dataframe["stage20_age_score"] = (
            (dataframe["stage20_history_bars"] - self.startup_candle_count) / 720
        ).clip(0.35, 1.0)

        atr = dataframe["stage19_atr_pct"].fillna(0.0)
        atr_mean = atr.rolling(240, min_periods=60).mean()
        atr_std = atr.rolling(240, min_periods=60).std()
        dataframe["stage20_atr_z"] = ((atr - atr_mean) / atr_std.replace(0, np.nan)).clip(
            -3.0,
            3.0,
        )
        width = dataframe["stage19_bb_width"].fillna(0.0)
        width_mean = width.rolling(240, min_periods=60).mean()
        width_std = width.rolling(240, min_periods=60).std()
        dataframe["stage20_width_z"] = (
            (width - width_mean) / width_std.replace(0, np.nan)
        ).clip(-3.0, 3.0)

        ema_13 = dataframe["stage19_ema_13"]
        ema_34 = dataframe["stage19_ema_34"]
        ema_89 = close.ewm(span=89, adjust=False, min_periods=45).mean()
        dataframe["stage20_ema_89"] = ema_89
        dataframe["stage20_ema13_slope"] = ema_13 / ema_13.shift(12) - 1
        dataframe["stage20_ema34_slope"] = ema_34 / ema_34.shift(24) - 1
        dataframe["stage20_vwap60_dist"] = close / dataframe["stage19_vwap_60"] - 1

        trend_long = (
            0.24 * (close > ema_13).astype(float)
            + 0.22 * (ema_13 > ema_34).astype(float)
            + 0.16 * (ema_34 > ema_89).astype(float)
            + 0.18 * self._score(dataframe["stage20_ema13_slope"].fillna(0.0), 0.0002, 0.012)
            + 0.12 * self._score(dataframe["stage19_roc_30"].fillna(0.0), 0.003, 0.050)
            + 0.08 * self._score(dataframe["stage20_vwap60_dist"].fillna(0.0), -0.004, 0.020)
        )
        trend_short = (
            0.24 * (close < ema_13).astype(float)
            + 0.22 * (ema_13 < ema_34).astype(float)
            + 0.16 * (ema_34 < ema_89).astype(float)
            + 0.18 * self._score(-dataframe["stage20_ema13_slope"].fillna(0.0), 0.0002, 0.012)
            + 0.12 * self._score(-dataframe["stage19_roc_30"].fillna(0.0), 0.003, 0.050)
            + 0.08 * self._score(-dataframe["stage20_vwap60_dist"].fillna(0.0), -0.004, 0.020)
        )
        dataframe["stage20_trend_long"] = trend_long.clip(0.0, 1.0)
        dataframe["stage20_trend_short"] = trend_short.clip(0.0, 1.0)

        candle_range = (high - low).replace(0, np.nan)
        close_pos = ((close - low) / candle_range).clip(0.0, 1.0).fillna(0.5)
        body_ratio = self._safe_div((close - open_).abs(), candle_range).clip(0.0, 1.0)
        wick_ratio = self._safe_div(
            dataframe["stage19_upper_wick_pct"] + dataframe["stage19_lower_wick_pct"],
            dataframe["stage19_body_pct"] + 0.0005,
        ).clip(0.0, 5.0)
        alternating = (
            np.sign(close.diff()).replace(0, np.nan)
            != np.sign(close.diff().shift(1)).replace(0, np.nan)
        )
        alternating_rate = alternating.astype(float).rolling(16, min_periods=6).mean()
        dataframe["stage20_close_pos"] = close_pos
        dataframe["stage20_body_ratio"] = body_ratio
        dataframe["stage20_chop_risk"] = (
            0.30 * (1.0 - dataframe[["stage20_trend_long", "stage20_trend_short"]].max(axis=1))
            + 0.25 * self._score(wick_ratio.fillna(1.0), 1.2, 3.8)
            + 0.20 * self._score(alternating_rate.fillna(0.5), 0.45, 0.78)
            + 0.15
            * self._score(
                (width_mean / width.replace(0, np.nan))
                .replace([np.inf, -np.inf], np.nan)
                .fillna(1.0),
                1.05,
                2.40,
            )
            + 0.10 * (1.0 - body_ratio.fillna(0.5))
        ).clip(0.0, 1.0)
        dataframe["stage20_exhaustion_long"] = (
            0.44 * self._score(dataframe["stage19_rsi_7"].fillna(50.0), 72, 89)
            + 0.34
            * self._score(
                dataframe["stage19_upper_wick_pct"].fillna(0.0)
                / (dataframe["stage19_body_pct"].fillna(0.0) + 0.0008),
                1.0,
                3.5,
            )
            + 0.22 * self._score(dataframe["stage19_roc_15"].fillna(0.0), 0.030, 0.085)
        ).clip(0.0, 1.0)
        dataframe["stage20_exhaustion_short"] = (
            0.44 * self._score(100 - dataframe["stage19_rsi_7"].fillna(50.0), 72, 89)
            + 0.34
            * self._score(
                dataframe["stage19_lower_wick_pct"].fillna(0.0)
                / (dataframe["stage19_body_pct"].fillna(0.0) + 0.0008),
                1.0,
                3.5,
            )
            + 0.22 * self._score(-dataframe["stage19_roc_15"].fillna(0.0), 0.030, 0.085)
        ).clip(0.0, 1.0)

        btc_context = self._stage20_btc_context()
        if not btc_context.empty and "date" in dataframe:
            dataframe = dataframe.merge(btc_context, on="date", how="left")
            for column, default in (
                ("stage20_btc_bias", 0.0),
                ("stage20_btc_trend", 0.0),
                ("stage20_btc_risk", 0.5),
            ):
                dataframe[column] = dataframe[column].ffill().fillna(default)
        else:
            dataframe["stage20_btc_bias"] = 0.0
            dataframe["stage20_btc_trend"] = 0.0
            dataframe["stage20_btc_risk"] = 0.5

        raw_common = (
            (atr > 0.00055)
            & (atr < 0.060)
            & (dataframe["stage19_volume_ratio"].fillna(1.0) > 0.72)
            & (dataframe["stage20_chop_risk"].fillna(1.0) < 0.82)
        )
        raw_momo_long = (
            raw_common
            & (dataframe["stage20_trend_long"] > 0.52)
            & (dataframe["stage19_hot_score"].fillna(0.0) > 0.38)
            & (close > dataframe["stage19_don_high_20"] * 1.0002)
            & (dataframe["stage19_roc_8"] > 0.0018)
            & (dataframe["stage20_exhaustion_long"] < 0.82)
        )
        raw_momo_short = (
            raw_common
            & (dataframe["stage20_trend_short"] > 0.52)
            & (dataframe["stage19_hot_score"].fillna(0.0) > 0.38)
            & (close < dataframe["stage19_don_low_20"] * 0.9998)
            & (dataframe["stage19_roc_8"] < -0.0018)
            & (dataframe["stage20_exhaustion_short"] < 0.82)
        )
        raw_pull_long = (
            raw_common
            & (dataframe["stage20_trend_long"] > 0.62)
            & (dataframe["stage19_roc_30"] > 0.006)
            & (dataframe["stage19_roc_3"] > 0.0006)
            & (low < ema_13 * 1.0015)
            & (close > dataframe["stage19_vwap_20"])
            & (dataframe["stage19_rsi_3"].between(34, 68))
            & (dataframe["stage20_exhaustion_long"] < 0.70)
        )
        raw_pull_short = (
            raw_common
            & (dataframe["stage20_trend_short"] > 0.62)
            & (dataframe["stage19_roc_30"] < -0.006)
            & (dataframe["stage19_roc_3"] < -0.0006)
            & (high > ema_13 * 0.9985)
            & (close < dataframe["stage19_vwap_20"])
            & (dataframe["stage19_rsi_3"].between(32, 66))
            & (dataframe["stage20_exhaustion_short"] < 0.70)
        )

        future_ready_long = close / close.shift(self.stage20_memory_horizon) - 1
        future_ready_short = close.shift(self.stage20_memory_horizon) / close - 1
        long_result = future_ready_long - self.stage20_fee_drag
        short_result = future_ready_short - self.stage20_fee_drag

        momo_long_memory_mask = raw_momo_long.shift(self.stage20_memory_horizon).fillna(False)
        momo_short_memory_mask = raw_momo_short.shift(self.stage20_memory_horizon).fillna(False)
        pull_long_memory_mask = raw_pull_long.shift(self.stage20_memory_horizon).fillna(False)
        pull_short_memory_mask = raw_pull_short.shift(self.stage20_memory_horizon).fillna(False)

        long_edge_momo, long_count_momo = self._rolling_mean_when(
            long_result,
            momo_long_memory_mask,
            self.stage20_memory_window,
        )
        short_edge_momo, short_count_momo = self._rolling_mean_when(
            short_result,
            momo_short_memory_mask,
            self.stage20_memory_window,
        )
        long_edge_pull, long_count_pull = self._rolling_mean_when(
            long_result,
            pull_long_memory_mask,
            self.stage20_memory_window,
        )
        short_edge_pull, short_count_pull = self._rolling_mean_when(
            short_result,
            pull_short_memory_mask,
            self.stage20_memory_window,
        )

        long_edge_momo_slow, long_count_momo_slow = self._rolling_mean_when(
            long_result,
            momo_long_memory_mask,
            self.stage20_slow_memory_window,
            min_periods=30,
        )
        short_edge_momo_slow, short_count_momo_slow = self._rolling_mean_when(
            short_result,
            momo_short_memory_mask,
            self.stage20_slow_memory_window,
            min_periods=30,
        )
        long_edge_pull_slow, long_count_pull_slow = self._rolling_mean_when(
            long_result,
            pull_long_memory_mask,
            self.stage20_slow_memory_window,
            min_periods=30,
        )
        short_edge_pull_slow, short_count_pull_slow = self._rolling_mean_when(
            short_result,
            pull_short_memory_mask,
            self.stage20_slow_memory_window,
            min_periods=30,
        )

        long_win_value = (long_result > 0).astype(float)
        short_win_value = (short_result > 0).astype(float)
        long_win_momo, _ = self._rolling_mean_when(
            long_win_value,
            momo_long_memory_mask,
            self.stage20_memory_window,
        )
        short_win_momo, _ = self._rolling_mean_when(
            short_win_value,
            momo_short_memory_mask,
            self.stage20_memory_window,
        )
        long_win_pull, _ = self._rolling_mean_when(
            long_win_value,
            pull_long_memory_mask,
            self.stage20_memory_window,
        )
        short_win_pull, _ = self._rolling_mean_when(
            short_win_value,
            pull_short_memory_mask,
            self.stage20_memory_window,
        )

        dataframe["stage20_momo_edge_long"] = long_edge_momo
        dataframe["stage20_momo_edge_short"] = short_edge_momo
        dataframe["stage20_pull_edge_long"] = long_edge_pull
        dataframe["stage20_pull_edge_short"] = short_edge_pull
        dataframe["stage20_momo_edge_long_slow"] = long_edge_momo_slow
        dataframe["stage20_momo_edge_short_slow"] = short_edge_momo_slow
        dataframe["stage20_pull_edge_long_slow"] = long_edge_pull_slow
        dataframe["stage20_pull_edge_short_slow"] = short_edge_pull_slow
        dataframe["stage20_momo_count_long"] = long_count_momo
        dataframe["stage20_momo_count_short"] = short_count_momo
        dataframe["stage20_pull_count_long"] = long_count_pull
        dataframe["stage20_pull_count_short"] = short_count_pull
        dataframe["stage20_momo_count_long_slow"] = long_count_momo_slow
        dataframe["stage20_momo_count_short_slow"] = short_count_momo_slow
        dataframe["stage20_pull_count_long_slow"] = long_count_pull_slow
        dataframe["stage20_pull_count_short_slow"] = short_count_pull_slow
        dataframe["stage20_momo_win_long"] = long_win_momo
        dataframe["stage20_momo_win_short"] = short_win_momo
        dataframe["stage20_pull_win_long"] = long_win_pull
        dataframe["stage20_pull_win_short"] = short_win_pull
        dataframe["stage20_edge_long"] = pd.concat([long_edge_momo, long_edge_pull], axis=1).max(
            axis=1,
        )
        dataframe["stage20_edge_short"] = pd.concat([short_edge_momo, short_edge_pull], axis=1).max(
            axis=1,
        )
        dataframe["stage20_edge_long_slow"] = pd.concat(
            [long_edge_momo_slow, long_edge_pull_slow],
            axis=1,
        ).max(axis=1)
        dataframe["stage20_edge_short_slow"] = pd.concat(
            [short_edge_momo_slow, short_edge_pull_slow],
            axis=1,
        ).max(axis=1)
        dataframe["stage20_winrate_long"] = pd.concat([long_win_momo, long_win_pull], axis=1).max(
            axis=1,
        )
        dataframe["stage20_winrate_short"] = pd.concat(
            [short_win_momo, short_win_pull],
            axis=1,
        ).max(axis=1)
        dataframe["stage20_memory_long_count"] = pd.concat(
            [long_count_momo, long_count_pull],
            axis=1,
        ).max(axis=1)
        dataframe["stage20_memory_short_count"] = pd.concat(
            [short_count_momo, short_count_pull],
            axis=1,
        ).max(axis=1)

        long_edge_score = (
            0.62 * self._score(dataframe["stage20_edge_long"].fillna(0.0), -0.0018, 0.0060)
            + 0.25
            * self._score(dataframe["stage20_edge_long_slow"].fillna(0.0), -0.0010, 0.0035)
            + 0.13 * self._score(dataframe["stage20_winrate_long"].fillna(0.5), 0.46, 0.62)
        ).clip(0.0, 1.0)
        short_edge_score = (
            0.62 * self._score(dataframe["stage20_edge_short"].fillna(0.0), -0.0018, 0.0060)
            + 0.25
            * self._score(dataframe["stage20_edge_short_slow"].fillna(0.0), -0.0010, 0.0035)
            + 0.13 * self._score(dataframe["stage20_winrate_short"].fillna(0.5), 0.46, 0.62)
        ).clip(0.0, 1.0)

        slow_long_sample = pd.concat([long_count_momo_slow, long_count_pull_slow], axis=1).max(
            axis=1,
        )
        slow_short_sample = pd.concat([short_count_momo_slow, short_count_pull_slow], axis=1).max(
            axis=1,
        )
        long_sample_score = (dataframe["stage20_memory_long_count"].fillna(0.0) / 8.0).clip(
            0.20,
            1.0,
        )
        long_sample_score = (0.72 * long_sample_score + 0.28 * (slow_long_sample / 18.0)).clip(
            0.20,
            1.0,
        )
        short_sample_score = (dataframe["stage20_memory_short_count"].fillna(0.0) / 8.0).clip(
            0.20,
            1.0,
        )
        short_sample_score = (0.72 * short_sample_score + 0.28 * (slow_short_sample / 18.0)).clip(
            0.20,
            1.0,
        )
        market_long = (
            0.70
            + 0.20 * dataframe["stage20_btc_bias"].clip(-1.0, 1.0)
            + 0.10 * dataframe["stage20_btc_trend"].clip(-1.0, 1.0)
            - 0.22 * dataframe["stage20_btc_risk"].clip(0.0, 1.0)
        ).clip(0.35, 1.05)
        market_short = (
            0.70
            - 0.20 * dataframe["stage20_btc_bias"].clip(-1.0, 1.0)
            - 0.10 * dataframe["stage20_btc_trend"].clip(-1.0, 1.0)
            - 0.22 * dataframe["stage20_btc_risk"].clip(0.0, 1.0)
        ).clip(0.35, 1.05)

        dataframe["stage20_adaptive_long"] = (
            (
                0.34 * dataframe["stage20_trend_long"].fillna(0.0)
                + 0.23 * dataframe["stage19_hot_score"].fillna(0.0)
                + 0.20 * long_edge_score
                + 0.10 * long_sample_score
                + 0.08 * dataframe["stage20_age_score"].fillna(0.35)
                + 0.05 * (1.0 - dataframe["stage20_chop_risk"].fillna(1.0))
            )
            * market_long
        ).clip(0.0, 1.0)
        dataframe["stage20_adaptive_short"] = (
            (
                0.34 * dataframe["stage20_trend_short"].fillna(0.0)
                + 0.23 * dataframe["stage19_hot_score"].fillna(0.0)
                + 0.20 * short_edge_score
                + 0.10 * short_sample_score
                + 0.08 * dataframe["stage20_age_score"].fillna(0.35)
                + 0.05 * (1.0 - dataframe["stage20_chop_risk"].fillna(1.0))
            )
            * market_short
        ).clip(0.0, 1.0)

        dataframe["stage20_raw_momo_long"] = raw_momo_long
        dataframe["stage20_raw_momo_short"] = raw_momo_short
        dataframe["stage20_raw_pull_long"] = raw_pull_long
        dataframe["stage20_raw_pull_short"] = raw_pull_short
        dataframe["stage20_momo_long_promoted"] = (
            (long_count_momo >= 8)
            & (long_edge_momo > 0.0012)
            & ((long_count_momo_slow < 14) | (long_edge_momo_slow > -0.00015))
            & (long_win_momo.fillna(0.5) >= 0.54)
        )
        dataframe["stage20_pull_long_promoted"] = (
            bool(self.stage20_enable_pull_learning_entries)
            & (long_count_pull >= 8)
            & (long_edge_pull > 0.0010)
            & ((long_count_pull_slow < 14) | (long_edge_pull_slow > -0.00015))
            & (long_win_pull.fillna(0.5) >= 0.53)
        )
        dataframe["stage20_momo_short_promoted"] = (
            bool(self.stage20_enable_short_learning_entries)
            & (short_count_momo >= 12)
            & (short_edge_momo > 0.0018)
            & (short_count_momo_slow >= 18)
            & (short_edge_momo_slow > 0.00025)
            & (short_win_momo.fillna(0.5) >= 0.56)
        )
        dataframe["stage20_pull_short_promoted"] = (
            bool(self.stage20_enable_short_learning_entries)
            & bool(self.stage20_enable_pull_learning_entries)
            & (short_count_pull >= 12)
            & (short_edge_pull > 0.0018)
            & (short_count_pull_slow >= 18)
            & (short_edge_pull_slow > 0.00025)
            & (short_win_pull.fillna(0.5) >= 0.56)
        )
        return dataframe

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
        rsi_7 = dataframe["stage19_rsi_7"].fillna(50.0)

        common_risk = (
            (atr > 0.00065)
            & (atr < 0.045)
            & (volume_ratio > 0.78)
            & (dataframe["stage20_chop_risk"].fillna(1.0) < 0.60)
            & (dataframe["stage20_btc_risk"].fillna(0.5) < 0.86)
        )
        market_long_ok = (dataframe["stage20_btc_bias"] > -0.35) & (
            dataframe["stage20_btc_trend"] > -0.45
        )
        market_short_ok = (
            ((dataframe["stage20_btc_bias"] < -0.12) | (dataframe["stage20_btc_trend"] < -0.18))
            & (dataframe["stage19_roc_60"] < -0.010)
        )
        no_stage_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        momo_long = (
            no_stage_entry
            & common_risk
            & market_long_ok
            & dataframe["stage20_momo_long_promoted"].fillna(False)
            & dataframe["stage20_raw_momo_long"].fillna(False)
            & (dataframe["stage20_adaptive_long"] > 0.66)
            & (dataframe["stage20_trend_long"] > 0.64)
            & (risk < 0.76)
            & (hot > 0.48)
            & (volume_ratio > 1.16)
            & (dataframe["stage19_roc_3"] > 0.0010)
            & (dataframe["stage19_roc_8"] > 0.0022)
            & (dataframe["stage19_roc_60"] > -0.020)
            & (rsi_7 > 51)
            & (rsi_7 < 78)
            & (dataframe["stage20_close_pos"] > 0.48)
            & (dataframe["stage20_exhaustion_long"] < 0.72)
        )
        dataframe.loc[momo_long, ["enter_long", "enter_tag"]] = (1, "s20_momo_l_h12m_l7")

        no_stage_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        momo_short = (
            no_stage_entry
            & common_risk
            & market_short_ok
            & dataframe["stage20_momo_short_promoted"].fillna(False)
            & dataframe["stage20_raw_momo_short"].fillna(False)
            & (dataframe["stage20_adaptive_short"] > 0.76)
            & (dataframe["stage20_trend_short"] > 0.72)
            & (risk < 0.70)
            & (hot > 0.54)
            & (volume_ratio > 1.24)
            & (dataframe["stage19_roc_3"] < -0.0010)
            & (dataframe["stage19_roc_8"] < -0.0022)
            & (dataframe["stage19_roc_60"] < 0.020)
            & (rsi_7 < 49)
            & (rsi_7 > 22)
            & (dataframe["stage20_close_pos"] < 0.52)
            & (dataframe["stage20_exhaustion_short"] < 0.72)
        )
        dataframe.loc[momo_short, ["enter_short", "enter_tag"]] = (1, "s20_momo_s_h12m_l7")

        no_stage_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        pull_long = (
            no_stage_entry
            & common_risk
            & market_long_ok
            & dataframe["stage20_pull_long_promoted"].fillna(False)
            & dataframe["stage20_raw_pull_long"].fillna(False)
            & (dataframe["stage20_adaptive_long"] > 0.68)
            & (dataframe["stage20_trend_long"] > 0.68)
            & (risk < 0.70)
            & (hot > 0.42)
            & (dataframe["stage19_roc_60"] > 0.004)
            & (dataframe["stage20_btc_bias"] > -0.42)
            & (dataframe["stage20_exhaustion_long"] < 0.62)
        )
        dataframe.loc[pull_long, ["enter_long", "enter_tag"]] = (1, "s20_pull_l_h10m_l6")

        no_stage_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        pull_short = (
            no_stage_entry
            & common_risk
            & market_short_ok
            & dataframe["stage20_pull_short_promoted"].fillna(False)
            & dataframe["stage20_raw_pull_short"].fillna(False)
            & (dataframe["stage20_adaptive_short"] > 0.78)
            & (dataframe["stage20_trend_short"] > 0.72)
            & (risk < 0.68)
            & (hot > 0.48)
            & (dataframe["stage19_roc_60"] < -0.004)
            & (dataframe["stage20_btc_bias"] < 0.42)
            & (dataframe["stage20_exhaustion_short"] < 0.62)
        )
        dataframe.loc[pull_short, ["enter_short", "enter_tag"]] = (1, "s20_pull_s_h10m_l6")
        return dataframe

    def _stage20_scores(
        self,
        pair: str,
        current_time: datetime | None,
        family: str = "blend",
    ) -> dict[str, float]:
        scores = {
            "long": 0.45,
            "short": 0.45,
            "risk": 0.5,
            "edge_long": 0.0,
            "edge_short": 0.0,
            "edge_long_slow": 0.0,
            "edge_short_slow": 0.0,
            "win_long": 0.5,
            "win_short": 0.5,
            "count_long": 0.0,
            "count_short": 0.0,
            "count_long_slow": 0.0,
            "count_short_slow": 0.0,
            "age": 0.35,
            "chop": 0.5,
            "btc_risk": 0.5,
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
        family = family if family in {"momo", "pull"} else "blend"
        scores["long"] = self._bounded(float(row.get("stage20_adaptive_long", 0.45)))
        scores["short"] = self._bounded(float(row.get("stage20_adaptive_short", 0.45)))
        scores["risk"] = self._bounded(float(row.get("stage19_overheat_score", 0.5)))
        if family == "blend":
            scores["edge_long"] = float(row.get("stage20_edge_long", 0.0) or 0.0)
            scores["edge_short"] = float(row.get("stage20_edge_short", 0.0) or 0.0)
            scores["edge_long_slow"] = float(row.get("stage20_edge_long_slow", 0.0) or 0.0)
            scores["edge_short_slow"] = float(row.get("stage20_edge_short_slow", 0.0) or 0.0)
            scores["win_long"] = self._bounded(float(row.get("stage20_winrate_long", 0.5) or 0.5))
            scores["win_short"] = self._bounded(
                float(row.get("stage20_winrate_short", 0.5) or 0.5),
            )
            scores["count_long"] = float(row.get("stage20_memory_long_count", 0.0) or 0.0)
            scores["count_short"] = float(row.get("stage20_memory_short_count", 0.0) or 0.0)
            scores["count_long_slow"] = max(
                float(row.get("stage20_momo_count_long_slow", 0.0) or 0.0),
                float(row.get("stage20_pull_count_long_slow", 0.0) or 0.0),
            )
            scores["count_short_slow"] = max(
                float(row.get("stage20_momo_count_short_slow", 0.0) or 0.0),
                float(row.get("stage20_pull_count_short_slow", 0.0) or 0.0),
            )
        else:
            scores["edge_long"] = float(row.get(f"stage20_{family}_edge_long", 0.0) or 0.0)
            scores["edge_short"] = float(row.get(f"stage20_{family}_edge_short", 0.0) or 0.0)
            scores["edge_long_slow"] = float(
                row.get(f"stage20_{family}_edge_long_slow", 0.0) or 0.0,
            )
            scores["edge_short_slow"] = float(
                row.get(f"stage20_{family}_edge_short_slow", 0.0) or 0.0,
            )
            scores["win_long"] = self._bounded(
                float(row.get(f"stage20_{family}_win_long", 0.5) or 0.5),
            )
            scores["win_short"] = self._bounded(
                float(row.get(f"stage20_{family}_win_short", 0.5) or 0.5),
            )
            scores["count_long"] = float(row.get(f"stage20_{family}_count_long", 0.0) or 0.0)
            scores["count_short"] = float(row.get(f"stage20_{family}_count_short", 0.0) or 0.0)
            scores["count_long_slow"] = float(
                row.get(f"stage20_{family}_count_long_slow", 0.0) or 0.0,
            )
            scores["count_short_slow"] = float(
                row.get(f"stage20_{family}_count_short_slow", 0.0) or 0.0,
            )
        scores["age"] = self._bounded(float(row.get("stage20_age_score", 0.35)), 0.35, 1.0)
        scores["chop"] = self._bounded(float(row.get("stage20_chop_risk", 0.5)))
        scores["btc_risk"] = self._bounded(float(row.get("stage20_btc_risk", 0.5)))
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
        if not self._is_stage20_tag(entry_tag):
            return True

        scores = self._stage20_scores(pair, current_time, self._stage20_tag_family(entry_tag))
        side_score = scores["long"] if side == "long" else scores["short"]
        side_edge = scores["edge_long"] if side == "long" else scores["edge_short"]
        side_count = scores["count_long"] if side == "long" else scores["count_short"]
        side_edge_slow = scores["edge_long_slow"] if side == "long" else scores["edge_short_slow"]
        side_count_slow = (
            scores["count_long_slow"] if side == "long" else scores["count_short_slow"]
        )
        side_win = scores["win_long"] if side == "long" else scores["win_short"]
        if side_score < 0.54:
            return False
        if side_count >= 6 and side_edge < -0.0014:
            return False
        if side_count >= 8 and side_win < 0.50:
            return False
        if side_count_slow >= 14 and side_edge_slow < -0.00025:
            return False
        if scores["btc_risk"] > 0.94 and side_score < 0.62:
            return False
        if scores["risk"] > 0.88 and scores["chop"] > 0.56 and side_score < 0.62:
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
        if stake is None or not self._is_stage20_tag(entry_tag):
            return stake

        scores = self._stage20_scores(pair, current_time, self._stage20_tag_family(entry_tag))
        side_score = scores["long"] if side == "long" else scores["short"]
        side_edge = scores["edge_long"] if side == "long" else scores["edge_short"]
        side_count = scores["count_long"] if side == "long" else scores["count_short"]
        side_edge_slow = scores["edge_long_slow"] if side == "long" else scores["edge_short_slow"]
        side_count_slow = (
            scores["count_long_slow"] if side == "long" else scores["count_short_slow"]
        )
        side_win = scores["win_long"] if side == "long" else scores["win_short"]

        tag_boost = 1.18 if entry_tag and "_momo_" in entry_tag else 1.06
        sample_factor = 0.74 + min(side_count / 12.0, 1.0) * 0.18
        sample_factor += min(side_count_slow / 24.0, 1.0) * 0.08
        edge_factor = 1.0 + self._bounded(side_edge, -0.006, 0.008) * 19.0
        multiplier = self._stage20_pair_weight(pair) * tag_boost
        multiplier *= 0.54 + side_score * 0.48
        multiplier *= sample_factor
        multiplier *= edge_factor
        multiplier *= 0.88 + max(side_win - 0.52, 0.0) * 0.80
        multiplier *= 1.0 - max(scores["risk"] - 0.72, 0.0) * 0.84
        multiplier *= 1.0 - max(scores["chop"] - 0.46, 0.0) * 0.62
        multiplier *= scores["age"]
        if side_count < 8:
            multiplier *= 0.72
        if side_edge < 0.0010:
            multiplier *= 0.78
        if side_count_slow >= 14 and side_edge_slow < 0.00015:
            multiplier *= 0.72
        multiplier = self._bounded(multiplier, 0.20, 0.78)

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
        if not self._is_stage20_tag(entry_tag):
            return max(1.0, min(target, max_leverage, self.max_stage20_leverage))

        tag_leverage = self._stage20_tag_leverage(entry_tag)
        if tag_leverage is not None:
            target = max(target, tag_leverage)
        scores = self._stage20_scores(pair, current_time, self._stage20_tag_family(entry_tag))
        side_score = scores["long"] if side == "long" else scores["short"]
        side_edge = scores["edge_long"] if side == "long" else scores["edge_short"]
        side_count = scores["count_long"] if side == "long" else scores["count_short"]
        side_edge_slow = scores["edge_long_slow"] if side == "long" else scores["edge_short_slow"]
        side_count_slow = (
            scores["count_long_slow"] if side == "long" else scores["count_short_slow"]
        )
        if side_score > 0.72 and side_edge > 0.0018 and side_count >= 8:
            target += 0.25
        if side_score < 0.52 or scores["risk"] > 0.84 or scores["btc_risk"] > 0.90:
            target -= 0.65
        if side_count < 3:
            target -= 0.45
        if side_count_slow >= 14 and side_edge_slow < 0.0001:
            target -= 0.35
        if pair.startswith(self.stage20_core_prefixes):
            target -= 0.35
        return max(1.0, min(target, max_leverage, self.max_stage20_leverage))

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool | None:
        if not self._is_stage20_tag(trade.enter_tag):
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
        side_edge_slow = scores["edge_short_slow"] if trade.is_short else scores["edge_long_slow"]
        side_count_slow = (
            scores["count_short_slow"] if trade.is_short else scores["count_long_slow"]
        )
        side_win = scores["win_short"] if trade.is_short else scores["win_long"]

        if current_profit >= 0.017:
            return "stage20_fast_profit_exit"
        if trade_minutes >= 4 and current_profit >= 0.009 and side_score < 0.50:
            return "stage20_adaptive_take_profit"
        if trade_minutes >= 3 and current_profit <= -0.016:
            return "stage20_fast_loss_exit"
        if side_count >= 6 and side_edge < 0.0002 and current_profit <= -0.004:
            return "stage20_memory_edge_exit"
        if side_count >= 8 and side_win < 0.48 and current_profit <= -0.003:
            return "stage20_winrate_decay_exit"
        if side_count_slow >= 14 and side_edge_slow < -0.00025 and current_profit <= -0.003:
            return "stage20_slow_memory_decay_exit"
        if scores["risk"] > 0.80 and scores["chop"] > 0.52 and current_profit <= -0.006:
            return "stage20_regime_risk_exit"
        if trade_minutes >= hold_minutes:
            return "stage20_fixed_hold_exit"
        return super().custom_exit(
            pair,
            trade,
            current_time,
            current_rate,
            current_profit,
            **kwargs,
        )
