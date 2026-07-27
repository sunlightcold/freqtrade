"""Cross-sectional long/short research across a fixed liquid futures universe."""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
from research_fast_screener import simulate, simulate_fixed_hold
from research_stage31_tp_horizon import DEFAULT_PAIRS, WINDOWS, metrics


def load_pair(data_dir: Path, pair: str) -> pd.DataFrame:
    path = data_dir / "binance" / "futures" / f"{pair}_USDT_USDT-1m-futures.feather"
    dataframe = pd.read_feather(path, columns=["date", "open", "high", "low", "close", "volume"])
    dataframe = dataframe.set_index("date").sort_index()
    return (
        dataframe.resample("15min", label="right", closed="right")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
    )


def build_signals(
    close: pd.DataFrame,
    lookback: int,
    rebalance: int,
    rank_count: int,
    z_floor: float,
    mode: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    returns = close / close.shift(lookback) - 1
    mean = returns.mean(axis=1)
    std = returns.std(axis=1).replace(0, np.nan)
    zscore = returns.sub(mean, axis=0).div(std, axis=0)
    rebalance_mask = pd.Series(False, index=close.index)
    rebalance_mask.iloc[::rebalance] = True

    high_rank = returns.rank(axis=1, ascending=False, method="first") <= rank_count
    low_rank = returns.rank(axis=1, ascending=True, method="first") <= rank_count
    high_quality = zscore >= z_floor
    low_quality = zscore <= -z_floor
    if mode == "momentum":
        long_signal = high_rank & high_quality
        short_signal = low_rank & low_quality
    else:
        long_signal = low_rank & low_quality
        short_signal = high_rank & high_quality
    return (
        long_signal & rebalance_mask.to_numpy()[:, None],
        short_signal & rebalance_mask.to_numpy()[:, None],
    )


def side_counts(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[int, int]:
    dates = pd.to_datetime(trades["date"], utc=True)
    selected = trades[(dates >= start) & (dates < end)]
    return int((selected["side"] == "long").sum()), int((selected["side"] == "short").sum())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="user_data/data")
    parser.add_argument("--pairs", nargs="+", default=DEFAULT_PAIRS)
    parser.add_argument("--cost", type=float, default=0.0007)
    parser.add_argument("--leverage", type=float, default=5.0)
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--bracket", action="store_true")
    args = parser.parse_args()

    pair_data = {pair: load_pair(Path(args.data_dir), pair) for pair in args.pairs}
    common_index = pair_data[args.pairs[0]].index
    for dataframe in pair_data.values():
        common_index = common_index.intersection(dataframe.index)
    pair_data = {pair: dataframe.reindex(common_index) for pair, dataframe in pair_data.items()}
    close = pd.DataFrame({pair: dataframe["close"] for pair, dataframe in pair_data.items()})

    modes = ["momentum", "reversion"]
    lookbacks = [4, 16, 96, 288, 672]
    rebalances = [4, 16, 96]
    holds = [4, 16, 96, 288]
    rank_counts = [1, 2, 3]
    z_floors = [0.0, 0.75, 1.25]
    brackets = [(0.0, 0.0)]
    if args.bracket:
        modes = ["reversion"]
        lookbacks = [96, 288]
        rebalances = [16, 96]
        holds = [96, 288]
        rank_counts = [1, 2]
        z_floors = [0.75, 1.25]
        brackets = [(0.005, 0.020), (0.008, 0.020), (0.008, 0.030), (0.012, 0.030)]

    results = []
    signal_cache = {}
    for mode, lookback, rebalance, hold, rank_count, z_floor, (tp, sl) in itertools.product(
        modes, lookbacks, rebalances, holds, rank_counts, z_floors, brackets
    ):
        key = (mode, lookback, rebalance, rank_count, z_floor)
        if key not in signal_cache:
            signal_cache[key] = build_signals(close, lookback, rebalance, rank_count, z_floor, mode)
        long_signals, short_signals = signal_cache[key]
        all_trades = []
        for pair, dataframe in pair_data.items():
            for side, signals in (("long", long_signals[pair]), ("short", short_signals[pair])):
                if tp > 0:
                    trades = simulate(
                        dataframe, signals, side, hold, tp, sl, args.cost, args.leverage
                    )
                else:
                    trades = simulate_fixed_hold(
                        dataframe, signals, side, hold, args.cost, args.leverage
                    )
                if not trades.empty:
                    trades["pair"] = pair
                    trades["side"] = side
                    all_trades.append(trades)
        combined = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
        scores = {name: metrics(combined, *window) for name, window in WINDOWS.items()}
        counts = {name: side_counts(combined, *window) for name, window in WINDOWS.items()}
        dev = scores["development"]
        gate = (
            dev["winrate"] >= 0.70
            and dev["tpd"] >= 2
            and (dev["return"] >= 1 or dev["daily"] >= 0.005)
        )
        dev_score = (
            min(dev["winrate"], 0.85) * 4
            + min(dev["daily"], 0.01) * 250
            + min(dev["tpd"], 8) * 0.04
            + min(dev["pf"], 3) * 0.2
            - (0 if gate else 5)
        )
        results.append(
            (
                dev_score,
                (mode, lookback, rebalance, hold, rank_count, z_floor, tp, sl),
                scores,
                counts,
            )
        )

    results.sort(key=lambda item: item[0], reverse=True)
    print(
        "rank,mode,lookback,rebalance,hold,ranks,z_floor,tp,sl,window,trades,tpd,winrate,return,daily,pf,long,short"
    )
    for rank, (_, params, scores, counts) in enumerate(results[: args.top], 1):
        mode, lookback, rebalance, hold, rank_count, z_floor, tp, sl = params
        for window, score in scores.items():
            long_count, short_count = counts[window]
            print(
                f"{rank},{mode},{lookback},{rebalance},{hold},{rank_count},{z_floor:.2f},"
                f"{tp:.4f},{sl:.4f},{window},{score['trades']},{score['tpd']:.3f},"
                f"{score['winrate']:.4f},{score['return']:.4f},{score['daily']:.5f},"
                f"{score['pf']:.3f},{long_count},{short_count}"
            )


if __name__ == "__main__":
    main()
