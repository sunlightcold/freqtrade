"""Conservative trailing-exit study for Stage31 relative-shock events."""

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
    from user_data.scripts.research_stage40_wide_tail import load_pair, metrics
except ModuleNotFoundError:
    from research_stage31_tp_horizon import DEFAULT_PAIRS, WINDOWS, make_signals
    from research_stage36_path_exit import EventPaths, build_event_paths, execute_portfolio
    from research_stage40_wide_tail import load_pair, metrics


@dataclass(frozen=True)
class ExitProfile:
    activation: float
    trail: float
    stop: float
    long_hold: int
    short_hold: int


def resolve_trailing(
    event: EventPaths,
    activation: float,
    trail: float,
    stop: float,
    hold: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    favorable = event.favorable[:, :hold]
    adverse = event.adverse[:, :hold]
    close_return = event.close_return[:, :hold]
    peak = np.maximum.accumulate(favorable, axis=1)
    active = peak >= activation
    if event.side == "long":
        trailing_return = (1 + peak) * (1 - trail) - 1
    else:
        trailing_return = (1 + peak) / (1 + trail) - 1
    trailing_hits = active & (adverse <= trailing_return)
    stop_hits = adverse <= -stop
    first_trail = np.where(trailing_hits.any(axis=1), trailing_hits.argmax(axis=1), hold)
    first_stop = np.where(stop_hits.any(axis=1), stop_hits.argmax(axis=1), hold)
    stop_first = (first_stop <= first_trail) & (first_stop < hold)
    trail_first = (first_trail < first_stop) & (first_trail < hold)
    exit_offsets = np.where(stop_first, first_stop, np.where(trail_first, first_trail, hold - 1))
    indices = np.arange(len(event.entry_dates))
    underlying = np.where(
        stop_first,
        -stop,
        np.where(
            trail_first,
            trailing_return[indices, first_trail.clip(max=hold - 1)],
            close_return[:, hold - 1],
        ),
    )
    reason = np.where(stop_first, "stop", np.where(trail_first, "trailing", "horizon"))
    return exit_offsets, underlying, reason


def trades_for_side(
    events: list[EventPaths],
    activation: float,
    trail: float,
    stop: float,
    hold: int,
    cost: float,
    leverage: float,
) -> pd.DataFrame:
    parts = []
    for event in events:
        exit_offsets, underlying, reason = resolve_trailing(
            event, activation, trail, stop, hold
        )
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


def development_score(result: dict[str, float | int]) -> float:
    score = (
        min(float(result["wr"]), 0.80) * 5
        + min(float(result["tpd"]), 6.0) * 0.15
        + min(float(result["return"]), 2.0) * 1.5
        + min(float(result["pf"]), 2.0)
        - float(result["dd"]) * 0.75
    )
    if result["wr"] < 0.70 or result["tpd"] < 2 or result["return"] <= 0:
        score -= 5
    return score


def robust_score(
    development: dict[str, float | int],
    validation: dict[str, float | int],
) -> float:
    minimum_return = min(float(development["return"]), float(validation["return"]))
    minimum_pf = min(float(development["pf"]), float(validation["pf"]))
    minimum_winrate = min(float(development["wr"]), float(validation["wr"]))
    minimum_frequency = min(float(development["tpd"]), float(validation["tpd"]))
    worst_drawdown = max(float(development["dd"]), float(validation["dd"]))
    score = (
        min(minimum_winrate, 0.80) * 5
        + min(minimum_frequency, 6.0) * 0.15
        + min(minimum_return, 2.0) * 2.0
        + min(minimum_pf, 2.0)
        - worst_drawdown * 0.75
    )
    if minimum_winrate < 0.70 or minimum_frequency < 2 or minimum_return <= 0:
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
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument(
        "--selection",
        choices=("development", "robust"),
        default="development",
    )
    args = parser.parse_args()

    activations = (0.008, 0.010, 0.012, 0.015, 0.020)
    trails = (0.002, 0.004, 0.006, 0.008)
    stops = (0.10, 0.12, 0.15, 0.20)
    long_holds = (60, 90, 120)
    short_holds = (30, 60, 90, 120)
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
        for activation, trail, stop, hold in itertools.product(
            activations, trails, stops, holds
        ):
            side_cache[(side, activation, trail, stop, hold)] = trades_for_side(
                events[side], activation, trail, stop, hold, args.cost, args.leverage
            )

    ranked = []
    for activation, trail, stop, long_hold, short_hold in itertools.product(
        activations, trails, stops, long_holds, short_holds
    ):
        combined = pd.concat(
            [
                side_cache[("long", activation, trail, stop, long_hold)],
                side_cache[("short", activation, trail, stop, short_hold)],
            ],
            ignore_index=True,
        )
        trades = execute_portfolio(combined, args.max_slots)
        development = metrics(trades, *WINDOWS["development"], args.stake_fraction)
        validation = metrics(trades, *WINDOWS["validation"], args.stake_fraction)
        profile = ExitProfile(activation, trail, stop, long_hold, short_hold)
        score = (
            robust_score(development, validation)
            if args.selection == "robust"
            else development_score(development)
        )
        ranked.append((score, profile, trades))
    ranked.sort(key=lambda item: item[0], reverse=True)

    print(
        "rank,activation,trail,stop,long_hold,short_hold,window,trades,tpd,winrate,return,daily,pf,max_dd,long,short,stops"
    )
    for rank, (_, profile, trades) in enumerate(ranked[: args.top], 1):
        for window_name, window in WINDOWS.items():
            result = metrics(trades, *window, args.stake_fraction)
            print(
                f"{rank},{profile.activation:.4f},{profile.trail:.4f},{profile.stop:.4f},"
                f"{profile.long_hold},{profile.short_hold},{window_name},{result['trades']},"
                f"{result['tpd']:.3f},{result['wr']:.4f},{result['return']:.4f},"
                f"{result['daily']:.5f},{result['pf']:.3f},{result['dd']:.4f},"
                f"{result['long']},{result['short']},{result['stops']}"
            )


if __name__ == "__main__":
    main()
