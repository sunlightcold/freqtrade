"""No-progress checkpoint exits layered on the Stage42 trailing model."""

from __future__ import annotations

import argparse
import itertools
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from research_stage31_tp_horizon import DEFAULT_PAIRS, WINDOWS, make_signals
from research_stage36_path_exit import EventPaths, build_event_paths, execute_portfolio
from research_stage40_wide_tail import load_pair, metrics
from research_stage41_trailing_exit import resolve_trailing


@dataclass(frozen=True)
class CheckpointProfile:
    checkpoint: int
    floor: float


def resolve_checkpoint(
    event: EventPaths,
    hold: int,
    checkpoint: int,
    floor: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    exit_offsets, underlying, reason = resolve_trailing(
        event,
        activation=0.008,
        trail=0.002,
        stop=0.20,
        hold=hold,
    )
    checkpoint_offset = checkpoint - 1
    checkpoint_return = event.close_return[:, checkpoint_offset]
    no_progress = (exit_offsets > checkpoint_offset) & (checkpoint_return <= floor)
    exit_offsets = np.where(no_progress, checkpoint_offset, exit_offsets)
    underlying = np.where(no_progress, checkpoint_return, underlying)
    reason = np.where(no_progress, "checkpoint", reason)
    return exit_offsets, underlying, reason


def trades_for_side(
    events: list[EventPaths],
    hold: int,
    checkpoint: int,
    floor: float,
    cost: float,
    leverage: float,
) -> pd.DataFrame:
    parts = []
    for event in events:
        exit_offsets, underlying, reason = resolve_checkpoint(
            event, hold, checkpoint, floor
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="user_data/data")
    parser.add_argument("--pairs", nargs="+", default=DEFAULT_PAIRS)
    parser.add_argument("--cost", type=float, default=0.0007)
    parser.add_argument("--leverage", type=float, default=4.0)
    parser.add_argument("--stake-fraction", type=float, default=0.10)
    parser.add_argument("--max-slots", type=int, default=9)
    args = parser.parse_args()

    checkpoints = (15, 30, 45, 60)
    floors = (-0.020, -0.010, -0.005, 0.0, 0.002)
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
    for checkpoint, floor in itertools.product(checkpoints, floors):
        combined = pd.concat(
            [
                trades_for_side(
                    events["long"], 90, checkpoint, floor, args.cost, args.leverage
                ),
                trades_for_side(
                    events["short"], 120, checkpoint, floor, args.cost, args.leverage
                ),
            ],
            ignore_index=True,
        )
        trades = execute_portfolio(combined, args.max_slots)
        result = metrics(trades, *WINDOWS["development"], args.stake_fraction)
        ranked.append((development_score(result), CheckpointProfile(checkpoint, floor), trades))
    ranked.sort(key=lambda item: item[0], reverse=True)

    print(
        "rank,checkpoint,floor,window,trades,tpd,winrate,return,daily,pf,max_dd,long,short,stops"
    )
    for rank, (_, profile, trades) in enumerate(ranked, 1):
        for window_name, window in WINDOWS.items():
            result = metrics(trades, *window, args.stake_fraction)
            print(
                f"{rank},{profile.checkpoint},{profile.floor:.4f},{window_name},"
                f"{result['trades']},{result['tpd']:.3f},{result['wr']:.4f},"
                f"{result['return']:.4f},{result['daily']:.5f},{result['pf']:.3f},"
                f"{result['dd']:.4f},{result['long']},{result['short']},{result['stops']}"
            )


if __name__ == "__main__":
    main()
