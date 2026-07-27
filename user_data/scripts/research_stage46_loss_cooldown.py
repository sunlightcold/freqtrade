"""Causal post-loss cooldown study for the Stage42 trailing model."""

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
    from user_data.scripts.research_stage36_path_exit import EventPaths, build_event_paths
    from user_data.scripts.research_stage40_wide_tail import load_pair, metrics
    from user_data.scripts.research_stage41_trailing_exit import resolve_trailing
except ModuleNotFoundError:
    from research_stage31_tp_horizon import DEFAULT_PAIRS, WINDOWS, make_signals
    from research_stage36_path_exit import EventPaths, build_event_paths
    from research_stage40_wide_tail import load_pair, metrics
    from research_stage41_trailing_exit import resolve_trailing


@dataclass(frozen=True)
class CooldownProfile:
    loss_trigger: float
    cooldown_minutes: int
    scope: str


def raw_trades_for_side(
    events: list[EventPaths],
    hold: int,
    cost: float,
    leverage: float,
) -> pd.DataFrame:
    parts = []
    for event in events:
        exit_offsets, underlying, reason = resolve_trailing(
            event,
            activation=0.008,
            trail=0.002,
            stop=0.20,
            hold=hold,
        )
        indices = np.arange(len(event.entry_dates))
        parts.append(
            pd.DataFrame(
                {
                    "pair": event.pair,
                    "side": event.side,
                    "entry_date": event.entry_dates,
                    "exit_date": event.path_dates[indices, exit_offsets],
                    "profit": np.maximum(leverage * (underlying - 2 * cost), -0.99),
                    "reason": reason,
                }
            )
        )
    return pd.concat(parts, ignore_index=True)


def execute_with_cooldown(
    trades: pd.DataFrame,
    profile: CooldownProfile,
    max_slots: int,
) -> pd.DataFrame:
    open_positions = []
    accepted = []
    cooldown_until: dict[str, pd.Timestamp] = {}

    for row in trades.sort_values(["entry_date", "pair"]).itertuples():
        still_open = []
        for position in open_positions:
            if position.exit_date >= row.entry_date:
                still_open.append(position)
                continue
            if position.profit <= profile.loss_trigger:
                key = position.side if profile.scope == "side" else "global"
                resume = position.exit_date + pd.Timedelta(minutes=profile.cooldown_minutes)
                cooldown_until[key] = max(cooldown_until.get(key, resume), resume)
        open_positions = still_open

        key = row.side if profile.scope == "side" else "global"
        resume_time = cooldown_until.get(key)
        if resume_time is not None and row.entry_date <= resume_time:
            continue
        if len(open_positions) >= max_slots or row.pair in {
            position.pair for position in open_positions
        }:
            continue
        accepted.append(row.Index)
        open_positions.append(row)

    return trades.loc[accepted].sort_values("entry_date")


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

    profiles = [
        CooldownProfile(loss_trigger, cooldown_minutes, scope)
        for loss_trigger, cooldown_minutes, scope in itertools.product(
            (-0.05, -0.10, -0.20, -0.40),
            (30, 60, 120, 240, 360),
            ("global", "side"),
        )
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

    raw_trades = pd.concat(
        [
            raw_trades_for_side(events["long"], 90, args.cost, args.leverage),
            raw_trades_for_side(events["short"], 120, args.cost, args.leverage),
        ],
        ignore_index=True,
    )
    ranked = []
    for profile in profiles:
        trades = execute_with_cooldown(raw_trades, profile, args.max_slots)
        result = metrics(trades, *WINDOWS["development"], args.stake_fraction)
        ranked.append((development_score(result), profile, trades))
    ranked.sort(key=lambda item: item[0], reverse=True)

    print(
        "rank,loss_trigger,cooldown,scope,window,trades,tpd,winrate,return,daily,"
        "pf,max_dd,long,short,stops"
    )
    for rank, (_, profile, trades) in enumerate(ranked[: args.top], 1):
        for window_name, window in WINDOWS.items():
            result = metrics(trades, *window, args.stake_fraction)
            print(
                f"{rank},{profile.loss_trigger:.3f},{profile.cooldown_minutes},"
                f"{profile.scope},{window_name},{result['trades']},{result['tpd']:.3f},"
                f"{result['wr']:.4f},{result['return']:.4f},{result['daily']:.5f},"
                f"{result['pf']:.3f},{result['dd']:.4f},{result['long']},"
                f"{result['short']},{result['stops']}"
            )


if __name__ == "__main__":
    main()
