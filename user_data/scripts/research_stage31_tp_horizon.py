"""Leakage-free take-profit/horizon study for the Stage31 entry family."""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_PAIRS = [
    "FET",
    "APT",
    "NEAR",
    "INJ",
    "DOGE",
    "FIL",
    "SOL",
    "ETC",
    "AVAX",
    "BCH",
    "LTC",
    "1000PEPE",
    "ETH",
    "ADA",
    "COMP",
    "DOT",
    "OP",
    "1000SHIB",
    "XTZ",
    "HBAR",
]
WINDOWS = {
    "development": (pd.Timestamp("2023-07-01", tz="UTC"), pd.Timestamp("2024-07-01", tz="UTC")),
    "validation": (pd.Timestamp("2024-07-01", tz="UTC"), pd.Timestamp("2025-07-01", tz="UTC")),
    "sample_out": (pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2026-07-01", tz="UTC")),
}


def load_pair(data_dir: Path, pair: str) -> pd.DataFrame:
    path = data_dir / "binance" / "futures" / f"{pair}_USDT_USDT-1m-futures.feather"
    dataframe = pd.read_feather(path, columns=["date", "high", "low", "close", "volume"])
    return dataframe.set_index("date").sort_index()


def make_signals(
    dataframe: pd.DataFrame,
    btc_close: pd.Series,
    lookback: int,
    shock: float,
    volume_floor: float,
    side: str,
) -> pd.Series:
    aligned_btc = btc_close.reindex(dataframe.index)
    relative_return = dataframe["close"].pct_change(lookback) - aligned_btc.pct_change(lookback)
    volume_ratio = dataframe["volume"] / dataframe["volume"].rolling(240).median()
    liquid = volume_ratio > volume_floor
    if side == "long":
        crossed = (relative_return < -shock) & (relative_return.shift(1) >= -shock)
    else:
        crossed = (relative_return > shock) & (relative_return.shift(1) <= shock)
    return liquid & crossed & (dataframe["volume"] > 0)


def screen_trade_inputs(
    dataframe: pd.DataFrame,
    signals: pd.Series,
    side: str,
    hold: int,
) -> pd.DataFrame:
    # This deliberately allows overlapping signals for fast screening. Native
    # Freqtrade validation later enforces pair locks and portfolio slot limits.
    forward = pd.api.indexers.FixedForwardWindowIndexer(window_size=hold)
    entry = dataframe["close"].shift(-1)
    horizon = dataframe["close"].shift(-(hold + 1))
    if side == "long":
        favorable = dataframe["high"].shift(-2).rolling(forward, min_periods=hold).max()
        favorable_return = favorable / entry - 1
        timeout_return = horizon / entry - 1
    else:
        favorable = dataframe["low"].shift(-2).rolling(forward, min_periods=hold).min()
        favorable_return = entry / favorable - 1
        timeout_return = entry / horizon - 1
    selected = signals.fillna(False) & timeout_return.notna() & favorable_return.notna()
    return pd.DataFrame(
        {
            "date": dataframe.index[selected] + pd.Timedelta(minutes=1),
            "timeout_return": timeout_return[selected].to_numpy(),
            "favorable_return": favorable_return[selected].to_numpy(),
            "side": side,
        }
    )


def apply_target(
    inputs: pd.DataFrame,
    target: float,
    cost_per_side: float,
    leverage: float,
) -> pd.DataFrame:
    target_hit = inputs["favorable_return"] >= target
    underlying_return = inputs["timeout_return"].where(~target_hit, target)
    return pd.DataFrame(
        {
            "date": inputs["date"],
            "profit": (leverage * (underlying_return - 2 * cost_per_side)).clip(lower=-0.99),
            "side": inputs["side"],
            "reason": np.where(target_hit, "target", "horizon"),
        }
    )


def metrics(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    if trades.empty:
        return {"trades": 0, "tpd": 0.0, "winrate": 0.0, "return": 0.0, "daily": 0.0, "pf": 0.0}
    dates = pd.to_datetime(trades["date"], utc=True)
    selected = trades[(dates >= start) & (dates < end)].sort_values("date")
    if selected.empty:
        return {"trades": 0, "tpd": 0.0, "winrate": 0.0, "return": 0.0, "daily": 0.0, "pf": 0.0}
    profits = selected["profit"]
    # Ten equal capital slots approximate the production max-open-trades setting.
    equity = (1 + profits * 0.10).cumprod()
    days = (end - start).days
    gains = profits[profits > 0].sum()
    losses = -profits[profits < 0].sum()
    total_return = float(equity.iloc[-1] - 1)
    return {
        "trades": len(selected),
        "tpd": float(len(selected) / days),
        "winrate": float((profits > 0).mean()),
        "return": total_return,
        "daily": float((max(1 + total_return, 1e-9) ** (1 / days)) - 1),
        "pf": float(gains / losses) if losses else 99.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="user_data/data")
    parser.add_argument("--pairs", nargs="+", default=DEFAULT_PAIRS)
    parser.add_argument("--cost", type=float, default=0.0007)
    parser.add_argument("--leverage", type=float, default=3.0)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument(
        "--entry-grid",
        action="store_true",
        help="Expand entry parameters after the fixed Stage31 diagnostic passes.",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    results = []

    lookbacks = [15, 30, 60] if args.entry_grid else [30]
    long_shocks = [0.015, 0.020, 0.025, 0.035] if args.entry_grid else [0.025]
    short_shocks = [0.025, 0.040, 0.060] if args.entry_grid else [0.060]
    volume_floors = [1.5, 2.0, 3.0] if args.entry_grid else [2.0]
    targets = [
        0.0015,
        0.0020,
        0.0030,
        0.0040,
        0.0050,
        0.0060,
        0.0075,
        0.0080,
        0.0100,
        0.0150,
    ]
    holds = [15, 30, 45, 60, 90, 120]

    if args.entry_grid:
        raise SystemExit("Entry-grid mode is disabled until the fixed-entry diagnostic passes.")

    btc = load_pair(data_dir, "BTC")["close"]
    side_buckets: dict[tuple[str, int, float], list[pd.DataFrame]] = {
        (side, hold, target): []
        for side, hold, target in itertools.product(("long", "short"), holds, targets)
    }
    lookback = lookbacks[0]
    long_shock = long_shocks[0]
    short_shock = short_shocks[0]
    volume_floor = volume_floors[0]
    for pair in args.pairs:
        dataframe = load_pair(data_dir, pair)
        for side, shock in (("long", long_shock), ("short", short_shock)):
            signals = make_signals(dataframe, btc, lookback, shock, volume_floor, side)
            for hold in holds:
                inputs = screen_trade_inputs(dataframe, signals, side, hold)
                for target in targets:
                    trades = apply_target(inputs, target, args.cost, args.leverage)
                    trades["pair"] = pair
                    side_buckets[(side, hold, target)].append(trades)

    combined_buckets = {
        key: pd.concat(parts, ignore_index=True) for key, parts in side_buckets.items()
    }
    for target, long_hold, short_hold in itertools.product(targets, holds, holds):
        combined = pd.concat(
            [
                combined_buckets[("long", long_hold, target)],
                combined_buckets[("short", short_hold, target)],
            ],
            ignore_index=True,
        )
        scores = {name: metrics(combined, *window) for name, window in WINDOWS.items()}
        dev = scores["development"]
        dev_gate = (
            dev["winrate"] >= 0.70
            and dev["tpd"] >= 2.0
            and (dev["return"] >= 1.0 or dev["daily"] >= 0.005)
        )
        # Rank strictly by development data. Validation columns are output only.
        score = (
            min(dev["winrate"], 0.85) * 4
            + min(dev["daily"], 0.01) * 200
            + min(dev["tpd"], 6) * 0.05
            + min(dev["pf"], 3) * 0.2
            - (0 if dev_gate else 5)
        )
        results.append(
            (
                score,
                lookback,
                long_shock,
                short_shock,
                volume_floor,
                target,
                long_hold,
                short_hold,
                scores,
            )
        )

    results.sort(key=lambda item: item[0], reverse=True)
    print(
        "rank,lookback,long_shock,short_shock,volume,target,long_hold,short_hold,window,trades,tpd,winrate,return,daily,pf"
    )
    for rank, result in enumerate(results[: args.top], 1):
        (
            _,
            lookback,
            long_shock,
            short_shock,
            volume_floor,
            target,
            long_hold,
            short_hold,
            scores,
        ) = result
        for window, score in scores.items():
            print(
                f"{rank},{lookback},{long_shock:.4f},{short_shock:.4f},{volume_floor:.1f},"
                f"{target:.4f},{long_hold},{short_hold},{window},{score['trades']},"
                f"{score['tpd']:.3f},{score['winrate']:.4f},{score['return']:.4f},"
                f"{score['daily']:.5f},{score['pf']:.3f}"
            )


if __name__ == "__main__":
    main()
