"""Wide-tail stop study for the Stage31 relative-shock event family."""

from __future__ import annotations

import argparse
import itertools
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


try:
    from user_data.scripts.research_stage31_tp_horizon import (
        DEFAULT_PAIRS,
        WINDOWS,
        make_signals,
    )
    from user_data.scripts.research_stage36_path_exit import (
        EventPaths,
        build_event_paths,
        execute_portfolio,
    )
except ModuleNotFoundError:
    from research_stage31_tp_horizon import DEFAULT_PAIRS, WINDOWS, make_signals
    from research_stage36_path_exit import EventPaths, build_event_paths, execute_portfolio


@dataclass(frozen=True)
class ExitProfile:
    target: float
    stop: float
    long_hold: int
    short_hold: int


def load_pair(data_dir: Path, pair: str) -> pd.DataFrame:
    path = data_dir / "binance" / "futures" / f"{pair}_USDT_USDT-1m-futures.feather"
    return (
        pd.read_feather(path, columns=["date", "open", "high", "low", "close", "volume"])
        .set_index("date")
        .sort_index()
    )


def trades_for_side(
    events: list[EventPaths],
    target: float,
    stop: float,
    hold: int,
    cost: float,
    leverage: float,
) -> pd.DataFrame:
    parts = []
    for event in events:
        favorable = event.favorable[:, :hold]
        adverse = event.adverse[:, :hold]
        close_return = event.close_return[:, :hold]
        target_hits = favorable >= target
        stop_hits = adverse <= -stop
        first_target = np.where(target_hits.any(axis=1), target_hits.argmax(axis=1), hold)
        first_stop = np.where(stop_hits.any(axis=1), stop_hits.argmax(axis=1), hold)
        stop_first = (first_stop <= first_target) & (first_stop < hold)
        target_first = (first_target < first_stop) & (first_target < hold)
        exit_offsets = np.where(
            stop_first,
            first_stop,
            np.where(target_first, first_target, hold - 1),
        )
        underlying = np.where(
            stop_first,
            -stop,
            np.where(target_first, target, close_return[:, hold - 1]),
        )
        reason = np.where(stop_first, "stop", np.where(target_first, "target", "horizon"))
        indices = np.arange(len(event.entry_dates))
        exit_dates = event.path_dates[indices, exit_offsets]

        accepted = []
        open_until = None
        for index, entry_date in enumerate(event.entry_dates):
            if open_until is not None and entry_date <= open_until:
                continue
            accepted.append(index)
            open_until = exit_dates[index]
        accepted_indices = np.asarray(accepted, dtype=np.int32)
        parts.append(
            pd.DataFrame(
                {
                    "pair": event.pair,
                    "side": event.side,
                    "entry_date": event.entry_dates[accepted_indices],
                    "exit_date": exit_dates[accepted_indices],
                    "profit": np.maximum(
                        leverage * (underlying[accepted_indices] - 2 * cost),
                        -0.99,
                    ),
                    "reason": reason[accepted_indices],
                }
            )
        )
    return pd.concat(parts, ignore_index=True)


def metrics(
    trades: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    stake_fraction: float,
) -> dict[str, float | int]:
    selected = trades[(trades["entry_date"] >= start) & (trades["entry_date"] < end)].copy()
    selected = selected.sort_values("exit_date")
    pnl = selected["profit"] * stake_fraction
    gains = pnl[pnl > 0].sum()
    losses = -pnl[pnl < 0].sum()
    equity = 1 + pnl.cumsum()
    drawdown = equity / equity.cummax() - 1
    days = (end - start).days
    return {
        "trades": len(selected),
        "tpd": len(selected) / days,
        "wr": float((pnl > 0).mean()),
        "return": float(pnl.sum()),
        "daily": float(pnl.sum() / days),
        "pf": float(gains / losses) if losses else 99.0,
        "dd": float(-drawdown.min()),
        "long": int((selected["side"] == "long").sum()),
        "short": int((selected["side"] == "short").sum()),
        "stops": int((selected["reason"] == "stop").sum()),
    }


def development_score(result: dict[str, float | int]) -> float:
    score = (
        min(float(result["wr"]), 0.80) * 5
        + min(float(result["tpd"]), 6.0) * 0.15
        + min(float(result["return"]), 2.0) * 1.5
        + min(float(result["pf"]), 2.0)
        - float(result["dd"]) * 0.5
    )
    if result["wr"] < 0.70 or result["tpd"] < 2 or result["return"] <= 0:
        score -= 5
    return score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="user_data/data")
    parser.add_argument("--pairs", nargs="+", default=DEFAULT_PAIRS)
    parser.add_argument("--cost", type=float, default=0.0007)
    parser.add_argument("--leverage", type=float, default=4.0)
    parser.add_argument("--stake-fraction", type=float, default=0.10)
    parser.add_argument("--max-slots", type=int, default=9)
    parser.add_argument("--max-stop", type=float, default=0.20)
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    targets = (0.008, 0.010, 0.012, 0.015)
    stops = tuple(
        stop for stop in (0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20) if stop <= args.max_stop
    )
    long_holds = (45, 60, 90, 120)
    short_holds = (30, 45, 60, 90, 120)
    max_hold = max((*long_holds, *short_holds))
    data_dir = Path(args.data_dir)
    btc_close = load_pair(data_dir, "BTC")["close"]
    events = {"long": [], "short": []}
    for number, pair in enumerate(args.pairs, 1):
        dataframe = load_pair(data_dir, pair)
        for side, shock in (("long", 0.025), ("short", 0.060)):
            signals = make_signals(dataframe, btc_close, 30, shock, 2.0, side)
            events[side].append(build_event_paths(dataframe, signals, pair, side, max_hold))
        print(f"loaded,{number}/{len(args.pairs)},{pair}", flush=True)

    side_cache = {}
    for side, holds in (("long", long_holds), ("short", short_holds)):
        for target, stop, hold in itertools.product(targets, stops, holds):
            side_cache[(side, target, stop, hold)] = trades_for_side(
                events[side], target, stop, hold, args.cost, args.leverage
            )

    development = WINDOWS["development"]
    ranked = []
    profiles = itertools.product(targets, stops, long_holds, short_holds)
    for target, stop, long_hold, short_hold in profiles:
        combined = pd.concat(
            [
                side_cache[("long", target, stop, long_hold)],
                side_cache[("short", target, stop, short_hold)],
            ],
            ignore_index=True,
        )
        trades = execute_portfolio(combined, args.max_slots)
        result = metrics(trades, *development, args.stake_fraction)
        profile = ExitProfile(target, stop, long_hold, short_hold)
        ranked.append((development_score(result), profile, trades))
    ranked.sort(key=lambda item: item[0], reverse=True)

    print(
        "rank,target,stop,long_hold,short_hold,window,trades,tpd,winrate,return,daily,pf,max_dd,long,short,stops"
    )
    for rank, (_, profile, trades) in enumerate(ranked[: args.top], 1):
        for window_name, window in WINDOWS.items():
            result = metrics(trades, *window, args.stake_fraction)
            print(
                f"{rank},{profile.target:.4f},{profile.stop:.4f},{profile.long_hold},"
                f"{profile.short_hold},{window_name},{result['trades']},{result['tpd']:.3f},"
                f"{result['wr']:.4f},{result['return']:.4f},{result['daily']:.5f},"
                f"{result['pf']:.3f},{result['dd']:.4f},{result['long']},"
                f"{result['short']},{result['stops']}"
            )


if __name__ == "__main__":
    main()
