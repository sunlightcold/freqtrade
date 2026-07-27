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
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd


_FIXED_PROFIT_CACHE: dict[tuple[int, str, int, float, float], pd.Series] = {}


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
    regime: str = "any"


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
        dataframe.resample(pandas_timeframe(timeframe), label="right", closed="right")
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


def pandas_timeframe(timeframe: str) -> str:
    if timeframe.endswith("m") and timeframe[:-1].isdigit():
        return f"{timeframe[:-1]}min"
    return timeframe


def load_prepared_pair(
    data_dir: Path,
    pair: str,
    timeframe: str,
    timerange: str | None,
) -> pd.DataFrame:
    return add_base_indicators(apply_timerange(load_pair(data_dir, pair, timeframe), timerange))


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
    dataframe["ema_3"] = ema(dataframe["close"], 3)
    dataframe["ema_5"] = ema(dataframe["close"], 5)
    dataframe["ema_8"] = ema(dataframe["close"], 8)
    dataframe["ema_12"] = ema(dataframe["close"], 12)
    dataframe["ema_20"] = ema(dataframe["close"], 20)
    dataframe["ema_34"] = ema(dataframe["close"], 34)
    dataframe["ema_50"] = ema(dataframe["close"], 50)
    dataframe["ema_100"] = ema(dataframe["close"], 100)
    dataframe["ema_200"] = ema(dataframe["close"], 200)
    dataframe["rsi_2"] = rsi(dataframe["close"], 2)
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
    dataframe["don_high_24"] = dataframe["high"].rolling(24).max().shift(1)
    dataframe["don_low_24"] = dataframe["low"].rolling(24).min().shift(1)
    dataframe["don_high_60"] = dataframe["high"].rolling(60).max().shift(1)
    dataframe["don_low_60"] = dataframe["low"].rolling(60).min().shift(1)
    dataframe["don_high"] = dataframe["high"].rolling(34).max().shift(1)
    dataframe["don_low"] = dataframe["low"].rolling(34).min().shift(1)
    for period in (1, 3, 6, 12, 24, 48):
        dataframe[f"roc_{period}"] = dataframe["close"] / dataframe["close"].shift(period) - 1
    dataframe["ema_8_slope"] = dataframe["ema_8"] / dataframe["ema_8"].shift(8) - 1
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
    dataframe["vwap_24"] = (
        (typical_price * dataframe["volume"]).rolling(24).sum()
        / dataframe["volume"].rolling(24).sum()
    )
    dataframe["vwap_96_dist"] = dataframe["close"] / dataframe["vwap_96"] - 1
    dataframe["vwap_96_dist_mean"] = dataframe["vwap_96_dist"].rolling(96).mean()
    dataframe["vwap_96_dist_std"] = dataframe["vwap_96_dist"].rolling(96).std()
    dataframe["vwap_96_z"] = (
        (dataframe["vwap_96_dist"] - dataframe["vwap_96_dist_mean"])
        / dataframe["vwap_96_dist_std"]
    )
    session_minute = dataframe.index.hour * 60 + dataframe.index.minute
    dataframe["session_minute"] = session_minute
    session_day = dataframe.index.floor("D")
    open_window = session_minute < 30
    orb_high = dataframe["high"].where(open_window).groupby(session_day).transform("max")
    orb_low = dataframe["low"].where(open_window).groupby(session_day).transform("min")
    dataframe["orb_high_30"] = orb_high.where(session_minute >= 30)
    dataframe["orb_low_30"] = orb_low.where(session_minute >= 30)
    dataframe["orb_range_30_pct"] = (
        (dataframe["orb_high_30"] - dataframe["orb_low_30"]) / dataframe["close"]
    )
    low_14 = dataframe["low"].rolling(14).min()
    high_14 = dataframe["high"].rolling(14).max()
    dataframe["stoch_k"] = 100 * (dataframe["close"] - low_14) / (high_14 - low_14)
    dataframe["stoch_d"] = dataframe["stoch_k"].rolling(3).mean()
    money_flow = typical_price * dataframe["volume"]
    positive_flow = money_flow.where(typical_price > typical_price.shift(), 0.0)
    negative_flow = money_flow.where(typical_price < typical_price.shift(), 0.0)
    money_ratio = (
        positive_flow.rolling(14).sum()
        / negative_flow.rolling(14).sum().replace(0, np.nan)
    )
    dataframe["mfi"] = 100 - (100 / (1 + money_ratio))
    typical_mean = typical_price.rolling(20).mean()
    typical_dev = (typical_price - typical_mean).abs().rolling(20).mean()
    dataframe["cci"] = (typical_price - typical_mean) / (0.015 * typical_dev)
    dataframe["local_up"] = (
        (dataframe["close"] > dataframe["ema_50"])
        & (dataframe["ema_20"] > dataframe["ema_50"])
        & (dataframe["ema_20_slope"] > 0)
    )
    dataframe["local_down"] = (
        (dataframe["close"] < dataframe["ema_50"])
        & (dataframe["ema_20"] < dataframe["ema_50"])
        & (dataframe["ema_20_slope"] < 0)
    )
    dataframe["local_chop"] = (
        ~dataframe["local_up"]
        & ~dataframe["local_down"]
        & (dataframe["bb_width"] < dataframe["bb_width_mean_96"] * 1.10)
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


def attach_market_regime(pair_data: dict[str, pd.DataFrame], market_pair: str = "BTC") -> None:
    if market_pair not in pair_data:
        for dataframe in pair_data.values():
            dataframe["market_bull"] = True
            dataframe["market_bear"] = True
            dataframe["market_chop"] = True
            dataframe["market_high_vol"] = True
            dataframe["market_panic_down"] = True
            dataframe["market_euphoria_up"] = True
        return

    market = pair_data[market_pair]
    regime = pd.DataFrame(index=market.index)
    regime["market_bull"] = (
        (market["close"] > market["ema_200"])
        & (market["ema_50_slope"] > 0)
        & (market["rsi"] > 45)
    )
    regime["market_bear"] = (
        (market["close"] < market["ema_200"])
        & (market["ema_50_slope"] < 0)
        & (market["rsi"] < 55)
    )
    regime["market_high_vol"] = (
        (market["atr_pct"] > market["atr_pct"].rolling(288).mean() * 1.20)
        | (market["bb_width"] > market["bb_width_mean_96"] * 1.25)
    )
    regime["market_chop"] = (
        ~regime["market_bull"]
        & ~regime["market_bear"]
        & (market["bb_width"] < market["bb_width_mean_96"] * 1.15)
    )
    regime["market_panic_down"] = (market["roc_48"] < -0.035) | (market["roc_24"] < -0.025)
    regime["market_euphoria_up"] = (market["roc_48"] > 0.035) | (market["roc_24"] > 0.025)

    for dataframe in pair_data.values():
        aligned = regime.reindex(dataframe.index, method="ffill").fillna(False)
        for column in aligned.columns:
            dataframe[column] = aligned[column]


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


def signal_rsi_reversion(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    risk_ok = (
        (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["atr_pct"] < params["atr_ceiling"])
        & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
        & (dataframe["bb_width"] > params["bb_width"])
    )
    if side == "long":
        return (
            risk_ok
            & (dataframe["low"] < dataframe["bb_low"] * params["band_pad"])
            & (dataframe["rsi_2"] < params["rsi_2_long"])
            & (dataframe["stoch_k"] < params["stoch_low"])
            & (dataframe["mfi"] < params["mfi_low"])
            & (dataframe["roc_12"] > -params["macro_limit"])
            & (dataframe["close"] > dataframe["low"] + (dataframe["high"] - dataframe["low"]) * 0.35)
        )
    return (
        risk_ok
        & (dataframe["high"] > dataframe["bb_high"] / params["band_pad"])
        & (dataframe["rsi_2"] > params["rsi_2_short"])
        & (dataframe["stoch_k"] > 100 - params["stoch_low"])
        & (dataframe["mfi"] > 100 - params["mfi_low"])
        & (dataframe["roc_12"] < params["macro_limit"])
        & (dataframe["close"] < dataframe["high"] - (dataframe["high"] - dataframe["low"]) * 0.35)
    )


def signal_stoch_turn(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    crossed_up = (dataframe["stoch_k"] > dataframe["stoch_d"]) & (
        dataframe["stoch_k"].shift(1) <= dataframe["stoch_d"].shift(1)
    )
    crossed_down = (dataframe["stoch_k"] < dataframe["stoch_d"]) & (
        dataframe["stoch_k"].shift(1) >= dataframe["stoch_d"].shift(1)
    )
    risk_ok = (
        (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["atr_pct"] < params["atr_ceiling"])
        & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
        & (dataframe["range_pct"] > dataframe["atr_pct"] * params["range_mult"])
    )
    if side == "long":
        return (
            risk_ok
            & (dataframe["local_up"] | dataframe["local_chop"])
            & crossed_up
            & (dataframe["stoch_k"].shift(1) < params["turn_level"])
            & (dataframe["rsi_fast"] > dataframe["rsi_fast"].shift(1))
            & (dataframe["cci"] < params["cci_low"])
            & (dataframe["roc_6"] > -params["roc_limit"])
        )
    return (
        risk_ok
        & (dataframe["local_down"] | dataframe["local_chop"])
        & crossed_down
        & (dataframe["stoch_k"].shift(1) > 100 - params["turn_level"])
        & (dataframe["rsi_fast"] < dataframe["rsi_fast"].shift(1))
        & (dataframe["cci"] > -params["cci_low"])
        & (dataframe["roc_6"] < params["roc_limit"])
    )


def signal_range_breakout(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    squeezed = dataframe["bb_width"].shift(1) < dataframe["bb_width_mean_96"].shift(1) * params["squeeze_mult"]
    risk_ok = (
        (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["atr_pct"] < params["atr_ceiling"])
        & (dataframe["volume_z"] > params["volume_z"])
        & (dataframe["range_pct"] > dataframe["atr_pct"] * params["range_mult"])
        & squeezed
    )
    if side == "long":
        return (
            risk_ok
            & (dataframe["close"] > dataframe["don_high_24"])
            & (dataframe["close"] > dataframe["vwap_24"])
            & (dataframe["ema_8_slope"] > params["slope"])
            & (dataframe["roc_3"] > params["roc_fast"])
            & (dataframe["rsi"] > params["rsi_min"])
            & (dataframe["rsi"] < params["rsi_max"])
        )
    return (
        risk_ok
        & (dataframe["close"] < dataframe["don_low_24"])
        & (dataframe["close"] < dataframe["vwap_24"])
        & (dataframe["ema_8_slope"] < -params["slope"])
        & (dataframe["roc_3"] < -params["roc_fast"])
        & (dataframe["rsi"] < 100 - params["rsi_min"])
        & (dataframe["rsi"] > 100 - params["rsi_max"])
    )


def signal_ema_cross_scalp(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    cross_up = (dataframe["ema_3"] > dataframe["ema_8"]) & (
        dataframe["ema_3"].shift(1) <= dataframe["ema_8"].shift(1)
    )
    cross_down = (dataframe["ema_3"] < dataframe["ema_8"]) & (
        dataframe["ema_3"].shift(1) >= dataframe["ema_8"].shift(1)
    )
    risk_ok = (
        (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["atr_pct"] < params["atr_ceiling"])
        & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
        & (dataframe["bb_width"] > params["bb_width"])
    )
    if side == "long":
        return (
            risk_ok
            & cross_up
            & (dataframe["close"] > dataframe["ema_20"] * (1 - params["ema_pad"]))
            & (dataframe["ema_20_slope"] > -params["slope_tolerance"])
            & (dataframe["rsi_fast"] > params["rsi_fast_min"])
            & (dataframe["rsi_fast"] < params["rsi_fast_max"])
            & (dataframe["roc_12"] > -params["roc_limit"])
        )
    return (
        risk_ok
        & cross_down
        & (dataframe["close"] < dataframe["ema_20"] * (1 + params["ema_pad"]))
        & (dataframe["ema_20_slope"] < params["slope_tolerance"])
        & (dataframe["rsi_fast"] < 100 - params["rsi_fast_min"])
        & (dataframe["rsi_fast"] > 100 - params["rsi_fast_max"])
        & (dataframe["roc_12"] < params["roc_limit"])
    )


def signal_panic_snapback(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    risk_ok = (
        (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["atr_pct"] < params["atr_ceiling"])
        & (dataframe["volume_z"] > params["volume_z"])
        & (dataframe["range_pct"] > dataframe["atr_pct"] * params["range_mult"])
    )
    if side == "long":
        return (
            risk_ok
            & (dataframe["roc_3"] < -params["shock"])
            & (dataframe["low"] < dataframe["don_low_12"])
            & (dataframe["lower_wick_pct"] > dataframe["body_pct"] * params["wick_body"])
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["rsi_fast"] < params["rsi_fast"])
        )
    return (
        risk_ok
        & (dataframe["roc_3"] > params["shock"])
        & (dataframe["high"] > dataframe["don_high_12"])
        & (dataframe["upper_wick_pct"] > dataframe["body_pct"] * params["wick_body"])
        & (dataframe["close"] < dataframe["open"])
        & (dataframe["rsi_fast"] > 100 - params["rsi_fast"])
    )


def signal_liquidity_sweep(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    risk_ok = (
        (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["atr_pct"] < params["atr_ceiling"])
        & (dataframe["volume_z"] > params["volume_z"])
        & (dataframe["bb_width"] > params["bb_width"])
    )
    if side == "long":
        return (
            risk_ok
            & (dataframe["low"] < dataframe["don_low_24"])
            & (dataframe["close"] > dataframe["don_low_24"])
            & (dataframe["lower_wick_pct"] > dataframe["atr_pct"] * params["wick_atr"])
            & (dataframe["close"] > dataframe["vwap_24"] * (1 - params["vwap_pad"]))
            & (dataframe["rsi_2"] < params["rsi_2"])
            & (dataframe["roc_24"] > -params["macro_limit"])
        )
    return (
        risk_ok
        & (dataframe["high"] > dataframe["don_high_24"])
        & (dataframe["close"] < dataframe["don_high_24"])
        & (dataframe["upper_wick_pct"] > dataframe["atr_pct"] * params["wick_atr"])
        & (dataframe["close"] < dataframe["vwap_24"] * (1 + params["vwap_pad"]))
        & (dataframe["rsi_2"] > 100 - params["rsi_2"])
        & (dataframe["roc_24"] < params["macro_limit"])
    )


def signal_orb_breakout(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    crossed_above_orb = (dataframe["close"] > dataframe["orb_high_30"] * (1 + params["break_pad"])) & (
        dataframe["close"].shift(1) <= dataframe["orb_high_30"].shift(1) * (1 + params["break_pad"])
    )
    crossed_below_orb = (dataframe["close"] < dataframe["orb_low_30"] * (1 - params["break_pad"])) & (
        dataframe["close"].shift(1) >= dataframe["orb_low_30"].shift(1) * (1 - params["break_pad"])
    )
    time_ok = (
        (dataframe["session_minute"] >= params["start_minute"])
        & (dataframe["session_minute"] <= params["end_minute"])
    )
    risk_ok = (
        time_ok
        & (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["atr_pct"] < params["atr_ceiling"])
        & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
        & (dataframe["volume_z"] > params["volume_z"])
        & (dataframe["orb_range_30_pct"] > params["range_floor"])
        & (dataframe["orb_range_30_pct"] < params["range_ceiling"])
    )
    if side == "long":
        return (
            risk_ok
            & crossed_above_orb
            & (dataframe["close"] > dataframe["vwap_24"])
            & (dataframe["ema_20_slope"] > -params["slope_tolerance"])
            & (dataframe["rsi_fast"] > params["rsi_fast"])
            & (dataframe["rsi"] < params["rsi_cap"])
        )
    return (
        risk_ok
        & crossed_below_orb
        & (dataframe["close"] < dataframe["vwap_24"])
        & (dataframe["ema_20_slope"] < params["slope_tolerance"])
        & (dataframe["rsi_fast"] < 100 - params["rsi_fast"])
        & (dataframe["rsi"] > 100 - params["rsi_cap"])
    )


def signal_vwap_stretch_reversion(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    risk_ok = (
        (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["atr_pct"] < params["atr_ceiling"])
        & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
        & (dataframe["bb_width"] > params["bb_width"])
        & (dataframe["vwap_96_dist"].abs() > params["min_dist"])
    )
    if side == "long":
        return (
            risk_ok
            & (dataframe["vwap_96_z"] < -params["z_entry"])
            & (dataframe["close"] < dataframe["vwap_96"] * (1 - params["min_dist"]))
            & (dataframe["rsi_2"] < params["rsi_2"])
            & (dataframe["rsi_fast"] > dataframe["rsi_fast"].shift(1))
            & (dataframe["close"] > dataframe["low"] + (dataframe["high"] - dataframe["low"]) * params["close_pos"])
            & (dataframe["roc_24"] > -params["macro_limit"])
        )
    return (
        risk_ok
        & (dataframe["vwap_96_z"] > params["z_entry"])
        & (dataframe["close"] > dataframe["vwap_96"] * (1 + params["min_dist"]))
        & (dataframe["rsi_2"] > 100 - params["rsi_2"])
        & (dataframe["rsi_fast"] < dataframe["rsi_fast"].shift(1))
        & (dataframe["close"] < dataframe["high"] - (dataframe["high"] - dataframe["low"]) * params["close_pos"])
        & (dataframe["roc_24"] < params["macro_limit"])
    )


def signal_ma_offset_reversion(dataframe: pd.DataFrame, side: str, params: dict) -> pd.Series:
    risk_ok = (
        (dataframe["atr_pct"] > params["atr_floor"])
        & (dataframe["atr_pct"] < params["atr_ceiling"])
        & (dataframe["volume"] > dataframe["volume_mean_48"] * params["volume_mult"])
        & (dataframe["bb_width"] > params["bb_width"])
        & (dataframe["range_pct"] > dataframe["atr_pct"] * params["range_mult"])
    )
    if side == "long":
        return (
            risk_ok
            & (dataframe["close"] < dataframe["ema_20"] * (1 - params["ema20_offset"]))
            & (dataframe["close"] > dataframe["ema_50"] * (1 - params["ema50_guard"]))
            & (dataframe["ema_50_slope"] > -params["slope_guard"])
            & (dataframe["rsi_2"] < params["rsi_2"])
            & (dataframe["rsi_fast"] > dataframe["rsi_fast"].shift(1))
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["roc_12"] > -params["macro_limit"])
        )
    return (
        risk_ok
        & (dataframe["close"] > dataframe["ema_20"] * (1 + params["ema20_offset"]))
        & (dataframe["close"] < dataframe["ema_50"] * (1 + params["ema50_guard"]))
        & (dataframe["ema_50_slope"] < params["slope_guard"])
        & (dataframe["rsi_2"] > 100 - params["rsi_2"])
        & (dataframe["rsi_fast"] < dataframe["rsi_fast"].shift(1))
        & (dataframe["close"] < dataframe["open"])
        & (dataframe["roc_12"] < params["macro_limit"])
    )


def regime_filter(dataframe: pd.DataFrame, regime: str, side: str) -> pd.Series:
    if regime == "any":
        return pd.Series(True, index=dataframe.index)
    if regime == "local_trend":
        return dataframe["local_up"] if side == "long" else dataframe["local_down"]
    if regime == "local_chop":
        return dataframe["local_chop"]
    if regime == "market_bull":
        return dataframe["market_bull"]
    if regime == "market_bear":
        return dataframe["market_bear"]
    if regime == "market_aligned":
        return dataframe["market_bull"] if side == "long" else dataframe["market_bear"]
    if regime == "market_contra":
        return dataframe["market_bear"] if side == "long" else dataframe["market_bull"]
    if regime == "market_chop":
        return dataframe["market_chop"]
    if regime == "market_high_vol":
        return dataframe["market_high_vol"]
    if regime == "market_extreme":
        return dataframe["market_panic_down"] if side == "long" else dataframe["market_euphoria_up"]
    raise ValueError(regime)


def expand_regimes(candidates: list[Candidate], regimes: list[str]) -> list[Candidate]:
    expanded = []
    for candidate in candidates:
        expanded.extend(replace(candidate, regime=regime) for regime in regimes)
    return expanded


def needs_market_regime(regimes: list[str]) -> bool:
    return any(regime.startswith("market_") for regime in regimes)


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
        if "rsi_reversion" in templates:
            rsi_grid = {
                "compact": (
                    [0.0006, 0.0012],
                    [0.014, 0.024],
                    [0.7],
                    [0.0035],
                    [0.998],
                    [8],
                    [28],
                    [35],
                ),
                "wide": (
                    [0.0004, 0.0008, 0.0015],
                    [0.012, 0.020, 0.035],
                    [0.5, 0.9],
                    [0.0025, 0.0050],
                    [0.998, 0.995],
                    [6, 10, 14],
                    [25, 35],
                    [30, 40],
                ),
            }[grid]
            for (
                atr_floor,
                atr_ceiling,
                volume_mult,
                bb_width,
                band_pad,
                rsi_2_long,
                stoch_low,
                mfi_low,
            ) in itertools.product(*rsi_grid):
                candidates.append(
                    Candidate(
                        "rsi_reversion",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "atr_ceiling": atr_ceiling,
                            "volume_mult": volume_mult,
                            "bb_width": bb_width,
                            "band_pad": band_pad,
                            "rsi_2_long": rsi_2_long,
                            "rsi_2_short": 100 - rsi_2_long,
                            "stoch_low": stoch_low,
                            "mfi_low": mfi_low,
                            "macro_limit": 0.045,
                        },
                    )
                )
        if "stoch_turn" in templates:
            stoch_grid = {
                "compact": (
                    [0.0006, 0.0012],
                    [0.016, 0.026],
                    [0.7],
                    [0.70],
                    [24],
                    [-70],
                    [0.018],
                ),
                "wide": (
                    [0.0004, 0.0008, 0.0015],
                    [0.014, 0.024, 0.038],
                    [0.5, 0.9],
                    [0.55, 0.85],
                    [20, 30],
                    [-55, -90],
                    [0.012, 0.025],
                ),
            }[grid]
            for atr_floor, atr_ceiling, volume_mult, range_mult, turn_level, cci_low, roc_limit in itertools.product(*stoch_grid):
                candidates.append(
                    Candidate(
                        "stoch_turn",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "atr_ceiling": atr_ceiling,
                            "volume_mult": volume_mult,
                            "range_mult": range_mult,
                            "turn_level": turn_level,
                            "cci_low": cci_low,
                            "roc_limit": roc_limit,
                        },
                    )
                )
        if "range_breakout" in templates:
            breakout_grid = {
                "compact": (
                    [0.0006, 0.0012],
                    [0.018, 0.030],
                    [0.3, 0.7],
                    [0.80],
                    [0.65],
                    [0.0002],
                    [0.0006],
                ),
                "wide": (
                    [0.0004, 0.0008, 0.0015],
                    [0.018, 0.030, 0.045],
                    [0.2, 0.6, 1.0],
                    [0.65, 0.85],
                    [0.55, 0.85],
                    [0.0000, 0.0004],
                    [0.0004, 0.0010],
                ),
            }[grid]
            for atr_floor, atr_ceiling, volume_z, squeeze_mult, range_mult, slope, roc_fast in itertools.product(*breakout_grid):
                candidates.append(
                    Candidate(
                        "range_breakout",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "atr_ceiling": atr_ceiling,
                            "volume_z": volume_z,
                            "squeeze_mult": squeeze_mult,
                            "range_mult": range_mult,
                            "slope": slope,
                            "roc_fast": roc_fast,
                            "rsi_min": 45,
                            "rsi_max": 76,
                        },
                    )
                )
        if "ema_cross_scalp" in templates:
            ema_grid = {
                "compact": (
                    [0.0005, 0.0010],
                    [0.014, 0.024],
                    [0.7],
                    [0.0025],
                    [0.0020],
                    [0.0008],
                    [38],
                    [72],
                ),
                "wide": (
                    [0.0003, 0.0008, 0.0015],
                    [0.012, 0.020, 0.034],
                    [0.5, 0.9],
                    [0.0015, 0.0040],
                    [0.0010, 0.0035],
                    [0.0005, 0.0015],
                    [34, 42],
                    [68, 78],
                ),
            }[grid]
            for (
                atr_floor,
                atr_ceiling,
                volume_mult,
                bb_width,
                ema_pad,
                slope_tolerance,
                rsi_fast_min,
                rsi_fast_max,
            ) in itertools.product(*ema_grid):
                candidates.append(
                    Candidate(
                        "ema_cross_scalp",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "atr_ceiling": atr_ceiling,
                            "volume_mult": volume_mult,
                            "bb_width": bb_width,
                            "ema_pad": ema_pad,
                            "slope_tolerance": slope_tolerance,
                            "rsi_fast_min": rsi_fast_min,
                            "rsi_fast_max": rsi_fast_max,
                            "roc_limit": 0.045,
                        },
                    )
                )
        if "panic_snapback" in templates:
            panic_grid = {
                "compact": (
                    [0.0010, 0.0020],
                    [0.030, 0.055],
                    [0.8],
                    [0.85],
                    [0.0040, 0.0070],
                    [1.4],
                    [28],
                ),
                "wide": (
                    [0.0008, 0.0015, 0.0025],
                    [0.024, 0.045, 0.070],
                    [0.5, 1.0],
                    [0.70, 1.00],
                    [0.0030, 0.0060, 0.0100],
                    [1.2, 1.8],
                    [25, 35],
                ),
            }[grid]
            for atr_floor, atr_ceiling, volume_z, range_mult, shock, wick_body, rsi_fast in itertools.product(*panic_grid):
                candidates.append(
                    Candidate(
                        "panic_snapback",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "atr_ceiling": atr_ceiling,
                            "volume_z": volume_z,
                            "range_mult": range_mult,
                            "shock": shock,
                            "wick_body": wick_body,
                            "rsi_fast": rsi_fast,
                        },
                    )
                )
        if "liquidity_sweep" in templates:
            sweep_grid = {
                "compact": (
                    [0.0008, 0.0015],
                    [0.020, 0.035],
                    [0.6],
                    [0.0040],
                    [0.60],
                    [0.0010],
                    [10],
                ),
                "wide": (
                    [0.0005, 0.0010, 0.0020],
                    [0.018, 0.030, 0.050],
                    [0.3, 0.8, 1.2],
                    [0.0025, 0.0060],
                    [0.45, 0.80],
                    [0.0005, 0.0015],
                    [8, 14],
                ),
            }[grid]
            for atr_floor, atr_ceiling, volume_z, bb_width, wick_atr, vwap_pad, rsi_2 in itertools.product(*sweep_grid):
                candidates.append(
                    Candidate(
                        "liquidity_sweep",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "atr_ceiling": atr_ceiling,
                            "volume_z": volume_z,
                            "bb_width": bb_width,
                            "wick_atr": wick_atr,
                            "vwap_pad": vwap_pad,
                            "rsi_2": rsi_2,
                            "macro_limit": 0.055,
                        },
                    )
                )
        if "orb_breakout" in templates:
            orb_grid = {
                "compact": (
                    [0.0008, 0.0015],
                    [0.018, 0.030],
                    [0.8],
                    [0.3],
                    [0.0005],
                    [0.0025],
                    [0.030],
                    [45, 60],
                    [360, 720],
                ),
                "wide": (
                    [0.0005, 0.0010, 0.0020],
                    [0.016, 0.026, 0.040],
                    [0.6, 1.0],
                    [0.0, 0.5],
                    [0.0002, 0.0008],
                    [0.0015, 0.0035],
                    [0.020, 0.045],
                    [35, 60, 120],
                    [240, 720, 1080],
                ),
            }[grid]
            for (
                atr_floor,
                atr_ceiling,
                volume_mult,
                volume_z,
                break_pad,
                range_floor,
                range_ceiling,
                start_minute,
                end_minute,
            ) in itertools.product(*orb_grid):
                candidates.append(
                    Candidate(
                        "orb_breakout",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "atr_ceiling": atr_ceiling,
                            "volume_mult": volume_mult,
                            "volume_z": volume_z,
                            "break_pad": break_pad,
                            "range_floor": range_floor,
                            "range_ceiling": range_ceiling,
                            "start_minute": start_minute,
                            "end_minute": end_minute,
                            "slope_tolerance": 0.0012,
                            "rsi_fast": 54,
                            "rsi_cap": 76,
                        },
                    )
                )
        if "vwap_stretch_reversion" in templates:
            stretch_grid = {
                "compact": (
                    [0.0006, 0.0012],
                    [0.018, 0.030],
                    [0.7],
                    [0.0025],
                    [0.0020, 0.0035],
                    [1.8, 2.4],
                    [10, 14],
                    [0.35],
                ),
                "wide": (
                    [0.0004, 0.0008, 0.0015],
                    [0.014, 0.024, 0.040],
                    [0.5, 0.9],
                    [0.0018, 0.0035],
                    [0.0015, 0.0030, 0.0050],
                    [1.5, 2.0, 2.6],
                    [8, 12, 16],
                    [0.30, 0.45],
                ),
            }[grid]
            for (
                atr_floor,
                atr_ceiling,
                volume_mult,
                bb_width,
                min_dist,
                z_entry,
                rsi_2,
                close_pos,
            ) in itertools.product(*stretch_grid):
                candidates.append(
                    Candidate(
                        "vwap_stretch_reversion",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "atr_ceiling": atr_ceiling,
                            "volume_mult": volume_mult,
                            "bb_width": bb_width,
                            "min_dist": min_dist,
                            "z_entry": z_entry,
                            "rsi_2": rsi_2,
                            "close_pos": close_pos,
                            "macro_limit": 0.055,
                        },
                    )
                )
        if "ma_offset_reversion" in templates:
            offset_grid = {
                "compact": (
                    [0.0006, 0.0012],
                    [0.018, 0.030],
                    [0.7],
                    [0.0025],
                    [0.60],
                    [0.0020, 0.0035],
                    [0.020],
                    [0.0030],
                    [10, 14],
                ),
                "wide": (
                    [0.0004, 0.0008, 0.0015],
                    [0.014, 0.024, 0.040],
                    [0.5, 0.9],
                    [0.0018, 0.0035],
                    [0.45, 0.75],
                    [0.0015, 0.0030, 0.0050],
                    [0.014, 0.024],
                    [0.0020, 0.0045],
                    [8, 12, 16],
                ),
            }[grid]
            for (
                atr_floor,
                atr_ceiling,
                volume_mult,
                bb_width,
                range_mult,
                ema20_offset,
                ema50_guard,
                slope_guard,
                rsi_2,
            ) in itertools.product(*offset_grid):
                candidates.append(
                    Candidate(
                        "ma_offset_reversion",
                        side,
                        {
                            "atr_floor": atr_floor,
                            "atr_ceiling": atr_ceiling,
                            "volume_mult": volume_mult,
                            "bb_width": bb_width,
                            "range_mult": range_mult,
                            "ema20_offset": ema20_offset,
                            "ema50_guard": ema50_guard,
                            "slope_guard": slope_guard,
                            "rsi_2": rsi_2,
                            "macro_limit": 0.055,
                        },
                    )
                )
    return candidates


