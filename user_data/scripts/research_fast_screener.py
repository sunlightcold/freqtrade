"""
Fast local OHLCV screener for INTP20 futures strategy research.

This is a coarse search tool. It intentionally uses simple vectorized rules to
find promising pair/side/template combinations before spending time on full
Freqtrade backtests. Any candidate found here still requires native Freqtrade
validation.
"""

from __future__ import annotations

import argparse
import itertools
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


PAIRS = [
    "SOL",
    "BTC",
    "ETH",
    "XRP",
    "DOGE",
    "BNB",
    "SUI",
    "BCH",
    "TRX",
    "OP",
    "AVAX",
    "LINK",
    "APT",
    "XLM",
    "LTC",
    "AAVE",
    "MKR",
    "ETC",
    "COMP",
    "XTZ",
]


SLICES = {
    "2024": ("2024-01-01", "2024-12-31 23:59:59"),
    "2025": ("2025-01-01", "2025-12-31 23:59:59"),
    "2026": ("2026-01-01", "2026-05-31 23:59:59"),
}


@dataclass(frozen=True)
class Candidate:
    template: str
    side: str
    params: dict


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_gain = up.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = down.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(dataframe: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = dataframe["high"] - dataframe["low"]
    high_close = (dataframe["high"] - dataframe["close"].shift()).abs()
    low_close = (dataframe["low"] - dataframe["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def load_pair(data_dir: Path, pair: str, timeframe: str) -> pd.DataFrame:
    path = data_dir / "binance" / "futures" / f"{pair}_USDT_USDT-1m-futures.feather"
    dataframe = pd.read_feather(path)
    dataframe = dataframe.set_index("date").sort_index()
    if timeframe == "1m":
        return dataframe

    return (
        dataframe.resample(timeframe, label="right", closed="right")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
    )


def apply_timerange(dataframe: pd.DataFrame, timerange: str | None) -> pd.DataFrame:
    if not timerange:
        return dataframe

    start_raw, _, end_raw = timerange.partition("-")
    if start_raw:
        start = pd.Timestamp(start_raw, tz="UTC")
        dataframe = dataframe[dataframe.index >= start]
    if end_raw:
        end = pd.Timestamp(end_raw, tz="UTC")
        dataframe = dataframe[dataframe.index <= end]
    return dataframe


def add_base_indicators(dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe = dataframe.copy()
    dataframe["ema_8"] = ema(dataframe["close"], 8)
    dataframe["ema_12"] = ema(dataframe["close"], 12)
    dataframe["ema_20"] = ema(dataframe["close"], 20)
    dataframe["ema_34"] = ema(dataframe["close"], 34)
    dataframe["ema_50"] = ema(dataframe["close"], 50)
    dataframe["ema_100"] = ema(dataframe["close"], 100)
    dataframe["ema_200"] = ema(dataframe["close"], 200)
    dataframe["rsi_fast"] = rsi(dataframe["close"], 4)
    dataframe["rsi"] = rsi(dataframe["close"], 14)
    dataframe["atr"] = atr(dataframe, 14)
    dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
    dataframe["volume_mean_48"] = dataframe["volume"].rolling(48).mean()
    dataframe["volume_mean_96"] = dataframe["volume"].rolling(96).mean()
    dataframe["volume_z"] = (
        (dataframe["volume"] - dataframe["volume"].rolling(96).mean())
        / dataframe["volume"].rolling(96).std()
    )
    mid = dataframe["close"].rolling(20).mean()
    std = dataframe["close"].rolling(20).std()
    dataframe["bb_mid"] = mid
    dataframe["bb_low"] = mid - 2 * std
    dataframe["bb_high"] = mid + 2 * std
    dataframe["bb_width"] = (dataframe["bb_high"] - dataframe["bb_low"]) / mid
    dataframe["bb_width_mean_96"] = dataframe["bb_width"].rolling(96).mean()
    dataframe["bb_pct"] = (
        (dataframe["close"] - dataframe["bb_low"]) / (dataframe["bb_high"] - dataframe["bb_low"])
    )
    dataframe["don_high_12"] = dataframe["high"].rolling(12).max().shift(1)
    dataframe["don_low_12"] = dataframe["low"].rolling(12).min().shift(1)
    dataframe["don_high"] = dataframe["high"].rolling(34).max().shift(1)
    dataframe["don_low"] = dataframe["low"].rolling(34).min().shift(1)
    for period in (3, 6, 12, 24, 48):
        dataframe[f"roc_{period}"] = dataframe["close"] / dataframe["close"].shift(period) - 1
    dataframe["ema_20_slope"] = dataframe["ema_20"] / dataframe["ema_20"].shift(12) - 1
    dataframe["ema_50_slope"] = dataframe["ema_50"] / dataframe["ema_50"].shift(24) - 1
    dataframe["range_pct"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"]
    dataframe["body_pct"] = (dataframe["close"] - dataframe["open"]).abs() / dataframe["close"]
    dataframe["upper_wick_pct"] = (
        dataframe["high"] - dataframe[["open", "close"]].max(axis=1)
    ) / dataframe["close"]
    dataframe["lower_wick_pct"] = (
        dataframe[["open", "close"]].min(axis=1) - dataframe["low"]
    ) / dataframe["close"]
    typical_price = (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3
    dataframe["vwap_96"] = (
        (typical_price * dataframe["volume"]).rolling(96).sum()
        / dataframe["volume"].rolling(96).sum()
    )
    dataframe["trend_up"] = (
        (dataframe["close"] > dataframe["ema_100"])
        & (dataframe["ema_50"] > dataframe["ema_200"])
    )
    dataframe["trend_down"] = (
        (dataframe["close"] < dataframe["ema_100"])
        & (dataframe["ema_50"] < dataframe["ema_200"])
    )
    return dataframe


def signal_mean_reversion(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    atr_floor = params["atr_floor"]
    rsi_long = params["rsi_long"]
    rsi_short = params["rsi_short"]
    volume_mult = params["volume_mult"]

    risk_ok = (
        (dataframe["atr_pct"] > atr_floor)
        & (dataframe["bb_width"] > params["bb_width"])
        & (dataframe["volume"] > dataframe["volume_mean_48"] * volume_mult)
    )
    if side == "long":
        return (
            risk_ok
            & dataframe["trend_up"]
            & (dataframe["low"] < dataframe["bb_low"] * params["band_pad"])
            & (dataframe["rsi"] < rsi_long)
            & (dataframe["close"] > dataframe["close"].shift(1))
        )
    return (
        risk_ok
        & dataframe["trend_down"]
        & (dataframe["high"] > dataframe["bb_high"] / params["band_pad"])
        & (dataframe["rsi"] > rsi_short)
        & (dataframe["close"] < dataframe["close"].shift(1))
    )


def signal_breakout(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    risk_ok = (
        (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["atr_pct"] < params["atr_ceiling"])
        & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
    )
    if side == "long":
        return (
            risk_ok
            & dataframe["trend_up"]
            & (dataframe["close"] > dataframe["don_high"])
            & (dataframe["rsi"] > params["rsi_min"])
            & (dataframe["rsi"] < params["rsi_max"])
        )
    return (
        risk_ok
        & dataframe["trend_down"]
        & (dataframe["close"] < dataframe["don_low"])
        & (dataframe["rsi"] < 100 - params["rsi_min"])
        & (dataframe["rsi"] > 100 - params["rsi_max"])
    )


def signal_trend_pullback(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    risk_ok = (
        (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
    )
    if side == "long":
        near_ema = (
            (dataframe["low"] < dataframe["ema_20"] * (1 + params["ema_pad"]))
            & (dataframe["close"] > dataframe["ema_50"] * (1 - params["ema_pad"]))
        )
        return (
            risk_ok
            & dataframe["trend_up"]
            & near_ema
            & (dataframe["rsi"] > params["rsi_min"])
            & (dataframe["rsi"] < params["rsi_max"])
            & (dataframe["close"] > dataframe["open"])
        )
    near_ema = (
        (dataframe["high"] > dataframe["ema_20"] * (1 - params["ema_pad"]))
        & (dataframe["close"] < dataframe["ema_50"] * (1 + params["ema_pad"]))
    )
    return (
        risk_ok
        & dataframe["trend_down"]
        & near_ema
        & (dataframe["rsi"] < 100 - params["rsi_min"])
        & (dataframe["rsi"] > 100 - params["rsi_max"])
        & (dataframe["close"] < dataframe["open"])
    )


def signal_micro_momentum(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    risk_ok = (
        (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["atr_pct"] < params["atr_ceiling"])
        & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
        & (dataframe["volume_z"] > params["volume_z"])
        & (dataframe["bb_width"] > dataframe["bb_width_mean_96"] * params["width_mult"])
    )
    if side == "long":
        return (
            risk_ok
            & (dataframe["ema_8"] > dataframe["ema_20"])
            & (dataframe["ema_20"] > dataframe["ema_50"])
            & (dataframe["ema_20_slope"] > params["slope"])
            & (dataframe["close"] > dataframe["don_high_12"])
            & (dataframe["roc_3"] > params["roc_fast"])
            & (dataframe["roc_12"] > params["roc_slow"])
            & (dataframe["rsi_fast"] > params["rsi_fast"])
            & (dataframe["rsi"] < params["rsi_cap"])
        )
    return (
        risk_ok
        & (dataframe["ema_8"] < dataframe["ema_20"])
        & (dataframe["ema_20"] < dataframe["ema_50"])
        & (dataframe["ema_20_slope"] < -params["slope"])
        & (dataframe["close"] < dataframe["don_low_12"])
        & (dataframe["roc_3"] < -params["roc_fast"])
        & (dataframe["roc_12"] < -params["roc_slow"])
        & (dataframe["rsi_fast"] < 100 - params["rsi_fast"])
        & (dataframe["rsi"] > 100 - params["rsi_cap"])
    )


def signal_vwap_reclaim(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    crossed_above_vwap = (dataframe["close"] > dataframe["vwap_96"]) & (
        dataframe["close"].shift(1) <= dataframe["vwap_96"].shift(1)
    )
    crossed_below_vwap = (dataframe["close"] < dataframe["vwap_96"]) & (
        dataframe["close"].shift(1) >= dataframe["vwap_96"].shift(1)
    )
    risk_ok = (
        (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["atr_pct"] < params["atr_ceiling"])
        & (dataframe["volume"] > dataframe["volume_mean_96"] * params["volume_mult"])
        & (dataframe["range_pct"] > dataframe["atr_pct"] * params["range_mult"])
    )
    if side == "long":
        return (
            risk_ok
            & (dataframe["ema_20"] > dataframe["ema_50"])
            & (dataframe["roc_24"] > -params["macro_pullback"])
            & (dataframe["low"] < dataframe["vwap_96"] * (1 - params["vwap_pad"]))
            & crossed_above_vwap
            & (dataframe["rsi_fast"] > dataframe["rsi_fast"].shift(1))
            & (dataframe["rsi_fast"].shift(1) < params["rsi_reset"])
        )
    return (
        risk_ok
        & (dataframe["ema_20"] < dataframe["ema_50"])
        & (dataframe["roc_24"] < params["macro_pullback"])
        & (dataframe["high"] > dataframe["vwap_96"] * (1 + params["vwap_pad"]))
        & crossed_below_vwap
        & (dataframe["rsi_fast"] < dataframe["rsi_fast"].shift(1))
        & (dataframe["rsi_fast"].shift(1) > 100 - params["rsi_reset"])
    )


def signal_squeeze_breakout(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    squeezed = dataframe["bb_width"].shift(1) < dataframe["bb_width_mean_96"].shift(1) * params["squeeze_mult"]
    risk_ok = (
        (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["atr_pct"] < params["atr_ceiling"])
        & (dataframe["volume_z"] > params["volume_z"])
        & squeezed
    )
    if side == "long":
        return (
            risk_ok
            & (dataframe["close"] > dataframe["don_high_12"])
            & (dataframe["close"] > dataframe["ema_34"])
            & (dataframe["ema_50_slope"] > -params["slope_tolerance"])
            & (dataframe["roc_6"] > params["roc"])
            & (dataframe["rsi"] > params["rsi_min"])
            & (dataframe["rsi"] < params["rsi_max"])
        )
    return (
        risk_ok
        & (dataframe["close"] < dataframe["don_low_12"])
        & (dataframe["close"] < dataframe["ema_34"])
        & (dataframe["ema_50_slope"] < params["slope_tolerance"])
        & (dataframe["roc_6"] < -params["roc"])
        & (dataframe["rsi"] < 100 - params["rsi_min"])
        & (dataframe["rsi"] > 100 - params["rsi_max"])
    )


def signal_wick_reversal(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    risk_ok = (
        (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["atr_pct"] < params["atr_ceiling"])
        & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
        & (dataframe["bb_width"] > params["bb_width"])
    )
    if side == "long":
        capitulation = (
            (dataframe["low"] < dataframe["don_low_12"])
            | (dataframe["low"] < dataframe["bb_low"] * params["band_pad"])
        )
        return (
            risk_ok
            & capitulation
            & (dataframe["lower_wick_pct"] > dataframe["body_pct"] * params["wick_body"])
            & (dataframe["lower_wick_pct"] > dataframe["atr_pct"] * params["wick_atr"])
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["rsi_fast"] < params["rsi_fast"])
            & (dataframe["roc_12"] > -params["roc_limit"])
        )
    blowoff = (
        (dataframe["high"] > dataframe["don_high_12"])
        | (dataframe["high"] > dataframe["bb_high"] / params["band_pad"])
    )
    return (
        risk_ok
        & blowoff
        & (dataframe["upper_wick_pct"] > dataframe["body_pct"] * params["wick_body"])
        & (dataframe["upper_wick_pct"] > dataframe["atr_pct"] * params["wick_atr"])
        & (dataframe["close"] < dataframe["open"])
        & (dataframe["rsi_fast"] > 100 - params["rsi_fast"])
        & (dataframe["roc_12"] < params["roc_limit"])
    )


def build_candidates(templates: set[str], grid: str) -> list[Candidate]:
    candidates: list[Candidate] = []
    for side in ("long", "short"):
        if "mean_reversion" in templates:
            for atr_floor, bb_width, volume_mult, band_pad in itertools.product(
                [0.0025, 0.0045],
                [0.012, 0.022],
                [0.6],
                [0.998],
            ):
                candidates.append(
                    Candidate(
                        "mean_reversion",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "bb_width": bb_width,
                            "volume_mult": volume_mult,
                            "band_pad": band_pad,
                            "rsi_long": 42,
                            "rsi_short": 58,
                        },
                    )
                )
        if "breakout" in templates:
            for atr_floor, atr_ceiling, volume_mult, rsi_min, rsi_max in itertools.product(
                [0.0025, 0.0045],
                [0.030, 0.055],
                [0.8, 1.2],
                [48],
                [70],
            ):
                candidates.append(
                    Candidate(
                        "breakout",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "atr_ceiling": atr_ceiling,
                            "volume_mult": volume_mult,
                            "rsi_min": rsi_min,
                            "rsi_max": rsi_max,
                        },
                    )
                )
        if "trend_pullback" in templates:
            for atr_floor, volume_mult, ema_pad, rsi_min, rsi_max in itertools.product(
                [0.0025, 0.0045],
                [0.6, 0.9],
                [0.006, 0.012],
                [43],
                [61],
            ):
                candidates.append(
                    Candidate(
                        "trend_pullback",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "volume_mult": volume_mult,
                            "ema_pad": ema_pad,
                            "rsi_min": rsi_min,
                            "rsi_max": rsi_max,
                        },
                    )
                )
        if "micro_momentum" in templates:
            micro_grid = {
                "compact": (
                    [0.0015, 0.0025],
                    [0.018],
                    [1.0],
                    [0.4],
                    [0.90],
                    [0.0004],
                    [0.0015],
                    [0.0020],
                ),
                "wide": (
                    [0.0008, 0.0015, 0.0025],
                    [0.018, 0.030],
                    [0.8, 1.2],
                    [0.2, 0.8],
                    [0.80, 1.05],
                    [0.0002, 0.0008],
                    [0.0010, 0.0020],
                    [0.0015, 0.0030],
                ),
            }[grid]
            for (
                atr_floor,
                atr_ceiling,
                volume_mult,
                volume_z,
                width_mult,
                slope,
                roc_fast,
                roc_slow,
            ) in itertools.product(*micro_grid):
                candidates.append(
                    Candidate(
                        "micro_momentum",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "atr_ceiling": atr_ceiling,
                            "volume_mult": volume_mult,
                            "volume_z": volume_z,
                            "width_mult": width_mult,
                            "slope": slope,
                            "roc_fast": roc_fast,
                            "roc_slow": roc_slow,
                            "rsi_fast": 58,
                            "rsi_cap": 74,
                        },
                    )
                )
        if "vwap_reclaim" in templates:
            vwap_grid = {
                "compact": (
                    [0.0015, 0.0025],
                    [0.018],
                    [1.0],
                    [0.8],
                    [0.0008],
                    [38],
                ),
                "wide": (
                    [0.0008, 0.0015, 0.0025],
                    [0.018, 0.030],
                    [0.7, 1.0, 1.3],
                    [0.7, 1.0],
                    [0.0005, 0.0012],
                    [35, 42],
                ),
            }[grid]
            for atr_floor, atr_ceiling, volume_mult, range_mult, vwap_pad, rsi_reset in itertools.product(*vwap_grid):
                candidates.append(
                    Candidate(
                        "vwap_reclaim",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "atr_ceiling": atr_ceiling,
                            "volume_mult": volume_mult,
                            "range_mult": range_mult,
                            "vwap_pad": vwap_pad,
                            "rsi_reset": rsi_reset,
                            "macro_pullback": 0.045,
                        },
                    )
                )
        if "squeeze_breakout" in templates:
            squeeze_grid = {
                "compact": (
                    [0.0015, 0.0025],
                    [0.018],
                    [0.6],
                    [0.80],
                    [0.0020],
                    [0.0015],
                ),
                "wide": (
                    [0.0008, 0.0015, 0.0025],
                    [0.018, 0.030],
                    [0.4, 1.0],
                    [0.70, 0.90],
                    [0.0015, 0.0030],
                    [0.0010, 0.0020],
                ),
            }[grid]
            for atr_floor, atr_ceiling, volume_z, squeeze_mult, slope_tolerance, roc in itertools.product(*squeeze_grid):
                candidates.append(
                    Candidate(
                        "squeeze_breakout",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "atr_ceiling": atr_ceiling,
                            "volume_z": volume_z,
                            "squeeze_mult": squeeze_mult,
                            "slope_tolerance": slope_tolerance,
                            "roc": roc,
                            "rsi_min": 46,
                            "rsi_max": 74,
                        },
                    )
                )
        if "wick_reversal" in templates:
            wick_grid = {
                "compact": (
                    [0.0020, 0.0035],
                    [0.020],
                    [1.0],
                    [0.006],
                    [1.6],
                    [0.60],
                    [0.998],
                    [32],
                ),
                "wide": (
                    [0.0010, 0.0020, 0.0035],
                    [0.020, 0.035],
                    [0.8, 1.2],
                    [0.006, 0.012],
                    [1.4, 2.0],
                    [0.45, 0.80],
                    [0.998, 0.995],
                    [28, 35],
                ),
            }[grid]
            for (
                atr_floor,
                atr_ceiling,
                volume_mult,
                bb_width,
                wick_body,
                wick_atr,
                band_pad,
                rsi_fast,
            ) in itertools.product(*wick_grid):
                candidates.append(
                    Candidate(
                        "wick_reversal",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "atr_ceiling": atr_ceiling,
                            "volume_mult": volume_mult,
                            "bb_width": bb_width,
                            "wick_body": wick_body,
                            "wick_atr": wick_atr,
                            "band_pad": band_pad,
                            "rsi_fast": rsi_fast,
                            "roc_limit": 0.035,
                        },
                    )
                )
    return candidates


def signals_for(candidate: Candidate, dataframe: pd.DataFrame) -> pd.Series:
    if candidate.template == "mean_reversion":
        return signal_mean_reversion(dataframe, candidate.side, candidate.params)
    if candidate.template == "breakout":
        return signal_breakout(dataframe, candidate.side, candidate.params)
    if candidate.template == "trend_pullback":
        return signal_trend_pullback(dataframe, candidate.side, candidate.params)
    if candidate.template == "micro_momentum":
        return signal_micro_momentum(dataframe, candidate.side, candidate.params)
    if candidate.template == "vwap_reclaim":
        return signal_vwap_reclaim(dataframe, candidate.side, candidate.params)
    if candidate.template == "squeeze_breakout":
        return signal_squeeze_breakout(dataframe, candidate.side, candidate.params)
    if candidate.template == "wick_reversal":
        return signal_wick_reversal(dataframe, candidate.side, candidate.params)
    raise ValueError(candidate.template)


def simulate(
    dataframe: pd.DataFrame,
    signals: pd.Series,
    side: str,
    hold: int,
    tp: float,
    sl: float,
    fee: float,
    leverage: float,
) -> pd.DataFrame:
    entries = np.flatnonzero(signals.fillna(False).to_numpy())
    rows = []
    i = 0
    open_until = -1
    high = dataframe["high"].to_numpy()
    low = dataframe["low"].to_numpy()
    close = dataframe["close"].to_numpy()
    dates = dataframe.index.to_numpy()

    while i < len(entries):
        idx = int(entries[i])
        if idx <= open_until or idx + 2 >= len(dataframe):
            i += 1
            continue

        entry_idx = idx + 1
        entry = close[entry_idx]
        end_idx = min(entry_idx + hold, len(dataframe) - 1)
        exit_idx = end_idx
        exit_reason = "timeout"

        for j in range(entry_idx + 1, end_idx + 1):
            if side == "long":
                if low[j] <= entry * (1 - sl):
                    exit_idx = j
                    exit_reason = "stop"
                    break
                if high[j] >= entry * (1 + tp):
                    exit_idx = j
                    exit_reason = "tp"
                    break
            else:
                if high[j] >= entry * (1 + sl):
                    exit_idx = j
                    exit_reason = "stop"
                    break
                if low[j] <= entry * (1 - tp):
                    exit_idx = j
                    exit_reason = "tp"
                    break

        if side == "long":
            profit = close[exit_idx] / entry - 1
            if exit_reason == "tp":
                profit = tp
            elif exit_reason == "stop":
                profit = -sl
        else:
            profit = entry / close[exit_idx] - 1
            if exit_reason == "tp":
                profit = tp
            elif exit_reason == "stop":
                profit = -sl

        profit = profit * leverage - fee * 2 * leverage
        profit = max(profit, -0.99)
        rows.append(
            {
                "date": dates[entry_idx],
                "profit": profit,
                "exit_reason": exit_reason,
            }
        )
        open_until = exit_idx
        i += 1

    return pd.DataFrame(rows)


def simulate_fixed_hold(
    dataframe: pd.DataFrame,
    signals: pd.Series,
    side: str,
    hold: int,
    fee: float,
    leverage: float,
) -> pd.DataFrame:
    entry = dataframe["close"].shift(-1)
    exit_price = dataframe["close"].shift(-(hold + 1))
    if side == "long":
        profit = exit_price / entry - 1
    else:
        profit = entry / exit_price - 1
    profit = profit * leverage - fee * 2 * leverage
    profit = profit.clip(lower=-0.99)
    selected = signals.fillna(False) & profit.notna()
    return pd.DataFrame(
        {
            "date": dataframe.index[selected],
            "profit": profit[selected].to_numpy(),
            "exit_reason": "fixed_hold",
        }
    )


def score_trades(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "trades": 0,
            "profit": 0.0,
            "daily": 0.0,
            "trades_per_day": 0.0,
            "winrate": 0.0,
            "pf": 0.0,
            "max_dd": 0.0,
        }

    profits = trades["profit"]
    equity = (1 + profits).cumprod()
    drawdown = equity / equity.cummax() - 1
    gains = profits[profits > 0].sum()
    losses = -profits[profits < 0].sum()
    days = max((trades["date"].max() - trades["date"].min()).days, 1)
    final_equity = max(float(equity.iloc[-1]), 0.000001)
    return {
        "trades": int(len(trades)),
        "profit": float(equity.iloc[-1] - 1),
        "daily": float((final_equity ** (1 / days)) - 1),
        "trades_per_day": float(len(trades) / days),
        "winrate": float((profits > 0).mean()),
        "pf": float(gains / losses) if losses else 99.0,
        "max_dd": float(-drawdown.min()),
    }


def evaluate_candidate(
    pair_data: dict[str, pd.DataFrame],
    candidate: Candidate,
    hold: int,
    tp: float,
    sl: float,
    fee: float,
    leverage: float,
) -> dict:
    all_trades = []
    per_slice = {}

    for pair, dataframe in pair_data.items():
        signals = signals_for(candidate, dataframe)
        trades = simulate(dataframe, signals, candidate.side, hold, tp, sl, fee, leverage)
        if not trades.empty:
            trades["pair"] = pair
            all_trades.append(trades)

    if not all_trades:
        combined = pd.DataFrame(columns=["date", "profit", "pair"])
    else:
        combined = pd.concat(all_trades, ignore_index=True).sort_values("date")

    for name, (start, end) in SLICES.items():
        if combined.empty:
            sliced = combined
        else:
            dates = pd.to_datetime(combined["date"], utc=True)
            sliced = combined[(dates >= pd.Timestamp(start, tz="UTC")) & (dates <= pd.Timestamp(end, tz="UTC"))]
        per_slice[name] = score_trades(sliced)

    total = score_trades(combined)
    add_robust_score(total, per_slice)
    return {
        "candidate": candidate,
        "hold": hold,
        "tp": tp,
        "sl": sl,
        "total": total,
        "slices": per_slice,
    }


def evaluate_candidate_with_signals(
    pair_data: dict[str, pd.DataFrame],
    candidate: Candidate,
    pair_signals: dict[str, pd.Series],
    hold: int,
    tp: float,
    sl: float,
    fee: float,
    leverage: float,
) -> dict:
    all_trades = []
    per_slice = {}

    for pair, dataframe in pair_data.items():
        trades = simulate(dataframe, pair_signals[pair], candidate.side, hold, tp, sl, fee, leverage)
        if not trades.empty:
            trades["pair"] = pair
            all_trades.append(trades)

    if not all_trades:
        combined = pd.DataFrame(columns=["date", "profit", "pair"])
    else:
        combined = pd.concat(all_trades, ignore_index=True).sort_values("date")

    for name, (start, end) in SLICES.items():
        if combined.empty:
            sliced = combined
        else:
            dates = pd.to_datetime(combined["date"], utc=True)
            sliced = combined[(dates >= pd.Timestamp(start, tz="UTC")) & (dates <= pd.Timestamp(end, tz="UTC"))]
        per_slice[name] = score_trades(sliced)

    total = score_trades(combined)
    add_robust_score(total, per_slice)
    return {
        "candidate": candidate,
        "hold": hold,
        "tp": tp,
        "sl": sl,
        "total": total,
        "slices": per_slice,
    }


def evaluate_candidate_fixed_hold(
    pair_data: dict[str, pd.DataFrame],
    candidate: Candidate,
    pair_signals: dict[str, pd.Series],
    hold: int,
    fee: float,
    leverage: float,
) -> dict:
    all_trades = []
    per_slice = {}

    for pair, dataframe in pair_data.items():
        trades = simulate_fixed_hold(dataframe, pair_signals[pair], candidate.side, hold, fee, leverage)
        if not trades.empty:
            trades["pair"] = pair
            all_trades.append(trades)

    if not all_trades:
        combined = pd.DataFrame(columns=["date", "profit", "pair"])
    else:
        combined = pd.concat(all_trades, ignore_index=True).sort_values("date")

    for name, (start, end) in SLICES.items():
        if combined.empty:
            sliced = combined
        else:
            dates = pd.to_datetime(combined["date"], utc=True)
            sliced = combined[(dates >= pd.Timestamp(start, tz="UTC")) & (dates <= pd.Timestamp(end, tz="UTC"))]
        per_slice[name] = score_trades(sliced)

    total = score_trades(combined)
    add_robust_score(total, per_slice)
    return {
        "candidate": candidate,
        "hold": hold,
        "tp": 0.0,
        "sl": 0.0,
        "total": total,
        "slices": per_slice,
    }


def add_robust_score(total: dict, per_slice: dict[str, dict]) -> None:
    slice_profits = [value["profit"] for value in per_slice.values()]
    slice_dailies = [value["daily"] for value in per_slice.values()]
    active_slices = [value for value in per_slice.values() if value["trades"] > 0]
    min_slice_profit = min(slice_profits)
    min_slice_daily = min(slice_dailies)
    min_slice_trades_per_day = (
        min(value["trades_per_day"] for value in active_slices) if active_slices else 0.0
    )
    positive_slices = sum(1 for value in per_slice.values() if value["profit"] > 0)
    daily_gap = abs(total["daily"] - 0.005)
    activity_gap = max(0.0, 0.50 - min_slice_trades_per_day)
    total["min_slice_profit"] = float(min_slice_profit)
    total["min_slice_daily"] = float(min_slice_daily)
    total["min_slice_trades_per_day"] = float(min_slice_trades_per_day)
    total["positive_slices"] = int(positive_slices)
    total["robust_score"] = (
        total["daily"] * 260.0
        + min_slice_daily * 360.0
        + min_slice_profit * 0.65
        + positive_slices * 0.20
        + min(total["trades_per_day"], 8.0) * 0.015
        - total["max_dd"] * 1.25
        - daily_gap * 20.0
        - activity_gap * 0.35
    )


def format_params(params: dict) -> str:
    return ",".join(f"{key}={value}" for key, value in sorted(params.items()))


def result_to_row(index: int, result: dict, leverage: float) -> dict:
    candidate = result["candidate"]
    total = result["total"]
    return {
        "rank": index,
        "scope": result.get("scope", "portfolio"),
        "template": candidate.template,
        "side": candidate.side,
        "hold": result["hold"],
        "leverage": leverage,
        "tp": result["tp"],
        "sl": result["sl"],
        "trades": total["trades"],
        "trades_per_day": total["trades_per_day"],
        "total_profit": total["profit"],
        "daily": total["daily"],
        "min_slice_daily": total["min_slice_daily"],
        "min_slice_trades_per_day": total["min_slice_trades_per_day"],
        "positive_slices": total["positive_slices"],
        "winrate": total["winrate"],
        "pf": total["pf"],
        "max_dd": total["max_dd"],
        "p2024": result["slices"]["2024"]["profit"],
        "d2024": result["slices"]["2024"]["daily"],
        "tpd2024": result["slices"]["2024"]["trades_per_day"],
        "p2025": result["slices"]["2025"]["profit"],
        "d2025": result["slices"]["2025"]["daily"],
        "tpd2025": result["slices"]["2025"]["trades_per_day"],
        "p2026": result["slices"]["2026"]["profit"],
        "d2026": result["slices"]["2026"]["daily"],
        "tpd2026": result["slices"]["2026"]["trades_per_day"],
        "robust_score": total["robust_score"],
        "params": format_params(candidate.params),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fast strategy screener.")
    parser.add_argument("--data-dir", default="user_data/data")
    parser.add_argument("--timeframe", default="15min")
    parser.add_argument("--timerange", default=None)
    parser.add_argument("--pairs", nargs="+", default=PAIRS)
    parser.add_argument(
        "--templates",
        nargs="+",
        default=["all"],
        choices=[
            "all",
            "mean_reversion",
            "breakout",
            "trend_pullback",
            "micro_momentum",
            "vwap_reclaim",
            "squeeze_breakout",
            "wick_reversal",
        ],
    )
    parser.add_argument("--grid", choices=["compact", "wide"], default="compact")
    parser.add_argument("--mode", choices=["portfolio", "per-pair"], default="portfolio")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--fee", type=float, default=0.0005)
    parser.add_argument("--leverage", type=float, default=4.0)
    parser.add_argument("--holds", nargs="+", type=int, default=[3, 6, 12, 24])
    parser.add_argument("--min-signals", type=int, default=10)
    parser.add_argument("--export-csv", default=None)
    args = parser.parse_args()

    available_templates = {
        "mean_reversion",
        "breakout",
        "trend_pullback",
        "micro_momentum",
        "vwap_reclaim",
        "squeeze_breakout",
        "wick_reversal",
    }
    templates = available_templates if "all" in args.templates else set(args.templates)

    data_dir = Path(args.data_dir)
    pair_data = {
        pair: add_base_indicators(apply_timerange(load_pair(data_dir, pair, args.timeframe), args.timerange))
        for pair in args.pairs
    }

    candidates = build_candidates(templates, args.grid)
    results = []
    for candidate in candidates:
        if args.mode == "per-pair":
            for pair, dataframe in pair_data.items():
                signals = signals_for(candidate, dataframe)
                if int(signals.sum()) < args.min_signals:
                    continue
                for hold in args.holds:
                    result = evaluate_candidate_fixed_hold(
                        {pair: dataframe},
                        candidate,
                        {pair: signals},
                        hold,
                        args.fee,
                        args.leverage,
                    )
                    result["scope"] = pair
                    results.append(result)
            continue

        pair_signals = {
            pair: signals_for(candidate, dataframe)
            for pair, dataframe in pair_data.items()
        }
        if sum(int(signals.sum()) for signals in pair_signals.values()) < args.min_signals:
            continue
        for hold in args.holds:
            result = evaluate_candidate_fixed_hold(
                pair_data,
                candidate,
                pair_signals,
                hold,
                args.fee,
                args.leverage,
            )
            result["scope"] = "portfolio"
            results.append(result)

    results.sort(key=lambda item: item["total"]["robust_score"], reverse=True)

    rows = [
        result_to_row(index, result, args.leverage)
        for index, result in enumerate(results[: args.top], 1)
    ]
    if args.export_csv:
        pd.DataFrame(rows).to_csv(args.export_csv, index=False)

    print(
        "rank,scope,template,side,hold,lev,trades,tpd,total_profit,daily,min_daily,"
        "min_tpd,positive_slices,winrate,pf,max_dd,p2024,d2024,p2025,d2025,"
        "p2026,d2026,score,params"
    )
    for row in rows:
        print(
            f"{row['rank']},{row['scope']},{row['template']},{row['side']},{row['hold']},"
            f"{row['leverage']:.1f},{row['trades']},{row['trades_per_day']:.3f},"
            f"{row['total_profit']:.4f},{row['daily']:.5f},"
            f"{row['min_slice_daily']:.5f},{row['min_slice_trades_per_day']:.3f},"
            f"{row['positive_slices']},{row['winrate']:.4f},{row['pf']:.3f},"
            f"{row['max_dd']:.4f},{row['p2024']:.4f},{row['d2024']:.5f},"
            f"{row['p2025']:.4f},{row['d2025']:.5f},"
            f"{row['p2026']:.4f},{row['d2026']:.5f},"
            f"{row['robust_score']:.4f},{row['params']}"
        )


if __name__ == "__main__":
    main()
