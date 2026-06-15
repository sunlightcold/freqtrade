from datetime import datetime

import numpy as np
import pandas as pd
from freqtrade.persistence import Trade
from pandas import DataFrame

from Intp20Stage16StressPrunedScalpStrategy import Intp20Stage16TurboPrunedScalpStrategy


class Intp20Stage17AdaptiveScalpStrategy(Intp20Stage16TurboPrunedScalpStrategy):
    """
    Stage-17 mature-market cost-pruned scalp strategy.

    Stage-17 is intentionally different from the Stage-20 new-coin pulse book:
    it only trades the mature 20-pair legacy scalp stack that survived the
    Stage-16 fee stress filter, then blocks the recent weak tags that turned
    profitable holds into fast losses during the 2026-06 drawdown window.
    """

    stoploss = -0.12

    order_types = {
        "entry": "limit",
        "exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    adaptive_blocked_tags = {
        "s15_01_aave_vwap_s_lt_h30m_l5",
        "s9_02_sol_panic_s_mc_h24_l4",
        "s9_04_xlm_panic_l_mc_h12_l4",
        "s9_05_comp_rsi_l_mx_h24_l4",
        "s10_06_xlm_maoff_l_ma_h12m_l5",
        "s13_01_near_rsi_s_lc_h24_l4",
        "s13_03_icp_rsi_s_lc_h24_l4",
        "s15_04_op_vwap_l_mchop_h30m_l5",
    }
    blocked_tags = Intp20Stage16TurboPrunedScalpStrategy.blocked_tags | adaptive_blocked_tags

    pair_stake_weights = {
        **Intp20Stage16TurboPrunedScalpStrategy.pair_stake_weights,
        "AAVE/": 1.10,
        "SOL/": 0.72,
        "ICP/": 0.72,
        "XLM/": 0.68,
        "SUI/": 0.62,
        "APT/": 0.50,
        "FET/": 0.48,
        "NEAR/": 0.48,
        "COMP/": 0.44,
    }

    tag_stake_weights = {
        **Intp20Stage16TurboPrunedScalpStrategy.tag_stake_weights,
        "s13_02_dot_rsi_s_lc_h24_l4": 1.28,
        "s9_08_xtz_rsi_s_lc_h24_l4": 1.22,
        "s9_10_xrp_rsi_s_mx_h24_l4": 1.18,
        "s15_02_doge_vwap_l_mchop_h30m_l5": 1.08,
        "s15_03_xrp_vwap_l_mhv_h30m_l5": 1.04,
        "s13_05_uni_rsi_s_lc_h24_l4": 0.64,
        "s9_25_sui_vwap_l_lc_h18_l5": 0.58,
    }

    leverage_bonus_tags = {
        "s13_02_dot_rsi_s_lc_h24_l4",
        "s9_08_xtz_rsi_s_lc_h24_l4",
        "s9_10_xrp_rsi_s_mx_h24_l4",
        "s15_02_doge_vwap_l_mchop_h30m_l5",
        "s15_03_xrp_vwap_l_mhv_h30m_l5",
    }
    guarded_short_tags = {
        "s13_02_dot_rsi_s_lc_h24_l4",
        "s9_08_xtz_rsi_s_lc_h24_l4",
        "s13_05_uni_rsi_s_lc_h24_l4",
    }
    stage17_mature_prefixes = (
        "AAVE/",
        "APT/",
        "COMP/",
        "DOGE/",
        "DOT/",
        "ETC/",
        "ETH/",
        "FET/",
        "ICP/",
        "LTC/",
        "MANA/",
        "MKR/",
        "NEAR/",
        "OP/",
        "SOL/",
        "SUI/",
        "UNI/",
        "XLM/",
        "XRP/",
        "XTZ/",
    )
    stage17_memory_window = 720
    stage17_memory_horizon = 6
    stage17_fee_drag = 0.00150
    max_stake_multiplier = 2.15
    min_stake_multiplier = 0.42
    max_boost_leverage = 7.0

    protected_legacy_prefixes = (
        "s7_",
        "s8_",
        "s9_",
        "s10_",
        "s11_",
        "s12_",
        "s13_",
        "s14_",
        "s15_",
    )

    @classmethod
    def _is_protected_legacy_tag(cls, entry_tag: str | None) -> bool:
        return bool(entry_tag and entry_tag.startswith(cls.protected_legacy_prefixes))

    @staticmethod
    def _is_stage17_tag(entry_tag: str | None) -> bool:
        return bool(entry_tag and entry_tag.startswith("s17_"))

    @staticmethod
    def _bounded(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
        if not np.isfinite(value):
            return (lower + upper) / 2
        return max(lower, min(upper, value))

    @staticmethod
    def _safe_div(numerator, denominator):
        return (numerator / denominator.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)

    @staticmethod
    def _rolling_mean_when(value, mask, window: int, min_periods: int = 1):
        weighted = value.where(mask, 0.0).rolling(window, min_periods=min_periods).sum()
        count = mask.astype(float).rolling(window, min_periods=min_periods).sum()
        return weighted / count.replace(0, np.nan), count

    @staticmethod
    def _rsi(close, period: int):
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _stage17_hold_minutes(entry_tag: str | None) -> int:
        if entry_tag:
            for token in entry_tag.split("_"):
                if token.startswith("h") and token.endswith("m") and token[1:-1].isdigit():
                    return int(token[1:-1])
        return 8

    @staticmethod
    def _stage17_tag_leverage(entry_tag: str | None) -> float | None:
        if entry_tag:
            for token in entry_tag.split("_"):
                if token.startswith("l") and token[1:].isdigit():
                    return float(token[1:])
        return None

    @staticmethod
    def _row_at_time(dataframe: DataFrame, current_time: datetime | None):
        if dataframe.empty:
            return None
        if current_time is None or "date" not in dataframe:
            return dataframe.iloc[-1]
        candle_time = pd.Timestamp(current_time)
        if candle_time.tzinfo is not None:
            candle_time = candle_time.tz_convert(None)
        dates = pd.to_datetime(dataframe["date"], utc=True, errors="coerce").dt.tz_convert(None)
        current_rows = dataframe.loc[dates <= candle_time]
        if current_rows.empty:
            return None
        return current_rows.iloc[-1]

    @staticmethod
    def _legacy_stage_exit_reason(
        trade: Trade,
        current_time: datetime,
        current_profit: float,
        stage_label: str,
    ) -> str | None:
        trade_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        if current_profit >= 0.020:
            return f"{stage_label}_legacy_fast_profit_exit"
        if trade_minutes >= 3 and current_profit >= 0.010:
            return f"{stage_label}_legacy_take_profit_exit"
        if trade_minutes >= 10 and current_profit >= 0.004:
            return f"{stage_label}_legacy_time_profit_exit"
        if trade_minutes >= 2 and current_profit <= -0.012:
            return f"{stage_label}_legacy_fast_loss_exit"
        if trade_minutes >= 6 and current_profit <= -0.008:
            return f"{stage_label}_legacy_adverse_loss_exit"
        if trade_minutes >= 30:
            return f"{stage_label}_legacy_max_hold_exit"
        return None

    @classmethod
    def _stage17_pair_weight(cls, pair: str) -> float:
        if pair.startswith(("DOT/", "XTZ/", "XRP/", "DOGE/")):
            return 1.14
        if pair.startswith(("AAVE/", "ETH/", "MKR/")):
            return 1.04
        if pair.startswith(("APT/", "FET/", "MANA/", "NEAR/", "SUI/")):
            return 0.82
        return 1.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)

        close = dataframe["close"].replace(0, np.nan)
        high = dataframe["high"]
        low = dataframe["low"]
        volume = dataframe["volume"]
        typical = (high + low + close) / 3

        dataframe["stage17_ema_8"] = close.ewm(span=8, adjust=False, min_periods=8).mean()
        dataframe["stage17_ema_21"] = close.ewm(span=21, adjust=False, min_periods=12).mean()
        dataframe["stage17_ema_55"] = close.ewm(span=55, adjust=False, min_periods=30).mean()
        dataframe["stage17_rsi_3"] = self._rsi(close, 3)
        dataframe["stage17_rsi_8"] = self._rsi(close, 8)

        prev_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        dataframe["stage17_atr_pct"] = self._safe_div(
            true_range.rolling(14, min_periods=5).mean(),
            close,
        )
        dataframe["stage17_volume_ratio"] = self._safe_div(
            volume.rolling(12, min_periods=4).mean(),
            volume.rolling(120, min_periods=30).mean(),
        ).fillna(1.0)
        volume_20 = volume.rolling(20, min_periods=5).sum()
        dataframe["stage17_vwap_20"] = self._safe_div(
            (typical * volume).rolling(20, min_periods=5).sum(),
            volume_20,
        )
        bb_mid = close.rolling(20, min_periods=10).mean()
        bb_std = close.rolling(20, min_periods=10).std()
        dataframe["stage17_bb_high"] = bb_mid + 2 * bb_std
        dataframe["stage17_bb_low"] = bb_mid - 2 * bb_std
        dataframe["stage17_don_high_20"] = high.rolling(20, min_periods=10).max().shift(1)
        dataframe["stage17_don_low_20"] = low.rolling(20, min_periods=10).min().shift(1)

        for period in (3, 8, 20, 60):
            dataframe[f"stage17_roc_{period}"] = close / close.shift(period) - 1

        candle_range = (high - low).replace(0, np.nan)
        dataframe["stage17_close_pos"] = self._safe_div(close - low, candle_range).fillna(0.5)
        dataframe["stage17_body_ratio"] = self._safe_div(
            (close - dataframe["open"]).abs(),
            candle_range,
        ).fillna(0.0)
        dataframe["stage17_lower_wick_pct"] = self._safe_div(
            dataframe[["open", "close"]].min(axis=1) - low,
            close,
        )
        dataframe["stage17_upper_wick_pct"] = self._safe_div(
            high - dataframe[["open", "close"]].max(axis=1),
            close,
        )
        dataframe["stage17_hot_score"] = (
            0.34 * ((dataframe["stage17_volume_ratio"] - 0.75) / 1.65).clip(0.0, 1.0)
            + 0.28 * (dataframe["stage17_roc_8"].abs() / 0.018).clip(0.0, 1.0).fillna(0.0)
            + 0.20 * (dataframe["stage17_roc_20"].abs() / 0.034).clip(0.0, 1.0).fillna(0.0)
            + 0.18 * ((dataframe["stage17_atr_pct"] - 0.0007) / 0.018).clip(0.0, 1.0)
        ).clip(0.0, 1.0)
        dataframe["stage17_risk_score"] = (
            0.46 * (dataframe["stage17_roc_3"].abs() / 0.026).clip(0.0, 1.0).fillna(0.0)
            + 0.34 * (dataframe["stage17_roc_20"].abs() / 0.060).clip(0.0, 1.0).fillna(0.0)
            + 0.20 * ((dataframe["stage17_atr_pct"] - 0.014) / 0.038).clip(0.0, 1.0)
        ).clip(0.0, 1.0)
        dataframe["stage17_trend_long"] = (
            0.26 * (close > dataframe["stage17_ema_8"]).astype(float)
            + 0.24 * (dataframe["stage17_ema_8"] > dataframe["stage17_ema_21"]).astype(float)
            + 0.18 * (dataframe["stage17_ema_21"] > dataframe["stage17_ema_55"]).astype(float)
            + 0.18 * ((dataframe["stage17_roc_20"] + 0.002) / 0.032).clip(0.0, 1.0)
            + 0.14 * ((dataframe["stage17_roc_60"] + 0.004) / 0.060).clip(0.0, 1.0)
        ).clip(0.0, 1.0)
        dataframe["stage17_trend_short"] = (
            0.26 * (close < dataframe["stage17_ema_8"]).astype(float)
            + 0.24 * (dataframe["stage17_ema_8"] < dataframe["stage17_ema_21"]).astype(float)
            + 0.18 * (dataframe["stage17_ema_21"] < dataframe["stage17_ema_55"]).astype(float)
            + 0.18 * ((-dataframe["stage17_roc_20"] + 0.002) / 0.032).clip(0.0, 1.0)
            + 0.14 * ((-dataframe["stage17_roc_60"] + 0.004) / 0.060).clip(0.0, 1.0)
        ).clip(0.0, 1.0)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)
        if "enter_long" not in dataframe:
            dataframe["enter_long"] = 0
        if "enter_short" not in dataframe:
            dataframe["enter_short"] = 0
        if "enter_tag" not in dataframe:
            dataframe["enter_tag"] = ""

        pair = metadata["pair"]
        mature_pair = pair.startswith(self.stage17_mature_prefixes)
        close = dataframe["close"].replace(0, np.nan)
        high = dataframe["high"]
        low = dataframe["low"]
        open_ = dataframe["open"]
        atr = dataframe["stage17_atr_pct"].fillna(0.0)
        volume_ratio = dataframe["stage17_volume_ratio"].fillna(1.0)
        hot = dataframe["stage17_hot_score"].fillna(0.0)
        risk = dataframe["stage17_risk_score"].fillna(1.0)
        rsi_3 = dataframe["stage17_rsi_3"].fillna(50.0)
        rsi_8 = dataframe["stage17_rsi_8"].fillna(50.0)
        close_pos = dataframe["stage17_close_pos"].fillna(0.5)
        body = (close - open_).abs()
        lower_wick = dataframe[["open", "close"]].min(axis=1) - low
        upper_wick = high - dataframe[["open", "close"]].max(axis=1)
        wick_long = lower_wick / (body + close * 0.0007)
        wick_short = upper_wick / (body + close * 0.0007)
        body_ratio = dataframe["stage17_body_ratio"].fillna(0.0)

        tradable = (
            mature_pair
            & (atr > 0.00055)
            & (atr < 0.032)
            & (volume_ratio > 0.72)
            & (risk < 0.82)
            & (dataframe["volume"] > 0)
        )
        raw_momo_long = (
            tradable
            & (dataframe["stage17_trend_long"] > 0.70)
            & (hot > 0.48)
            & (risk < 0.72)
            & (dataframe["stage17_roc_3"] > 0.0016)
            & (dataframe["stage17_roc_8"] > 0.0045)
            & (
                (close > dataframe["stage17_don_high_20"] * 1.0006)
                | (close > dataframe["stage17_vwap_20"] * 1.0026)
            )
            & (volume_ratio > 1.05)
            & (close_pos > 0.60)
            & (body_ratio > 0.34)
            & rsi_8.between(52, 74)
        )
        raw_momo_short = (
            tradable
            & (dataframe["stage17_trend_short"] > 0.70)
            & (hot > 0.48)
            & (risk < 0.72)
            & (dataframe["stage17_roc_3"] < -0.0016)
            & (dataframe["stage17_roc_8"] < -0.0045)
            & (
                (close < dataframe["stage17_don_low_20"] * 0.9994)
                | (close < dataframe["stage17_vwap_20"] * 0.9974)
            )
            & (volume_ratio > 1.05)
            & (close_pos < 0.40)
            & (body_ratio > 0.34)
            & rsi_8.between(26, 48)
        )
        raw_revert_long = (
            tradable
            & (dataframe["stage17_trend_short"] < 0.68)
            & (hot > 0.34)
            & (risk < 0.62)
            & (dataframe["stage17_roc_3"] < -0.0022)
            & (dataframe["stage17_roc_20"] > -0.028)
            & (
                (low < dataframe["stage17_bb_low"] * 0.9988)
                | (close < dataframe["stage17_vwap_20"] * 0.9965)
            )
            & (wick_long > 1.05)
            & (close_pos > 0.48)
            & (rsi_3 > rsi_3.shift(1))
            & rsi_3.between(12, 40)
        )
        raw_revert_short = (
            tradable
            & (dataframe["stage17_trend_long"] < 0.68)
            & (hot > 0.34)
            & (risk < 0.62)
            & (dataframe["stage17_roc_3"] > 0.0022)
            & (dataframe["stage17_roc_20"] < 0.028)
            & (
                (high > dataframe["stage17_bb_high"] * 1.0012)
                | (close > dataframe["stage17_vwap_20"] * 1.0035)
            )
            & (wick_short > 1.05)
            & (close_pos < 0.52)
            & (rsi_3 < rsi_3.shift(1))
            & rsi_3.between(60, 88)
        )

        horizon = self.stage17_memory_horizon
        long_result = close / close.shift(horizon) - 1 - self.stage17_fee_drag
        short_result = close.shift(horizon) / close - 1 - self.stage17_fee_drag
        long_win = (long_result > 0).astype(float)
        short_win = (short_result > 0).astype(float)

        momo_l_edge, momo_l_count = self._rolling_mean_when(
            long_result,
            raw_momo_long.shift(horizon).fillna(False),
            self.stage17_memory_window,
        )
        momo_l_win, _ = self._rolling_mean_when(
            long_win,
            raw_momo_long.shift(horizon).fillna(False),
            self.stage17_memory_window,
        )
        momo_s_edge, momo_s_count = self._rolling_mean_when(
            short_result,
            raw_momo_short.shift(horizon).fillna(False),
            self.stage17_memory_window,
        )
        momo_s_win, _ = self._rolling_mean_when(
            short_win,
            raw_momo_short.shift(horizon).fillna(False),
            self.stage17_memory_window,
        )
        revert_l_edge, revert_l_count = self._rolling_mean_when(
            long_result,
            raw_revert_long.shift(horizon).fillna(False),
            self.stage17_memory_window,
        )
        revert_l_win, _ = self._rolling_mean_when(
            long_win,
            raw_revert_long.shift(horizon).fillna(False),
            self.stage17_memory_window,
        )
        revert_s_edge, revert_s_count = self._rolling_mean_when(
            short_result,
            raw_revert_short.shift(horizon).fillna(False),
            self.stage17_memory_window,
        )
        revert_s_win, _ = self._rolling_mean_when(
            short_win,
            raw_revert_short.shift(horizon).fillna(False),
            self.stage17_memory_window,
        )

        momo_l_ok = (
            (momo_l_count >= 12)
            & (momo_l_edge > 0.0009)
            & (momo_l_win.fillna(0.0) >= 0.56)
        )
        momo_s_ok = (
            (momo_s_count >= 12)
            & (momo_s_edge > 0.0009)
            & (momo_s_win.fillna(0.0) >= 0.56)
        )
        revert_l_ok = (
            (revert_l_count >= 8)
            & (revert_l_edge > 0.00045)
            & (revert_l_win.fillna(0.0) >= 0.53)
        )
        revert_s_ok = (
            (revert_s_count >= 8)
            & (revert_s_edge > 0.00045)
            & (revert_s_win.fillna(0.0) >= 0.53)
        )

        dataframe = pd.concat(
            [
                dataframe,
                DataFrame(
                    {
                        "stage17_momo_l_edge": momo_l_edge,
                        "stage17_momo_s_edge": momo_s_edge,
                        "stage17_revert_l_edge": revert_l_edge,
                        "stage17_revert_s_edge": revert_s_edge,
                        "stage17_momo_l_count": momo_l_count,
                        "stage17_momo_s_count": momo_s_count,
                        "stage17_revert_l_count": revert_l_count,
                        "stage17_revert_s_count": revert_s_count,
                    },
                    index=dataframe.index,
                ),
            ],
            axis=1,
        )

        no_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        momo_long = no_entry & raw_momo_long & momo_l_ok
        dataframe.loc[momo_long, ["enter_long", "enter_tag"]] = (1, "s17_momo_l_h8m_l4")

        no_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        momo_short = no_entry & raw_momo_short & momo_s_ok
        dataframe.loc[momo_short, ["enter_short", "enter_tag"]] = (1, "s17_momo_s_h8m_l4")

        no_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        revert_long = no_entry & raw_revert_long & revert_l_ok
        dataframe.loc[revert_long, ["enter_long", "enter_tag"]] = (1, "s17_revert_l_h5m_l3")

        no_entry = (dataframe["enter_long"].fillna(0) != 1) & (
            dataframe["enter_short"].fillna(0) != 1
        )
        revert_short = no_entry & raw_revert_short & revert_s_ok
        dataframe.loc[revert_short, ["enter_short", "enter_tag"]] = (1, "s17_revert_s_h5m_l3")
        return dataframe

    def _stage17_scores(self, pair: str, current_time: datetime | None) -> dict[str, float]:
        scores = {
            "hot": 0.5,
            "risk": 0.5,
            "trend_long": 0.5,
            "trend_short": 0.5,
        }
        if not self.dp:
            return scores
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            row = self._row_at_time(dataframe, current_time)
        except (KeyError, ValueError, TypeError, AttributeError):
            row = None
        if row is None:
            return scores
        scores["hot"] = self._bounded(float(row.get("stage17_hot_score", 0.5)))
        scores["risk"] = self._bounded(float(row.get("stage17_risk_score", 0.5)))
        scores["trend_long"] = self._bounded(float(row.get("stage17_trend_long", 0.5)))
        scores["trend_short"] = self._bounded(float(row.get("stage17_trend_short", 0.5)))
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
        if not self._is_stage17_tag(entry_tag):
            return True

        scores = self._stage17_scores(pair, current_time)
        side_trend = scores["trend_long"] if side == "long" else scores["trend_short"]
        if scores["risk"] > 0.92 and scores["hot"] < 0.58:
            return False
        if side_trend < 0.38 and "_momo_" in (entry_tag or ""):
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
        if stake is None or not self._is_stage17_tag(entry_tag):
            return stake

        scores = self._stage17_scores(pair, current_time)
        side_trend = scores["trend_long"] if side == "long" else scores["trend_short"]
        tag_boost = 1.12 if entry_tag and "_momo_" in entry_tag else 0.94
        multiplier = self._stage17_pair_weight(pair) * tag_boost
        multiplier *= 1.0 + max(scores["hot"] - 0.48, 0.0) * 0.28
        multiplier *= 0.92 + side_trend * 0.20
        multiplier *= 1.0 - max(scores["risk"] - 0.76, 0.0) * 0.72
        multiplier = self._bounded(multiplier, 0.42, 1.24)

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
        if not self._is_stage17_tag(entry_tag):
            return target

        tag_leverage = self._stage17_tag_leverage(entry_tag)
        if tag_leverage is not None:
            target = max(target, tag_leverage)
        scores = self._stage17_scores(pair, current_time)
        side_trend = scores["trend_long"] if side == "long" else scores["trend_short"]
        if scores["hot"] > 0.64 and side_trend > 0.66 and scores["risk"] < 0.72:
            target += 0.35
        if scores["risk"] > 0.86:
            target -= 0.60
        return max(1.0, min(target, max_leverage, 5.8))

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
        if self._is_stage17_tag(trade.enter_tag):
            hold_minutes = self._stage17_hold_minutes(trade.enter_tag)
            scores = self._stage17_scores(pair, current_time)
            side_trend = scores["trend_short"] if trade.is_short else scores["trend_long"]
            if current_profit >= 0.012:
                return "stage17_hf_fast_profit_exit"
            if trade_minutes >= 1 and current_profit >= 0.006:
                return "stage17_hf_scalp_profit_exit"
            if trade_minutes >= 3 and current_profit >= 0.003:
                return "stage17_hf_time_profit_exit"
            if current_profit <= -0.0085:
                return "stage17_hf_fast_loss_exit"
            if trade_minutes >= 2 and current_profit <= -0.0048 and side_trend < 0.46:
                return "stage17_hf_decay_loss_exit"
            if trade_minutes >= hold_minutes:
                return "stage17_hf_fixed_hold_exit"
            return None
        if self._is_protected_legacy_tag(trade.enter_tag):
            exit_reason = self._legacy_stage_exit_reason(
                trade,
                current_time,
                current_profit,
                "stage17",
            )
            if exit_reason:
                return exit_reason
        if trade.enter_tag in self.guarded_short_tags and trade_minutes >= 12:
            if current_profit <= -0.016:
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
    Higher-risk Stage-17 variant with controlled concentration.
    """

    pair_stake_weights = {
        **Intp20Stage17AdaptiveScalpStrategy.pair_stake_weights,
        "DOT/": 1.22,
        "XTZ/": 1.16,
        "XRP/": 1.14,
        "DOGE/": 1.02,
    }

    tag_stake_weights = {
        **Intp20Stage17AdaptiveScalpStrategy.tag_stake_weights,
        "s13_02_dot_rsi_s_lc_h24_l4": 1.42,
        "s9_08_xtz_rsi_s_lc_h24_l4": 1.34,
        "s9_10_xrp_rsi_s_mx_h24_l4": 1.28,
        "s15_02_doge_vwap_l_mchop_h30m_l5": 1.16,
        "s15_03_xrp_vwap_l_mhv_h30m_l5": 1.12,
    }

    max_stake_multiplier = 2.35
    max_boost_leverage = 7.5
