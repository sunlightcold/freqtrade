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


def add_base_indicators(dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe = dataframe.copy()
    dataframe["ema_20"] = ema(dataframe["close"], 20)
    dataframe["ema_50"] = ema(dataframe["close"], 50)
    dataframe["ema_100"] = ema(dataframe["close"], 100)
    dataframe["ema_200"] = ema(dataframe["close"], 200)
    dataframe["rsi"] = rsi(dataframe["close"], 14)
    dataframe["atr"] = atr(dataframe, 14)
    dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
    dataframe["volume_mean_48"] = dataframe["volume"].rolling(48).mean()
    mid = dataframe["close"].rolling(20).mean()
    std = dataframe["close"].rolling(20).std()
    dataframe["bb_mid"] = mid
    dataframe["bb_low"] = mid - 2 * std
    dataframe["bb_high"] = mid + 2 * std
    dataframe["bb_width"] = (dataframe["bb_high"] - dataframe["bb_low"]) / mid
    dataframe["don_high"] = dataframe["high"].rolling(34).max().shift(1)
    dataframe["don_low"] = dataframe["low"].rolling(34).min().shift(1)
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


def build_candidates() -> list[Candidate]:
    candidates: list[Candidate] = []
    for side in ("long", "short"):
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
    return candidates


def signals_for(candidate: Candidate, dataframe: pd.DataFrame) -> pd.Series:
    if candidate.template == "mean_reversion":
        return signal_mean_reversion(dataframe, candidate.side, candidate.params)
    if candidate.template == "breakout":
        return signal_breakout(dataframe, candidate.side, candidate.params)
    if candidate.template == "trend_pullback":
        return signal_trend_pullback(dataframe, candidate.side, candidate.params)
    raise ValueError(candidate.template)


def simulate(
    dataframe: pd.DataFrame,
    signals: pd.Series,
    side: str,
    hold: int,
    tp: float,
    sl: float,
    fee: float,
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

        profit -= fee * 2
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
) -> pd.DataFrame:
    entry = dataframe["close"].shift(-1)
    exit_price = dataframe["close"].shift(-(hold + 1))
    if side == "long":
        profit = exit_price / entry - 1
    else:
        profit = entry / exit_price - 1
    profit = profit - fee * 2
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
    return {
        "trades": int(len(trades)),
        "profit": float(equity.iloc[-1] - 1),
        "daily": float((equity.iloc[-1] ** (1 / days)) - 1),
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
) -> dict:
    all_trades = []
    per_slice = {}

    for pair, dataframe in pair_data.items():
        signals = signals_for(candidate, dataframe)
        trades = simulate(dataframe, signals, candidate.side, hold, tp, sl, fee)
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
    min_slice_profit = min(value["profit"] for value in per_slice.values())
    min_slice_pf = min(value["pf"] for value in per_slice.values() if value["trades"] > 0) if total["trades"] else 0
    total["robust_score"] = (
        total["profit"]
        - total["max_dd"] * 1.6
        + min_slice_profit * 0.8
        + min_slice_pf * 0.05
    )
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
) -> dict:
    all_trades = []
    per_slice = {}

    for pair, dataframe in pair_data.items():
        trades = simulate(dataframe, pair_signals[pair], candidate.side, hold, tp, sl, fee)
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
    min_slice_profit = min(value["profit"] for value in per_slice.values())
    min_slice_pf = min(value["pf"] for value in per_slice.values() if value["trades"] > 0) if total["trades"] else 0
    total["robust_score"] = (
        total["profit"]
        - total["max_dd"] * 1.6
        + min_slice_profit * 0.8
        + min_slice_pf * 0.05
    )
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
) -> dict:
    all_trades = []
    per_slice = {}

    for pair, dataframe in pair_data.items():
        trades = simulate_fixed_hold(dataframe, pair_signals[pair], candidate.side, hold, fee)
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
    min_slice_profit = min(value["profit"] for value in per_slice.values())
    positive_slices = sum(1 for value in per_slice.values() if value["profit"] > 0)
    total["robust_score"] = (
        total["profit"]
        - total["max_dd"] * 1.4
        + min_slice_profit * 1.2
        + positive_slices * 0.1
    )
    return {
        "candidate": candidate,
        "hold": hold,
        "tp": 0.0,
        "sl": 0.0,
        "total": total,
        "slices": per_slice,
    }


def format_params(params: dict) -> str:
    return ",".join(f"{key}={value}" for key, value in sorted(params.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Fast strategy screener.")
    parser.add_argument("--data-dir", default="user_data/data")
    parser.add_argument("--timeframe", default="15min")
    parser.add_argument("--pairs", nargs="+", default=PAIRS)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--fee", type=float, default=0.0005)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    pair_data = {
        pair: add_base_indicators(load_pair(data_dir, pair, args.timeframe))
        for pair in args.pairs
    }

    candidates = build_candidates()
    results = []
    for candidate in candidates:
        pair_signals = {
            pair: signals_for(candidate, dataframe)
            for pair, dataframe in pair_data.items()
        }
        if sum(int(signals.sum()) for signals in pair_signals.values()) < 10:
            continue
        for hold in (3, 6, 12, 24):
            results.append(
                evaluate_candidate_fixed_hold(
                    pair_data,
                    candidate,
                    pair_signals,
                    hold,
                    args.fee,
                )
            )

    results.sort(key=lambda item: item["total"]["robust_score"], reverse=True)

    print(
        "rank,template,side,hold,tp,sl,trades,total_profit,daily,winrate,pf,max_dd,"
        "p2024,p2025,p2026,params"
    )
    for index, result in enumerate(results[: args.top], 1):
        candidate = result["candidate"]
        total = result["total"]
        print(
            f"{index},{candidate.template},{candidate.side},{result['hold']},"
            f"{result['tp']:.4f},{result['sl']:.4f},{total['trades']},"
            f"{total['profit']:.4f},{total['daily']:.5f},{total['winrate']:.4f},"
            f"{total['pf']:.3f},{total['max_dd']:.4f},"
            f"{result['slices']['2024']['profit']:.4f},"
            f"{result['slices']['2025']['profit']:.4f},"
            f"{result['slices']['2026']['profit']:.4f},"
            f"{format_params(candidate.params)}"
        )


if __name__ == "__main__":
    main()