def signals_for(candidate: Candidate, dataframe: pd.DataFrame) -> pd.Series:
    if candidate.template == "mean_reversion":
        signal = signal_mean_reversion(dataframe, candidate.side, candidate.params)
    elif candidate.template == "breakout":
        signal = signal_breakout(dataframe, candidate.side, candidate.params)
    elif candidate.template == "trend_pullback":
        signal = signal_trend_pullback(dataframe, candidate.side, candidate.params)
    elif candidate.template == "micro_momentum":
        signal = signal_micro_momentum(dataframe, candidate.side, candidate.params)
    elif candidate.template == "vwap_reclaim":
        signal = signal_vwap_reclaim(dataframe, candidate.side, candidate.params)
    elif candidate.template == "squeeze_breakout":
        signal = signal_squeeze_breakout(dataframe, candidate.side, candidate.params)
    elif candidate.template == "wick_reversal":
        signal = signal_wick_reversal(dataframe, candidate.side, candidate.params)
    elif candidate.template == "rsi_reversion":
        signal = signal_rsi_reversion(dataframe, candidate.side, candidate.params)
    elif candidate.template == "stoch_turn":
        signal = signal_stoch_turn(dataframe, candidate.side, candidate.params)
    elif candidate.template == "range_breakout":
        signal = signal_range_breakout(dataframe, candidate.side, candidate.params)
    elif candidate.template == "ema_cross_scalp":
        signal = signal_ema_cross_scalp(dataframe, candidate.side, candidate.params)
    elif candidate.template == "panic_snapback":
        signal = signal_panic_snapback(dataframe, candidate.side, candidate.params)
    elif candidate.template == "liquidity_sweep":
        signal = signal_liquidity_sweep(dataframe, candidate.side, candidate.params)
    elif candidate.template == "orb_breakout":
        signal = signal_orb_breakout(dataframe, candidate.side, candidate.params)
    elif candidate.template == "vwap_stretch_reversion":
        signal = signal_vwap_stretch_reversion(dataframe, candidate.side, candidate.params)
    elif candidate.template == "ma_offset_reversion":
        signal = signal_ma_offset_reversion(dataframe, candidate.side, candidate.params)
    else:
        raise ValueError(candidate.template)
    return signal & regime_filter(dataframe, candidate.regime, candidate.side)


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
    high = dataframe["high"].to_numpy()
    low = dataframe["low"].to_numpy()
    close = dataframe["close"].to_numpy()
    dates = dataframe.index.to_numpy()
    entries = entries[entries + hold + 1 < len(dataframe)]
    if not len(entries):
        return pd.DataFrame(columns=["date", "profit", "exit_reason"])

    entry_indices = entries + 1
    entry_prices = close[entry_indices]
    path_indices = entry_indices[:, None] + np.arange(1, hold + 1)
    if side == "long":
        stop_hits = low[path_indices] <= entry_prices[:, None] * (1 - sl)
        tp_hits = high[path_indices] >= entry_prices[:, None] * (1 + tp)
    else:
        stop_hits = high[path_indices] >= entry_prices[:, None] * (1 + sl)
        tp_hits = low[path_indices] <= entry_prices[:, None] * (1 - tp)

    no_hit = hold + 1
    first_stop = np.where(stop_hits.any(axis=1), stop_hits.argmax(axis=1) + 1, no_hit)
    first_tp = np.where(tp_hits.any(axis=1), tp_hits.argmax(axis=1) + 1, no_hit)
    stop_first = (first_stop <= first_tp) & (first_stop <= hold)
    tp_first = (first_tp < first_stop) & (first_tp <= hold)
    exit_offsets = np.where(stop_first, first_stop, np.where(tp_first, first_tp, hold))
    exit_indices = entry_indices + exit_offsets

    selected = []
    open_until = -1
    for index, signal_index in enumerate(entries):
        if signal_index <= open_until:
            continue
        selected.append(index)
        open_until = int(exit_indices[index])
    selected = np.asarray(selected, dtype=int)

    selected_entries = entry_prices[selected]
    selected_exits = close[exit_indices[selected]]
    if side == "long":
        profits = selected_exits / selected_entries - 1
    else:
        profits = selected_entries / selected_exits - 1
    selected_stop = stop_first[selected]
    selected_tp = tp_first[selected]
    profits = np.where(selected_stop, -sl, np.where(selected_tp, tp, profits))
    profits = np.maximum(profits * leverage - fee * 2 * leverage, -0.99)
    reasons = np.where(selected_stop, "stop", np.where(selected_tp, "tp", "timeout"))
    return pd.DataFrame(
        {
            "date": dates[entry_indices[selected]],
            "profit": profits,
            "exit_reason": reasons,
        }
    )


