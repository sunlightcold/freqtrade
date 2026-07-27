"""Recovery-aware checkpoint exits layered on the Stage42 trailing model."""

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
    from user_data.scripts.research_stage41_trailing_exit import resolve_trailing
except ModuleNotFoundError:
    from research_stage31_tp_horizon import DEFAULT_PAIRS, WINDOWS, make_signals
    from research_stage36_path_exit import EventPaths, build_event_paths, execute_portfolio
    from research_stage40_wide_tail import load_pair, metrics
    from research_stage41_trailing_exit import resolve_trailing


@dataclass(frozen=True)
class RecoveryProfile:
    checkpoint: int
    floor: float
    slope_window: int
    slope_ceiling: float


def resolve_recovery_checkpoint(
    event: EventPaths,
    hold: int,
    profile: RecoveryProfile,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Exit a losing, not-yet-activated trade only while it is still deteriorating."""
    exit_offsets, underlying, reason = resolve_trailing(
        event,
        activation=0.008,
        trail=0.002,
        stop=0.20,
        hold=hold,
    )
    checkpoint_offset = profile.checkpoint - 1
    slope_start = checkpoint_offset - profile.slope_window
    current_return = event.close_return[:, checkpoint_offset]
    prior_return = event.close_return[:, slope_start]
    recent_slope = current_return - prior_return
    peak_before_checkpoint = event.favorable[:, : profile.checkpoint].max(axis=1)
    no_activation = peak_before_checkpoint < 0.008
    checkpoint_exit = (
        (exit_offsets > checkpoint_offset)
        & no_activation
        & (current_return <= profile.floor)
        & (recent_slope <= profile.slope_ceiling)
    )
    exit_offsets = np.where(checkpoint_exit, checkpoint_offset, exit_offsets)
    underlying = np.where(checkpoint_exit, current_return, underlying)
    reason = np.where(checkpoint_exit, "recovery_checkpoint", reason)
    return exit_offsets.astype(np.int32), underlying, reason


def trades_for_side(
    events: list[EventPaths],
    hold: int,
    profile: RecoveryProfile,
    cost: float,
    leverage: float,
) -> pd.DataFrame:
    parts = []
    for event in events:
        exit_offsets, underlying, reason = resolve_recovery_checkpoint(event, hold, profile)
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="user_data/data")
    parser.add_argument("--pairs", nargs="+", default=DEFAULT_PAIRS)
    parser.add_argument("--cost", type=float, default=0.0007)
    parser.add_argument("--leverage", type=float, default=4.0)
    parser.add_argument("--stake-fraction", type=float, default=0.10)
    parser.add_argument("--max-slots", type=int, default=9)
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    checkpoints = (15, 30, 45, 60)
    floors = (-0.030, -0.020, -0.010, -0.005, 0.0)
    slope_windows = (5, 10, 15)
    slope_ceilings = (-0.010, -0.005, 0.0, 0.005)
    profiles = [
        RecoveryProfile(checkpoint, floor, slope_window, slope_ceiling)
        for checkpoint, floor, slope_window, slope_ceiling in itertools.product(
            checkpoints, floors, slope_windows, slope_ceilings
        )
        if slope_window < checkpoint
    ]

    data_dir = Path(args.data_dir)
    btc_close = load_pair(data_dir, "BTC")["close"]
    events = {"long": [], "short": []}
    for number, pair in enumerate(args.pairs, 1):
        dataframe = load_pair(data_dir, pair)
        for side, shock in (("long", 0.025), ("short", 0.060)):
            signals = make_signals(dataframe, btc_close, 30, shock, 2.0, side)
            events[side].append(build_event_paths(dataframe, signals, pair, side, 120))
        print(f"loaded,{number}/{len(args.pairs)},{pair}", flush=True)

    ranked = []
    for number, profile in enumerate(profiles, 1):
        combined = pd.concat(
            [
                trades_for_side(events["long"], 90, profile, args.cost, args.leverage),
                trades_for_side(events["short"], 120, profile, args.cost, args.leverage),
            ],
            ignore_index=True,
        )
        trades = execute_portfolio(combined, args.max_slots)
        result = metrics(trades, *WINDOWS["development"], args.stake_fraction)
        ranked.append((development_score(result), profile, trades))
        if number % 40 == 0:
            print(f"searched,{number}/{len(profiles)}", flush=True)
    ranked.sort(key=lambda item: item[0], reverse=True)

    print(
        "rank,checkpoint,floor,slope_window,slope_ceiling,window,trades,tpd,"
        "winrate,return,daily,pf,max_dd,long,short,stops,checkpoints"
    )
    for rank, (_, profile, trades) in enumerate(ranked[: args.top], 1):
        for window_name, window in WINDOWS.items():
            result = metrics(trades, *window, args.stake_fraction)
            selected = trades[
                (trades["entry_date"] >= window[0]) & (trades["entry_date"] < window[1])
            ]
            checkpoints_hit = int((selected["reason"] == "recovery_checkpoint").sum())
            print(
                f"{rank},{profile.checkpoint},{profile.floor:.4f},"
                f"{profile.slope_window},{profile.slope_ceiling:.4f},{window_name},"
                f"{result['trades']},{result['tpd']:.3f},{result['wr']:.4f},"
                f"{result['return']:.4f},{result['daily']:.5f},{result['pf']:.3f},"
                f"{result['dd']:.4f},{result['long']},{result['short']},"
                f"{result['stops']},{checkpoints_hit}"
            )


if __name__ == "__main__":
    main()
