from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from Intp20Stage19AggressiveNewcoinStrategy import Intp20Stage19AggressiveNewcoinStrategy
from pandas import DataFrame


class Intp20Stage20AdaptiveRegimeNewcoinStrategy(Intp20Stage19AggressiveNewcoinStrategy):
    """
    Stage-20 new-coin pulse / liquidity-sweep strategy.

    Stage-20 keeps the Stage-18/19 indicator stack but does not reuse their
    entries.  It specializes in high-beta/new futures names with three separate
    sleeves: impulse continuation, liquidity sweeps, and VWAP mean reversion.
    This keeps it materially different from Stage-17's mature-market trend
    reaction and Stage-24's broad robust pulse portfolio.
    """

    startup_candle_count = 180
    stoploss = -0.04

    order_types = {
        "entry": "limit",
        "exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    max_stake_multiplier = 3.00
    min_stake_multiplier = 0.32
    max_stage19_leverage = 6.2
    max_stage20_leverage = 6.2

    stage19_momentum_long_prefixes: tuple[str, ...] = ()
    stage19_momentum_short_prefixes: tuple[str, ...] = ()
    stage19_squeeze_prefixes: tuple[str, ...] = ()
    stage19_snap_prefixes: tuple[str, ...] = ()

    stage20_core_prefixes = ("BTC/", "ETH/", "BNB/", "TRX/")
    stage20_high_beta_prefixes = (
        "1000BONK/",
        "1000FLOKI/",
        "1000PEPE/",
        "1000SATS/",
        "1000SHIB/",
        "ACT/",
        "AEVO/",
        "AI/",
        "AIXBT/",
        "ALT/",
        "APE/",
        "APT/",
        "ARB/",
        "BERA/",
        "BOME/",
        "COW/",
        "CRV/",
        "DEGEN/",
        "DOGE/",
        "EIGEN/",
        "ENA/",
        "ETHFI/",
        "FARTCOIN/",
        "FET/",
        "GALA/",
        "GOAT/",
        "GRASS/",
        "INJ/",
        "JUP/",
        "JTO/",
        "KAITO/",
        "LDO/",
        "MEME/",
        "MERL/",
        "MEW/",
        "MOODENG/",
        "NOT/",
        "ONDO/",
        "ORDI/",
        "PENDLE/",
        "PEOPLE/",
        "PNUT/",
        "OP/",
        "POPCAT/",
        "PUMP/",
        "PYTH/",
        "RENDER/",
        "SCR/",
        "SEI/",
        "SHELL/",
        "STRK/",
        "SUI/",
        "TAO/",
        "TIA/",
        "TON/",
        "TURBO/",
        "VIRTUAL/",
        "W/",
        "WIF/",
        "WLD/",
        "ZK/",
        "ZRO/",
    )

    stage20_memory_window = 540
    stage20_slow_memory_window = 1440
    stage20_memory_horizon = 6
    stage20_fee_drag = 0.00170
    stage20_enable_short_learning_entries = True
    stage20_enable_pull_learning_entries = False

    stage20_sweep_prefixes = (
        "1000BONK/",
        "1000FLOKI/",
        "1000PEPE/",
        "1000SATS/",
        "1000SHIB/",
        "AAVE/",
        "ACT/",
        "AEVO/",
        "AI/",
        "AIXBT/",
        "ALT/",
        "APE/",
        "APT/",
        "BOME/",
        "COW/",
        "CRV/",
        "DEGEN/",
        "DOGE/",
        "EIGEN/",
        "ENA/",
        "ETHFI/",
        "FARTCOIN/",
        "FET/",
        "GALA/",
        "GOAT/",
        "GRASS/",
        "HBAR/",
        "INJ/",
        "JUP/",
        "JTO/",
        "KAITO/",
        "LDO/",
        "MANA/",
        "MEME/",
        "MERL/",
        "MEW/",
        "MOODENG/",
        "NOT/",
        "ONDO/",
        "ORDI/",
        "PENDLE/",
        "PEOPLE/",
        "PNUT/",
        "OP/",
        "POPCAT/",
        "PUMP/",
        "PYTH/",
        "RENDER/",
        "RUNE/",
        "SAND/",
        "SCR/",
        "SEI/",
        "SHELL/",
        "STRK/",
        "SUI/",
        "TAO/",
        "TIA/",
        "TON/",
        "TURBO/",
        "VIRTUAL/",
        "W/",
        "WIF/",
        "WLD/",
        "XLM/",
        "XRP/",
        "XTZ/",
        "ZK/",
        "ZRO/",
    )
    stage20_pulse_long_prefixes = (
        "1000BONK/",
        "1000FLOKI/",
        "1000PEPE/",
        "1000SHIB/",
        "APE/",
        "BERA/",
        "BOME/",
        "FARTCOIN/",
        "GOAT/",
        "GRASS/",
        "JUP/",
        "KAITO/",
        "MEME/",
        "MERL/",
        "MEW/",
        "MOODENG/",
        "ORDI/",
        "PNUT/",
        "POPCAT/",
        "PUMP/",
        "SUI/",
        "TURBO/",
        "VIRTUAL/",
        "WIF/",
        "WLD/",
        "ZRO/",
    )
    stage20_pulse_short_prefixes = (
        "1000BONK/",
        "1000FLOKI/",
        "1000PEPE/",
        "AI/",
        "ALT/",
        "ARB/",
        "BERA/",
        "BOME/",
        "COW/",
        "ETHFI/",
        "FARTCOIN/",
        "FET/",
        "JTO/",
        "MERL/",
        "MOODENG/",
        "NOT/",
        "ONDO/",
        "PNUT/",
        "POPCAT/",
        "PUMP/",
        "RENDER/",
        "SEI/",
        "SHELL/",
        "TIA/",
        "TURBO/",
        "W/",
        "WIF/",
        "ZK/",
    )
    stage20_sweep_short_prefixes = (
        "AIXBT/",
        "ARB/",
        "COW/",
        "ETHFI/",
        "JTO/",
        "LDO/",
        "MERL/",
        "MOODENG/",
        "ONDO/",
        "PENDLE/",
        "PNUT/",
        "POPCAT/",
        "RENDER/",
        "SHELL/",
        "TURBO/",
        "W/",
        "ZK/",
    )

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
        if entry_tag and ("_momo_" in entry_tag or "_pulse_" in entry_tag):
            return "momo"
        if entry_tag and "_pull_" in entry_tag:
            return "pull"
        if entry_tag and ("_sweep_" in entry_tag or "_vwaprev_" in entry_tag):
            return "pull"
        return "blend"

    @classmethod
    def _stage20_pair_weight(cls, pair: str) -> float:
        if pair.startswith(cls.stage20_sweep_prefixes):
            return 1.14
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

        stage20_edge_long = pd.concat([long_edge_momo, long_edge_pull], axis=1).max(axis=1)
        stage20_edge_short = pd.concat([short_edge_momo, short_edge_pull], axis=1).max(axis=1)
        stage20_edge_long_slow = pd.concat(
            [long_edge_momo_slow, long_edge_pull_slow],
            axis=1,
        ).max(axis=1)
        stage20_edge_short_slow = pd.concat(
            [short_edge_momo_slow, short_edge_pull_slow],
            axis=1,
        ).max(axis=1)
        stage20_winrate_long = pd.concat([long_win_momo, long_win_pull], axis=1).max(axis=1)
        stage20_winrate_short = pd.concat(
            [short_win_momo, short_win_pull],
            axis=1,
        ).max(axis=1)
        stage20_memory_long_count = pd.concat(
            [long_count_momo, long_count_pull],
            axis=1,
        ).max(axis=1)
        stage20_memory_short_count = pd.concat(
            [short_count_momo, short_count_pull],
            axis=1,
        ).max(axis=1)

        dataframe = pd.concat(
            [
                dataframe,
                DataFrame(
                    {
                        "stage20_momo_edge_long": long_edge_momo,
                        "stage20_momo_edge_short": short_edge_momo,
                        "stage20_pull_edge_long": long_edge_pull,
                        "stage20_pull_edge_short": short_edge_pull,
                        "stage20_momo_edge_long_slow": long_edge_momo_slow,
                        "stage20_momo_edge_short_slow": short_edge_momo_slow,
                        "stage20_pull_edge_long_slow": long_edge_pull_slow,
                        "stage20_pull_edge_short_slow": short_edge_pull_slow,
                        "stage20_momo_count_long": long_count_momo,
                        "stage20_momo_count_short": short_count_momo,
                        "stage20_pull_count_long": long_count_pull,
                        "stage20_pull_count_short": short_count_pull,
                        "stage20_momo_count_long_slow": long_count_momo_slow,
                        "stage20_momo_count_short_slow": short_count_momo_slow,
                        "stage20_pull_count_long_slow": long_count_pull_slow,
                        "stage20_pull_count_short_slow": short_count_pull_slow,
                        "stage20_momo_win_long": long_win_momo,
                        "stage20_momo_win_short": short_win_momo,
                        "stage20_pull_win_long": long_win_pull,
                        "stage20_pull_win_short": short_win_pull,
                        "stage20_edge_long": stage20_edge_long,
                        "stage20_edge_short": stage20_edge_short,
                        "stage20_edge_long_slow": stage20_edge_long_slow,
                        "stage20_edge_short_slow": stage20_edge_short_slow,
                        "stage20_winrate_long": stage20_winrate_long,
                        "stage20_winrate_short": stage20_winrate_short,
                        "stage20_memory_long_count": stage20_memory_long_count,
                        "stage20_memory_short_count": stage20_memory_short_count,
                    },
                    index=dataframe.index,
                ),
            ],
            axis=1,
        )

        long_edge_score = (
            0.62 * self._score(stage20_edge_long.fillna(0.0), -0.0018, 0.0060)
            + 0.25
            * self._score(stage20_edge_long_slow.fillna(0.0), -0.0010, 0.0035)
            + 0.13 * self._score(stage20_winrate_long.fillna(0.5), 0.46, 0.62)
        ).clip(0.0, 1.0)
        short_edge_score = (
            0.62 * self._score(stage20_edge_short.fillna(0.0), -0.0018, 0.0060)
            + 0.25
            * self._score(stage20_edge_short_slow.fillna(0.0), -0.0010, 0.0035)
            + 0.13 * self._score(stage20_winrate_short.fillna(0.5), 0.46, 0.62)
        ).clip(0.0, 1.0)

        slow_long_sample = pd.concat([long_count_momo_slow, long_count_pull_slow], axis=1).max(
            axis=1,
        )
        slow_short_sample = pd.concat([short_count_momo_slow, short_count_pull_slow], axis=1).max(
            axis=1,
        )
        long_sample_score = (stage20_memory_long_count.fillna(0.0) / 8.0).clip(
            0.20,
            1.0,
        )
        long_sample_score = (0.72 * long_sample_score + 0.28 * (slow_long_sample / 18.0)).clip(
            0.20,
            1.0,
        )
        short_sample_score = (stage20_memory_short_count.fillna(0.0) / 8.0).clip(
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

        stage20_adaptive_long = (
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
        stage20_adaptive_short = (
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

        dataframe = pd.concat(
            [
                dataframe,
                DataFrame(
                    {
                        "stage20_adaptive_long": stage20_adaptive_long,
                        "stage20_adaptive_short": stage20_adaptive_short,
                        "stage20_raw_momo_long": raw_momo_long,
                        "stage20_raw_momo_short": raw_momo_short,
                        "stage20_raw_pull_long": raw_pull_long,
                        "stage20_raw_pull_short": raw_pull_short,
                        "stage20_momo_long_promoted": (
                            (long_count_momo >= 8)
                            & (long_edge_momo > 0.0012)
                            & ((long_count_momo_slow < 14) | (long_edge_momo_slow > -0.00015))
                            & (long_win_momo.fillna(0.5) >= 0.54)
                        ),
                        "stage20_pull_long_promoted": (
                            bool(self.stage20_enable_pull_learning_entries)
                            & (long_count_pull >= 8)
                            & (long_edge_pull > 0.0010)
                            & ((long_count_pull_slow < 14) | (long_edge_pull_slow > -0.00015))
                            & (long_win_pull.fillna(0.5) >= 0.53)
                        ),
                        "stage20_momo_short_promoted": (
                            bool(self.stage20_enable_short_learning_entries)
                            & (short_count_momo >= 12)
                            & (short_edge_momo > 0.0018)
                            & (short_count_momo_slow >= 18)
                            & (short_edge_momo_slow > 0.00025)
                            & (short_win_momo.fillna(0.5) >= 0.56)
                        ),
                        "stage20_pull_short_promoted": (
                            bool(self.stage20_enable_short_learning_entries)
                            & bool(self.stage20_enable_pull_learning_entries)
                            & (short_count_pull >= 12)
                            & (short_edge_pull > 0.0018)
                            & (short_count_pull_slow >= 18)
                            & (short_edge_pull_slow > 0.00025)
                            & (short_win_pull.fillna(0.5) >= 0.56)
                        ),
                    },
                    index=dataframe.index,
                ),
            ],
            axis=1,
        )
        return dataframe

    def populate_entry_trend(
        self,
        dataframe: DataFrame,
        metadata: dict,
    ) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        close = dataframe["close"].replace(0, np.nan)
        high = dataframe["high"]
        low = dataframe["low"]
        open_ = dataframe["open"]
        atr = dataframe["stage19_atr_pct"].fillna(0.0)
        volume_ratio = dataframe["stage19_volume_ratio"].fillna(1.0)
        hot = dataframe["stage19_hot_score"].fillna(0.0)
        risk = dataframe["stage19_overheat_score"].fillna(1.0)
        rsi_3 = dataframe["stage19_rsi_3"].fillna(50.0)
        rsi_7 = dataframe["stage19_rsi_7"].fillna(50.0)
        roc_3 = dataframe["stage19_roc_3"].fillna(0.0)
        roc_8 = dataframe["stage19_roc_8"].fillna(0.0)
        roc_15 = dataframe["stage19_roc_15"].fillna(0.0)
        roc_30 = dataframe["stage19_roc_30"].fillna(0.0)
        close_pos = dataframe["stage20_close_pos"].fillna(0.5)
        vwap_20 = dataframe["stage19_vwap_20"].replace(0, np.nan)
        vwap_60 = dataframe["stage19_vwap_60"].replace(0, np.nan)
        bb_high = dataframe["stage19_bb_high"]
        bb_low = dataframe["stage19_bb_low"]
        body = (close - open_).abs()
        candle_range = (high - low).replace(0, np.nan)
        upper_wick = high - dataframe[["open", "close"]].max(axis=1)
        lower_wick = dataframe[["open", "close"]].min(axis=1) - low
        pair = metadata["pair"]
        sweep_pair = pair.startswith(self.stage20_sweep_prefixes)

        chop = dataframe["stage20_chop_risk"].fillna(1.0)
        btc_risk = dataframe["stage20_btc_risk"].fillna(0.5)
        tradable = (
            (atr > 0.00048)
            & (atr < 0.068)
            & (volume_ratio > 0.72)
            & (chop < 0.76)
            & (btc_risk < 0.94)
        )
        market_long_ok = (dataframe["stage20_btc_bias"] > -0.58) & (
            dataframe["stage20_btc_trend"] > -0.66
        )
        market_short_ok = (
            (dataframe["stage20_btc_bias"] < 0.58) & (dataframe["stage20_btc_trend"] < 0.66)
        )

        body_ratio = (body / candle_range).fillna(0.0)
        wick_long_strength = lower_wick / (body + close * 0.0007)
        wick_short_strength = upper_wick / (body + close * 0.0007)
        sweep_ready = body_ratio < 0.64
        fast_sweep_ready = body_ratio < 0.78
        fast_liquidity_ok = volume_ratio > 0.80
        long_extension_guard = ~(
            ((roc_30 > 0.012) & (close_pos < 0.55))
            | ((roc_15 < -0.024) & (close_pos < 0.45))
        )
        short_extension_guard = ~(
            ((roc_30 > 0.038) & (roc_3 > 0.0))
            | ((roc_15 > 0.030) & (close_pos > 0.45))
        )

        long_result = close / close.shift(self.stage20_memory_horizon) - 1 - self.stage20_fee_drag
        short_result = close.shift(self.stage20_memory_horizon) / close - 1 - self.stage20_fee_drag
        long_win = (long_result > 0).astype(float)
        short_win = (short_result > 0).astype(float)

        fast_long_sweep_raw = (
            sweep_pair
            & tradable
            & market_long_ok
            & (hot > 0.30)
            & (risk < 0.88)
            & (chop < 0.70)
            & fast_liquidity_ok
            & long_extension_guard
            & (roc_3 < -0.0012)
            & (roc_8 > -0.024)
            & (
                (low < dataframe["stage19_don_low_20"] * 0.9997)
                | (low < bb_low * 0.9990)
                | (close < vwap_20 * 0.9970)
            )
            & (wick_long_strength > 0.74)
            & (close_pos > 0.36)
            & (rsi_3 > rsi_3.shift(1))
            & rsi_3.between(12, 48)
            & rsi_7.between(20, 60)
            & fast_sweep_ready
        )
        fast_short_sweep_raw = (
            sweep_pair
            & tradable
            & market_short_ok
            & (hot > 0.30)
            & (risk < 0.88)
            & (chop < 0.70)
            & fast_liquidity_ok
            & short_extension_guard
            & (roc_3 > 0.0012)
            & (roc_8 < 0.024)
            & (
                (high > dataframe["stage19_don_high_20"] * 1.0003)
                | (high > bb_high * 1.0010)
                | (close > vwap_20 * 1.0030)
            )
            & (wick_short_strength > 0.74)
            & (close_pos < 0.64)
            & (rsi_3 < rsi_3.shift(1))
            & rsi_3.between(52, 88)
            & rsi_7.between(40, 80)
            & fast_sweep_ready
        )
        long_sweep_raw = (
            sweep_pair
            & tradable
            & market_long_ok
            & (hot > 0.34)
            & (risk < 0.82)
            & (volume_ratio > 0.86)
            & long_extension_guard
            & (roc_3 > -0.007)
            & (roc_8 > -0.014)
            & (low < dataframe["stage19_don_low_20"] * 0.9994)
            & (low < bb_low * 0.9990)
            & (wick_long_strength > 1.06)
            & (close > dataframe["stage19_vwap_20"])
            & (close_pos > 0.48)
            & (rsi_3 > rsi_3.shift(1))
            & rsi_3.between(16, 50)
            & rsi_7.between(24, 60)
            & sweep_ready
        )
        short_sweep_raw = (
            sweep_pair
            & tradable
            & market_short_ok
            & (hot > 0.34)
            & (risk < 0.82)
            & (volume_ratio > 0.86)
            & short_extension_guard
            & (roc_3 < 0.007)
            & (roc_8 < 0.014)
            & (high > dataframe["stage19_don_high_20"] * 1.0006)
            & (high > bb_high * 1.0010)
            & (wick_short_strength > 1.06)
            & (close < dataframe["stage19_vwap_20"])
            & (close_pos < 0.52)
            & (rsi_3 < rsi_3.shift(1))
            & rsi_3.between(50, 84)
            & rsi_7.between(40, 76)
            & sweep_ready
        )
        fast_vwap_long_raw = (
            False
            & sweep_pair
            & tradable
            & market_long_ok
            & (hot > 0.34)
            & (risk < 0.76)
            & (chop < 0.56)
            & (btc_risk < 0.88)
            & (close < vwap_20 * 0.9978)
            & (close > vwap_60 * 0.9940)
            & (dataframe["stage19_roc_15"] > -0.022)
            & (dataframe["stage19_roc_3"] > -0.0030)
            & (close_pos > 0.50)
            & (rsi_3 > rsi_3.shift(1))
            & rsi_3.between(24, 50)
            & rsi_7.between(32, 58)
            & (dataframe["stage20_exhaustion_long"] < 0.52)
            & (volume_ratio > 0.94)
        )
        fast_vwap_short_raw = (
            False
            & sweep_pair
            & tradable
            & market_short_ok
            & (hot > 0.36)
            & (risk < 0.76)
            & (chop < 0.58)
            & (btc_risk < 0.88)
            & (close > vwap_20 * 1.0024)
            & (close < vwap_60 * 1.0065)
            & (dataframe["stage19_roc_15"] < 0.024)
            & (dataframe["stage19_roc_3"] < 0.0030)
            & (close_pos < 0.50)
            & (rsi_3 < rsi_3.shift(1))
            & rsi_3.between(50, 78)
            & rsi_7.between(42, 70)
            & (dataframe["stage20_exhaustion_short"] < 0.52)
            & (volume_ratio > 0.96)
        )

        raw_long_reversion = fast_long_sweep_raw | long_sweep_raw | fast_vwap_long_raw
        raw_short_reversion = fast_short_sweep_raw | short_sweep_raw | fast_vwap_short_raw
        long_rev_edge, long_rev_count = self._rolling_mean_when(
            long_result,
            raw_long_reversion.shift(self.stage20_memory_horizon).fillna(False),
            self.stage20_memory_window,
        )
        short_rev_edge, short_rev_count = self._rolling_mean_when(
            short_result,
            raw_short_reversion.shift(self.stage20_memory_horizon).fillna(False),
            self.stage20_memory_window,
        )
        long_rev_edge_slow, long_rev_count_slow = self._rolling_mean_when(
            long_result,
            raw_long_reversion.shift(self.stage20_memory_horizon).fillna(False),
            self.stage20_slow_memory_window,
            min_periods=8,
        )
        short_rev_edge_slow, short_rev_count_slow = self._rolling_mean_when(
            short_result,
            raw_short_reversion.shift(self.stage20_memory_horizon).fillna(False),
            self.stage20_slow_memory_window,
            min_periods=8,
        )
        long_rev_win, _ = self._rolling_mean_when(
            long_win,
            raw_long_reversion.shift(self.stage20_memory_horizon).fillna(False),
            self.stage20_memory_window,
        )
        short_rev_win, _ = self._rolling_mean_when(
            short_win,
            raw_short_reversion.shift(self.stage20_memory_horizon).fillna(False),
            self.stage20_memory_window,
        )
        long_rev_ok = (
            (long_rev_count >= 5)
            & (long_rev_edge > 0.00030)
            & (long_rev_win.fillna(0.0) >= 0.50)
            & ((long_rev_count_slow < 8) | (long_rev_edge_slow > -0.00025))
        )
        short_rev_ok = (
            (short_rev_count >= 5)
            & (short_rev_edge > 0.00030)
            & (short_rev_win.fillna(0.0) >= 0.50)
            & ((short_rev_count_slow < 8) | (short_rev_edge_slow > -0.00025))
        )

        no_stage_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        fast_long_sweep = no_stage_entry & fast_long_sweep_raw & long_rev_ok
        dataframe.loc[fast_long_sweep, ["enter_long", "enter_tag"]] = (
            1,
            "s20_sweep_fast_l_h4m_l4",
        )

        no_stage_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        fast_short_sweep = no_stage_entry & fast_short_sweep_raw & short_rev_ok
        dataframe.loc[fast_short_sweep, ["enter_short", "enter_tag"]] = (
            1,
            "s20_sweep_fast_s_h4m_l4",
        )

        no_stage_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        long_sweep = no_stage_entry & long_sweep_raw & long_rev_ok
        dataframe.loc[long_sweep, ["enter_long", "enter_tag"]] = (1, "s20_sweep_l_h6m_l4")

        no_stage_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        short_sweep = no_stage_entry & short_sweep_raw & short_rev_ok
        dataframe.loc[short_sweep, ["enter_short", "enter_tag"]] = (1, "s20_sweep_s_h6m_l4")

        no_stage_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        fast_vwap_long = no_stage_entry & fast_vwap_long_raw & long_rev_ok
        dataframe.loc[fast_vwap_long, ["enter_long", "enter_tag"]] = (
            1,
            "s20_vwaprev_fast_l_h5m_l3",
        )

        no_stage_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        fast_vwap_short = no_stage_entry & fast_vwap_short_raw & short_rev_ok
        dataframe.loc[fast_vwap_short, ["enter_short", "enter_tag"]] = (
            1,
            "s20_vwaprev_fast_s_h5m_l3",
        )

        no_stage_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        vwap_long = (
            False
            & no_stage_entry
            & sweep_pair
            & tradable
            & market_long_ok
            & (dataframe["stage20_trend_long"] > 0.56)
            & (dataframe["stage20_adaptive_long"] > 0.46)
            & (chop < 0.64)
            & (btc_risk < 0.90)
            & (dataframe["stage19_roc_30"] > -0.002)
            & (dataframe["stage19_roc_3"] > -0.0028)
            & (close < vwap_20 * 0.9986)
            & (close > vwap_60 * 0.9940)
            & (close_pos > 0.44)
            & (dataframe["stage20_exhaustion_long"] < 0.64)
            & rsi_7.between(30, 62)
            & (volume_ratio > 0.86)
        )
        dataframe.loc[vwap_long, ["enter_long", "enter_tag"]] = (1, "s20_vwaprev_l_h8m_l4")

        no_stage_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        vwap_short = (
            False
            & no_stage_entry
            & sweep_pair
            & tradable
            & market_short_ok
            & (dataframe["stage20_trend_short"] > 0.58)
            & (dataframe["stage20_adaptive_short"] > 0.48)
            & (chop < 0.64)
            & (btc_risk < 0.90)
            & (dataframe["stage19_roc_30"] < 0.002)
            & (dataframe["stage19_roc_3"] < 0.0028)
            & (close > vwap_20 * 1.0014)
            & (close < vwap_60 * 1.0060)
            & (close_pos < 0.56)
            & (dataframe["stage20_exhaustion_short"] < 0.64)
            & rsi_7.between(38, 70)
            & (volume_ratio > 0.86)
        )
        dataframe.loc[vwap_short, ["enter_short", "enter_tag"]] = (1, "s20_vwaprev_s_h8m_l4")
        return dataframe

    def _populate_entry_trend_strict_stage20_disabled(
        self,
        dataframe: DataFrame,
        metadata: dict,
    ) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        close = dataframe["close"].replace(0, np.nan)
        high = dataframe["high"]
        low = dataframe["low"]
        open_ = dataframe["open"]
        atr = dataframe["stage19_atr_pct"].fillna(0.0)
        range_pct = dataframe["stage19_range_pct"].fillna(0.0)
        volume_ratio = dataframe["stage19_volume_ratio"].fillna(1.0)
        hot = dataframe["stage19_hot_score"].fillna(0.0)
        risk = dataframe["stage19_overheat_score"].fillna(1.0)
        rsi_3 = dataframe["stage19_rsi_3"].fillna(50.0)
        rsi_7 = dataframe["stage19_rsi_7"].fillna(50.0)
        close_pos = dataframe["stage20_close_pos"].fillna(0.5)
        vwap_20 = dataframe["stage19_vwap_20"].replace(0, np.nan)
        vwap_60 = dataframe["stage19_vwap_60"].replace(0, np.nan)
        bb_high = dataframe["stage19_bb_high"]
        bb_low = dataframe["stage19_bb_low"]
        body = (close - open_).abs()
        candle_range = (high - low).replace(0, np.nan)
        upper_wick = high - dataframe[["open", "close"]].max(axis=1)
        lower_wick = dataframe[["open", "close"]].min(axis=1) - low
        body_ratio = (body / candle_range).fillna(0.0)
        wick_long_strength = lower_wick / (body + close * 0.0008)
        wick_short_strength = upper_wick / (body + close * 0.0008)

        pair = metadata["pair"]
        high_beta_pair = pair.startswith(self.stage20_high_beta_prefixes)
        pulse_long_pair = pair.startswith(self.stage20_pulse_long_prefixes)
        pulse_short_pair = pair.startswith(self.stage20_pulse_short_prefixes)
        sweep_pair = pair.startswith(self.stage20_sweep_prefixes)
        sweep_short_pair = pair.startswith(self.stage20_sweep_short_prefixes)

        chop = dataframe["stage20_chop_risk"].fillna(1.0)
        btc_risk = dataframe["stage20_btc_risk"].fillna(0.5)
        btc_bias = dataframe["stage20_btc_bias"].fillna(0.0)
        btc_trend = dataframe["stage20_btc_trend"].fillna(0.0)
        roc_3 = dataframe["stage19_roc_3"].fillna(0.0)
        roc_8 = dataframe["stage19_roc_8"].fillna(0.0)
        roc_15 = dataframe["stage19_roc_15"].fillna(0.0)
        roc_30 = dataframe["stage19_roc_30"].fillna(0.0)
        strong_body = body_ratio > 0.46
        fresh_history = dataframe["stage20_age_score"].fillna(0.35) < 0.62
        launch_long = (
            fresh_history
            & pulse_long_pair
            & (volume_ratio > 1.70)
            & (hot > 0.66)
            & (risk < 0.56)
            & (chop < 0.46)
            & (btc_risk < 0.80)
            & (roc_3 > 0.0040)
            & (roc_8 > 0.0120)
            & (close_pos > 0.72)
            & (body_ratio > 0.56)
            & rsi_7.between(58, 78)
            & (btc_bias > -0.18)
        )
        launch_short = (
            fresh_history
            & pulse_short_pair
            & (volume_ratio > 1.75)
            & (hot > 0.68)
            & (risk < 0.56)
            & (chop < 0.46)
            & (btc_risk < 0.80)
            & (roc_3 < -0.0040)
            & (roc_8 < -0.0120)
            & (close_pos < 0.28)
            & (body_ratio > 0.56)
            & rsi_7.between(22, 42)
            & (btc_bias < 0.18)
        )
        tradable = (
            high_beta_pair
            & (atr > 0.00090)
            & (atr < 0.052)
            & (range_pct > 0.00080)
            & (volume_ratio > 0.86)
            & (chop < 0.66)
            & (btc_risk < 0.91)
            & (dataframe["volume"] > 0)
        )
        market_long_ok = (btc_bias > -0.42) & (btc_trend > -0.50)
        market_short_ok = (btc_bias < 0.42) & (btc_trend < 0.50)

        pulse_long_raw = (
            pulse_long_pair
            & tradable
            & market_long_ok
            & (dataframe["stage20_trend_long"] > 0.64)
            & (dataframe["stage20_adaptive_long"] > 0.57)
            & (hot > 0.52)
            & (risk < 0.70)
            & (chop < 0.56)
            & (roc_3 > 0.0028)
            & (roc_8 > 0.0068)
            & (
                (close > dataframe["stage19_don_high_20"] * 1.0006)
                | (close > vwap_20 * 1.0034)
            )
            & (volume_ratio > 1.14)
            & (close_pos > 0.64)
            & strong_body
            & rsi_7.between(54, 78)
            & (dataframe["stage20_exhaustion_long"] < 0.64)
        )
        pulse_short_raw = (
            pulse_short_pair
            & tradable
            & market_short_ok
            & (dataframe["stage20_trend_short"] > 0.66)
            & (dataframe["stage20_adaptive_short"] > 0.60)
            & (hot > 0.56)
            & (risk < 0.66)
            & (chop < 0.54)
            & (roc_3 < -0.0032)
            & (roc_8 < -0.0078)
            & (
                (close < dataframe["stage19_don_low_20"] * 0.9994)
                | (close < vwap_20 * 0.9966)
            )
            & (volume_ratio > 1.18)
            & (close_pos < 0.36)
            & strong_body
            & rsi_7.between(22, 46)
            & (dataframe["stage20_exhaustion_short"] < 0.62)
        )
        sweep_long_raw = (
            sweep_pair
            & tradable
            & market_long_ok
            & (hot > 0.42)
            & (risk < 0.68)
            & (chop < 0.52)
            & (btc_risk < 0.86)
            & (roc_3 < -0.0026)
            & (roc_8 > -0.022)
            & (
                (low < dataframe["stage19_don_low_20"] * 0.9986)
                | (low < bb_low * 0.9980)
            )
            & (wick_long_strength > 1.32)
            & (close_pos > 0.52)
            & (rsi_3 > rsi_3.shift(1))
            & rsi_3.between(12, 44)
            & rsi_7.between(20, 56)
            & (body_ratio < 0.62)
        )
        sweep_short_raw = (
            sweep_short_pair
            & tradable
            & market_short_ok
            & (hot > 0.44)
            & (risk < 0.66)
            & (chop < 0.50)
            & (btc_risk < 0.84)
            & (roc_3 > 0.0028)
            & (roc_8 < 0.020)
            & (
                (high > dataframe["stage19_don_high_20"] * 1.0014)
                | (high > bb_high * 1.0020)
            )
            & (wick_short_strength > 1.34)
            & (close_pos < 0.48)
            & (rsi_3 < rsi_3.shift(1))
            & rsi_3.between(56, 88)
            & rsi_7.between(44, 78)
            & (body_ratio < 0.60)
        )
        vwap_long_raw = (
            sweep_pair
            & tradable
            & market_long_ok
            & (hot > 0.44)
            & (risk < 0.58)
            & (chop < 0.46)
            & (btc_risk < 0.82)
            & (close < vwap_20 * 0.9972)
            & (close > vwap_60 * 0.9945)
            & (roc_30 > -0.012)
            & (roc_15 > -0.016)
            & (roc_3 > -0.0024)
            & (close_pos > 0.56)
            & (rsi_3 > rsi_3.shift(1))
            & rsi_3.between(22, 46)
            & rsi_7.between(32, 56)
            & (volume_ratio > 0.98)
        )
        vwap_short_raw = (
            sweep_short_pair
            & tradable
            & market_short_ok
            & (hot > 0.46)
            & (risk < 0.58)
            & (chop < 0.46)
            & (btc_risk < 0.82)
            & (close > vwap_20 * 1.0028)
            & (close < vwap_60 * 1.0055)
            & (roc_30 < 0.012)
            & (roc_15 < 0.016)
            & (roc_3 < 0.0024)
            & (close_pos < 0.44)
            & (rsi_3 < rsi_3.shift(1))
            & rsi_3.between(54, 80)
            & rsi_7.between(44, 70)
            & (volume_ratio > 1.00)
        )

        horizon = self.stage20_memory_horizon
        long_result = close / close.shift(horizon) - 1 - self.stage20_fee_drag
        short_result = close.shift(horizon) / close - 1 - self.stage20_fee_drag
        long_win = (long_result > 0).astype(float)
        short_win = (short_result > 0).astype(float)

        pulse_l_edge, pulse_l_count = self._rolling_mean_when(
            long_result,
            pulse_long_raw.shift(horizon).fillna(False),
            self.stage20_memory_window,
        )
        pulse_l_win, _ = self._rolling_mean_when(
            long_win,
            pulse_long_raw.shift(horizon).fillna(False),
            self.stage20_memory_window,
        )
        pulse_s_edge, pulse_s_count = self._rolling_mean_when(
            short_result,
            pulse_short_raw.shift(horizon).fillna(False),
            self.stage20_memory_window,
        )
        pulse_s_win, _ = self._rolling_mean_when(
            short_win,
            pulse_short_raw.shift(horizon).fillna(False),
            self.stage20_memory_window,
        )
        rev_l_raw = sweep_long_raw | vwap_long_raw
        rev_s_raw = sweep_short_raw | vwap_short_raw
        rev_l_edge, rev_l_count = self._rolling_mean_when(
            long_result,
            rev_l_raw.shift(horizon).fillna(False),
            self.stage20_memory_window,
        )
        rev_l_win, _ = self._rolling_mean_when(
            long_win,
            rev_l_raw.shift(horizon).fillna(False),
            self.stage20_memory_window,
        )
        rev_s_edge, rev_s_count = self._rolling_mean_when(
            short_result,
            rev_s_raw.shift(horizon).fillna(False),
            self.stage20_memory_window,
        )
        rev_s_win, _ = self._rolling_mean_when(
            short_win,
            rev_s_raw.shift(horizon).fillna(False),
            self.stage20_memory_window,
        )
        pulse_l_edge_slow, pulse_l_count_slow = self._rolling_mean_when(
            long_result,
            pulse_long_raw.shift(horizon).fillna(False),
            self.stage20_slow_memory_window,
            min_periods=12,
        )
        pulse_s_edge_slow, pulse_s_count_slow = self._rolling_mean_when(
            short_result,
            pulse_short_raw.shift(horizon).fillna(False),
            self.stage20_slow_memory_window,
            min_periods=12,
        )
        rev_l_edge_slow, rev_l_count_slow = self._rolling_mean_when(
            long_result,
            rev_l_raw.shift(horizon).fillna(False),
            self.stage20_slow_memory_window,
            min_periods=10,
        )
        rev_s_edge_slow, rev_s_count_slow = self._rolling_mean_when(
            short_result,
            rev_s_raw.shift(horizon).fillna(False),
            self.stage20_slow_memory_window,
            min_periods=10,
        )

        pulse_l_ok = (
            (
                (pulse_l_count >= 5)
                & (pulse_l_edge > 0.00055)
                & (pulse_l_win.fillna(0.0) >= 0.52)
                & ((pulse_l_count_slow < 12) | (pulse_l_edge_slow > -0.00035))
            )
            | ((pulse_l_count < 5) & launch_long)
        )
        pulse_s_ok = (
            (
                (pulse_s_count >= 6)
                & (pulse_s_edge > 0.00080)
                & (pulse_s_win.fillna(0.0) >= 0.53)
                & ((pulse_s_count_slow < 12) | (pulse_s_edge_slow > -0.00025))
            )
            | ((pulse_s_count < 5) & launch_short)
        )
        rev_l_ok = (
            (rev_l_count >= 5)
            & (rev_l_edge > 0.00035)
            & (rev_l_win.fillna(0.0) >= 0.51)
            & ((rev_l_count_slow < 10) | (rev_l_edge_slow > -0.00045))
        )
        rev_s_ok = (
            (rev_s_count >= 5)
            & (rev_s_edge > 0.00045)
            & (rev_s_win.fillna(0.0) >= 0.52)
            & ((rev_s_count_slow < 10) | (rev_s_edge_slow > -0.00035))
        )

        no_stage_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        pulse_long = no_stage_entry & pulse_long_raw & pulse_l_ok
        dataframe.loc[pulse_long, ["enter_long", "enter_tag"]] = (
            1,
            "s20_pulse_l_h6m_l4",
        )

        no_stage_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        pulse_short = no_stage_entry & pulse_short_raw & pulse_s_ok
        dataframe.loc[pulse_short, ["enter_short", "enter_tag"]] = (
            1,
            "s20_pulse_s_h5m_l4",
        )

        no_stage_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        sweep_long = no_stage_entry & sweep_long_raw & rev_l_ok
        dataframe.loc[sweep_long, ["enter_long", "enter_tag"]] = (
            1,
            "s20_sweep_l_h4m_l3",
        )

        no_stage_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        sweep_short = no_stage_entry & sweep_short_raw & rev_s_ok
        dataframe.loc[sweep_short, ["enter_short", "enter_tag"]] = (
            1,
            "s20_sweep_s_h4m_l3",
        )

        no_stage_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        vwap_long = no_stage_entry & vwap_long_raw & rev_l_ok
        dataframe.loc[vwap_long, ["enter_long", "enter_tag"]] = (
            1,
            "s20_vwaprev_l_h4m_l3",
        )

        no_stage_entry = (dataframe["enter_long"] != 1) & (dataframe["enter_short"] != 1)
        vwap_short = no_stage_entry & vwap_short_raw & rev_s_ok
        dataframe.loc[vwap_short, ["enter_short", "enter_tag"]] = (
            1,
            "s20_vwaprev_s_h4m_l3",
        )
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
        if entry_tag and ("_sweep_" in entry_tag or "_vwaprev_" in entry_tag):
            if scores["btc_risk"] > 0.88:
                return False
            if scores["risk"] > 0.78 or scores["chop"] > 0.58:
                return False
            if side_count >= 8 and side_edge < -0.0008:
                return False
            if side_count >= 10 and side_win < 0.50:
                return False
            return True
        if side_score < 0.58:
            return False
        if side_count >= 5 and side_edge < -0.0007:
            return False
        if side_count >= 6 and side_win < 0.52:
            return False
        if side_count_slow >= 12 and side_edge_slow < -0.00020:
            return False
        if scores["btc_risk"] > 0.88 and side_score < 0.66:
            return False
        if scores["risk"] > 0.76 and side_score < 0.68:
            return False
        if scores["chop"] > 0.58 and side_score < 0.68:
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

        if entry_tag and "_sweep_" in entry_tag:
            tag_boost = 0.86
        elif entry_tag and "_vwaprev_" in entry_tag:
            tag_boost = 0.78
        else:
            tag_boost = 1.02 if entry_tag and "_pulse_" in entry_tag else 0.94
        sample_factor = 0.62 + min(side_count / 14.0, 1.0) * 0.26
        sample_factor += min(side_count_slow / 30.0, 1.0) * 0.08
        edge_factor = 1.0 + self._bounded(side_edge, -0.006, 0.008) * 15.0
        multiplier = self._stage20_pair_weight(pair) * tag_boost
        multiplier *= 0.50 + side_score * 0.42
        multiplier *= sample_factor
        multiplier *= edge_factor
        multiplier *= 0.84 + max(side_win - 0.52, 0.0) * 0.70
        multiplier *= 1.0 - max(scores["risk"] - 0.62, 0.0) * 0.90
        multiplier *= 1.0 - max(scores["chop"] - 0.42, 0.0) * 0.70
        multiplier *= scores["age"]
        if entry_tag and ("_sweep_" in entry_tag or "_vwaprev_" in entry_tag):
            multiplier *= 1.02 - min(scores["btc_risk"], 0.95) * 0.24
            multiplier = self._bounded(multiplier, 0.24, 0.66)
        elif side_count < 8:
            multiplier *= 0.64
        is_reversion_tag = bool(
            entry_tag and ("_sweep_" in entry_tag or "_vwaprev_" in entry_tag)
        )
        if not is_reversion_tag and side_edge < 0.0010:
            multiplier *= 0.70
        if not is_reversion_tag and side_count_slow >= 14 and side_edge_slow < 0.00015:
            multiplier *= 0.66
        multiplier = self._bounded(multiplier, 0.18, 0.66 if is_reversion_tag else 0.74)

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
        if entry_tag and ("_sweep_" in entry_tag or "_vwaprev_" in entry_tag):
            target = min(target, 3.8)
            if scores["risk"] > 0.70 or scores["btc_risk"] > 0.82:
                target -= 0.70
            if pair.startswith(self.stage20_core_prefixes):
                target -= 0.35
            return max(1.0, min(target, max_leverage, 4.2))
        if side_score > 0.72 and side_edge > 0.0018 and side_count >= 8:
            target += 0.25
        if side_score < 0.60 or scores["risk"] > 0.76 or scores["btc_risk"] > 0.86:
            target -= 0.85
        if side_count < 5:
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

        if trade.enter_tag and ("_sweep_" in trade.enter_tag or "_vwaprev_" in trade.enter_tag):
            if current_profit >= 0.0062:
                return "stage20_fast_profit_exit"
            if trade_minutes >= 1 and current_profit >= 0.0030:
                return "stage20_reversion_take_profit"
            if trade_minutes >= 1 and current_profit <= -0.0030:
                return "stage20_fast_loss_exit"
            if scores["risk"] > 0.66 and current_profit <= -0.0018:
                return "stage20_reversion_risk_exit"
            if side_score < 0.36 and trade_minutes >= 2 and current_profit <= 0.0:
                return "stage20_reversion_decay_exit"
            if trade_minutes >= 4:
                return "stage20_reversion_fixed_hold_exit"
            return None

        if current_profit >= 0.013:
            return "stage20_fast_profit_exit"
        if trade_minutes >= 2 and current_profit >= 0.006 and side_score < 0.58:
            return "stage20_adaptive_take_profit"
        if trade_minutes >= 1 and current_profit <= -0.010:
            return "stage20_fast_loss_exit"
        if trade_minutes >= 3 and current_profit <= -0.006:
            return "stage20_time_loss_exit"
        if side_count >= 5 and side_edge < 0.0002 and current_profit <= -0.003:
            return "stage20_memory_edge_exit"
        if side_count >= 6 and side_win < 0.50 and current_profit <= -0.0025:
            return "stage20_winrate_decay_exit"
        if side_count_slow >= 12 and side_edge_slow < -0.00020 and current_profit <= -0.0025:
            return "stage20_slow_memory_decay_exit"
        if scores["risk"] > 0.72 and scores["chop"] > 0.50 and current_profit <= -0.004:
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
