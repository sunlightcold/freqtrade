"""Conservative two-stage profit protection for Stage42 event paths."""

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
    from user_data.scripts.research_stage41_trailing_exit import development_score
except ModuleNotFoundError:
    from research_stage31_tp_horizon import DEFAULT_PAIRS, WINDOWS, make_signals
    from research_stage36_path_exit import EventPaths, build_event_paths, execute_portfolio
    from research_stage40_wide_tail import load_pair, metrics
    from research_stage41_trailing_exit import development_score


@dataclass(frozen=True)
class ProtectionProfile:
    activation: float
    floor: float


def resolve_two_stage(
    event: EventPaths,
    hold: int,
    profile: ProtectionProfile,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    favorable = event.favorable[:, :hold]
    adverse = event.adverse[:, :hold]
    close_return = event.close_return[:, :hold]
    peak = np.maximum.accumulate(favorable, axis=1)

    protection_active = np.zeros_like(peak, dtype=bool)
    protection_active[:, 1:] = peak[:, :-1] >= profile.activation
    trailing_active = peak >= 0.008
    if event.side == "long":
        trailing_return = (1 + peak) * (1 - 0.002) - 1
    else:
        trailing_return = (1 + peak) / (1 + 0.002) - 1
    dynamic_stop = np.where(
        trailing_active,
        trailing_return,
        np.where(protection_active, profile.floor, -0.20),
    )
    stop_hits = adverse <= dynamic_stop
    first_stop = np.where(stop_hits.any(axis=1), stop_hits.argmax(axis=1), hold)
    stopped = first_stop < hold
    exit_offsets = np.where(stopped, first_stop, hold - 1)
    indices = np.arange(len(event.entry_dates))
    safe_offsets = first_stop.clip(max=hold - 1)
    underlying = np.where(
        stopped,
        dynamic_stop[indices, safe_offsets],
        close_return[:, hold - 1],
    )
    exit_trailing = stopped & trailing_active[indices, safe_offsets]
    exit_protection = stopped & ~exit_trailing & protection_active[indices, safe_offsets]
    reason = np.where(
        exit_trailing,
        "trailing",
        np.where(exit_protection, "protection", np.where(stopped, "stop", "horizon")),
    )
    return exit_offsets.astype(np.int32), underlying, reason


def trades_for_side(
    events: list[EventPaths],
    hold: int,
    profile: ProtectionProfile,
    cost: float,
    leverage: float,
) -> pd.DataFrame:
    parts = []
    for event in events:
        exit_offsets, underlying, reason = resolve_two_stage(event, hold, profile)
        indices = np.arange(len(event.entry_dates))
        exit_dates = event.path_dates[indices, exit_offsets]
        accepted = []
        open_until = None
        for index, entry_date in enumerate(event.entry_dates):
            if open_until is not None and entry_date <= open_until:
                continue
            accepted.append(index)
            open_until = exit_dates[index]
        selected = np.asarray(accepted, dtype=np.int32)
        parts.append(
            pd.DataFrame(
                {
                    "pair": event.pair,
                    "side": event.side,
                    "entry_date": event.entry_dates[selected],
                    "exit_date": exit_dates[selected],
                    "profit": np.maximum(
                        leverage * (underlying[selected] - 2 * cost),
                        -0.99,
                    ),
                    "reason": reason[selected],
                }
            )
        )
    return pd.concat(parts, ignore_index=True)


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

    profiles = [
        ProtectionProfile(activation, floor)
        for activation, floor in itertools.product(
            (0.003, 0.004, 0.005, 0.006),
            (-0.002, 0.0, 0.0015, 0.003),
        )
        if floor < activation
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
    for profile in profiles:
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
    ranked.sort(key=lambda item: item[0], reverse=True)

    print(
        "rank,activation,floor,window,trades,tpd,winrate,return,daily,pf,max_dd,"
        "long,short,stops,protections"
    )
    for rank, (_, profile, trades) in enumerate(ranked[: args.top], 1):
        for window_name, window in WINDOWS.items():
            result = metrics(trades, *window, args.stake_fraction)
            selected = trades[
                (trades["entry_date"] >= window[0]) & (trades["entry_date"] < window[1])
            ]
            protections = int((selected["reason"] == "protection").sum())
            print(
                f"{rank},{profile.activation:.4f},{profile.floor:.4f},{window_name},"
                f"{result['trades']},{result['tpd']:.3f},{result['wr']:.4f},"
                f"{result['return']:.4f},{result['daily']:.5f},{result['pf']:.3f},"
                f"{result['dd']:.4f},{result['long']},{result['short']},"
                f"{result['stops']},{protections}"
            )


if __name__ == "__main__":
    main()