def simulate_fixed_hold(
    dataframe: pd.DataFrame,
    signals: pd.Series,
    side: str,
    hold: int,
    fee: float,
    leverage: float,
) -> pd.DataFrame:
    cache_key = (id(dataframe), side, hold, fee, leverage)
    profit = _FIXED_PROFIT_CACHE.get(cache_key)
    if profit is None:
        entry = dataframe["close"].shift(-1)
        exit_price = dataframe["close"].shift(-(hold + 1))
        if side == "long":
            profit = exit_price / entry - 1
        else:
            profit = entry / exit_price - 1
        profit = (profit * leverage - fee * 2 * leverage).clip(lower=-0.99)
        _FIXED_PROFIT_CACHE[cache_key] = profit
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
        "regime": candidate.regime,
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
        "wr2024": result["slices"]["2024"]["winrate"],
        "pf2024": result["slices"]["2024"]["pf"],
        "p2025": result["slices"]["2025"]["profit"],
        "d2025": result["slices"]["2025"]["daily"],
        "tpd2025": result["slices"]["2025"]["trades_per_day"],
        "wr2025": result["slices"]["2025"]["winrate"],
        "pf2025": result["slices"]["2025"]["pf"],
        "p2026": result["slices"]["2026"]["profit"],
        "d2026": result["slices"]["2026"]["daily"],
        "tpd2026": result["slices"]["2026"]["trades_per_day"],
        "wr2026": result["slices"]["2026"]["winrate"],
        "pf2026": result["slices"]["2026"]["pf"],
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
            "rsi_reversion",
            "stoch_turn",
            "range_breakout",
            "ema_cross_scalp",
            "panic_snapback",
            "liquidity_sweep",
            "orb_breakout",
            "vwap_stretch_reversion",
            "ma_offset_reversion",
        ],
    )
    parser.add_argument("--grid", choices=["compact", "wide"], default="compact")
    parser.add_argument("--mode", choices=["portfolio", "per-pair"], default="portfolio")
    parser.add_argument("--exit-mode", choices=["fixed", "bracket"], default="fixed")
    parser.add_argument(
        "--load-mode",
        choices=["auto", "bulk", "stream"],
        default="auto",
        help="Use stream for per-pair 1m sweeps to avoid loading every pair at once.",
    )
    parser.add_argument(
        "--regimes",
        nargs="+",
        default=["any"],
        choices=[
            "any",
            "local_trend",
            "local_chop",
            "market_bull",
            "market_bear",
            "market_aligned",
            "market_contra",
            "market_chop",
            "market_high_vol",
            "market_extreme",
        ],
    )
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--fee", type=float, default=0.0005)
    parser.add_argument("--leverage", type=float, default=4.0)
    parser.add_argument("--holds", nargs="+", type=int, default=[3, 6, 12, 24])
    parser.add_argument("--tps", nargs="+", type=float, default=[0.006, 0.010, 0.016])
    parser.add_argument("--sls", nargs="+", type=float, default=[0.006, 0.010, 0.016])
    parser.add_argument("--min-signals", type=int, default=10)
    parser.add_argument("--export-csv", default=None)
    parser.add_argument(
        "--walk-forward",
        action="store_true",
        help="Use three consecutive July-to-July development/validation windows.",
    )
    args = parser.parse_args()

    if args.walk_forward:
        SLICES.update(
            {
                "2024": ("2023-07-01", "2024-06-30 23:59:59"),
                "2025": ("2024-07-01", "2025-06-30 23:59:59"),
                "2026": ("2025-07-01", "2026-06-30 23:59:59"),
            }
        )

    available_templates = {
        "mean_reversion",
        "breakout",
        "trend_pullback",
        "micro_momentum",
        "vwap_reclaim",
        "squeeze_breakout",
        "wick_reversal",
        "rsi_reversion",
        "stoch_turn",
        "range_breakout",
        "ema_cross_scalp",
        "panic_snapback",
        "liquidity_sweep",
        "orb_breakout",
        "vwap_stretch_reversion",
        "ma_offset_reversion",
    }
    templates = available_templates if "all" in args.templates else set(args.templates)

    data_dir = Path(args.data_dir)
    candidates = expand_regimes(build_candidates(templates, args.grid), args.regimes)
    results = []
    stream_pairs = args.load_mode == "stream" or (
        args.load_mode == "auto" and args.mode == "per-pair"
    )

    if stream_pairs:
        market_dataframe = None
        if needs_market_regime(args.regimes):
            market_dataframe = load_prepared_pair(data_dir, "BTC", args.timeframe, args.timerange)

        for pair in args.pairs:
            dataframe = (
                market_dataframe.copy()
                if pair == "BTC" and market_dataframe is not None
                else load_prepared_pair(data_dir, pair, args.timeframe, args.timerange)
            )
            pair_data = {pair: dataframe}
            if market_dataframe is not None and pair != "BTC":
                pair_data["BTC"] = market_dataframe
            attach_market_regime(pair_data)

            for candidate in candidates:
                signals = signals_for(candidate, dataframe)
                if int(signals.sum()) < args.min_signals:
                    continue
                for hold in args.holds:
                    if args.exit_mode == "fixed":
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
                    else:
                        for tp, sl in itertools.product(args.tps, args.sls):
                            result = evaluate_candidate_with_signals(
                                {pair: dataframe},
                                candidate,
                                {pair: signals},
                                hold,
                                tp,
                                sl,
                                args.fee,
                                args.leverage,
                            )
                            result["scope"] = pair
                            results.append(result)
        pair_data = {}
    else:
        pair_data = {
            pair: load_prepared_pair(data_dir, pair, args.timeframe, args.timerange)
            for pair in args.pairs
        }
        attach_market_regime(pair_data)

        for candidate in candidates:
            if args.mode == "per-pair":
                for pair, dataframe in pair_data.items():
                    signals = signals_for(candidate, dataframe)
                    if int(signals.sum()) < args.min_signals:
                        continue
                    for hold in args.holds:
                        if args.exit_mode == "fixed":
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
                        else:
                            for tp, sl in itertools.product(args.tps, args.sls):
                                result = evaluate_candidate_with_signals(
                                    {pair: dataframe},
                                    candidate,
                                    {pair: signals},
                                    hold,
                                    tp,
                                    sl,
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
                if args.exit_mode == "fixed":
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
                else:
                    for tp, sl in itertools.product(args.tps, args.sls):
                        result = evaluate_candidate_with_signals(
                            pair_data,
                            candidate,
                            pair_signals,
                            hold,
                            tp,
                            sl,
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
        "regime,min_tpd,positive_slices,winrate,pf,max_dd,p2024,d2024,p2025,d2025,"
        "p2026,d2026,score,params"
    )
    for row in rows:
        print(
            f"{row['rank']},{row['scope']},{row['template']},{row['side']},{row['hold']},"
            f"{row['leverage']:.1f},{row['trades']},{row['trades_per_day']:.3f},"
            f"{row['total_profit']:.4f},{row['daily']:.5f},"
            f"{row['min_slice_daily']:.5f},{row['regime']},{row['min_slice_trades_per_day']:.3f},"
            f"{row['positive_slices']},{row['winrate']:.4f},{row['pf']:.3f},"
            f"{row['max_dd']:.4f},{row['p2024']:.4f},{row['d2024']:.5f},"
            f"{row['p2025']:.4f},{row['d2025']:.5f},"
            f"{row['p2026']:.4f},{row['d2026']:.5f},"
            f"{row['robust_score']:.4f},{row['params']}"
        )


if __name__ == "__main__":
    main()
