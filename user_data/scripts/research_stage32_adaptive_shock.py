"""Walk-forward adaptive filter for relative-shock entries.

Every quality observation is delayed until its complete exit horizon is known,
so the gate at a signal candle only contains information available at that time.
"""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import pandas as pd
from research_stage31_tp_horizon import (
    DEFAULT_PAIRS,
    WINDOWS,
    apply_target,
    load_pair,
    make_signals,
    metrics,
    screen_trade_inputs,
)


def adaptive_filter_inputs(
    inputs: pd.DataFrame,
    target: float,
    cost: float,
    hold: int,
    span: int,
    min_events: int,
    win_floor: float,
    edge_floor: float,
) -> pd.DataFrame:
    if inputs.empty:
        return inputs
    target_hit = inputs["favorable_return"].to_numpy() >= target
    timeout = inputs["timeout_return"].to_numpy()
    outcomes = pd.Series(timeout).where(~target_hit, target).to_numpy() - 2 * cost
    dates = pd.DatetimeIndex(pd.to_datetime(inputs["date"], utc=True)).asi8
    resolved_dates = dates + pd.Timedelta(minutes=hold).value
    alpha = 2.0 / (span + 1.0)
    selected = []
    resolved_index = 0
    observations = 0
    win_estimate = 0.5
    edge_estimate = 0.0

    for current_index, current_date in enumerate(dates):
        while resolved_index < current_index and resolved_dates[resolved_index] <= current_date:
            outcome = outcomes[resolved_index]
            win = 1.0 if outcome > 0 else 0.0
            if observations == 0:
                win_estimate = win
                edge_estimate = outcome
            else:
                win_estimate = alpha * win + (1 - alpha) * win_estimate
                edge_estimate = alpha * outcome + (1 - alpha) * edge_estimate
            observations += 1
            resolved_index += 1
        selected.append(
            observations >= min_events and win_estimate >= win_floor and edge_estimate >= edge_floor
        )
    return inputs[pd.Series(selected, index=inputs.index)]


def side_metrics(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[int, int]:
    if trades.empty:
        return 0, 0
    dates = pd.to_datetime(trades["date"], utc=True)
    selected = trades[(dates >= start) & (dates < end)]
    return int((selected["side"] == "long").sum()), int((selected["side"] == "short").sum())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="user_data/data")
    parser.add_argument("--pairs", nargs="+", default=DEFAULT_PAIRS)
    parser.add_argument("--cost", type=float, default=0.0007)
    parser.add_argument("--leverage", type=float, default=3.0)
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    btc = load_pair(data_dir, "BTC")["close"]
    targets = [0.0100, 0.0150]
    holds = [120]
    spans = [20, 50]
    min_events_values = [5, 10]
    win_floors = [0.65, 0.70]
    edge_floors = [0.0, 0.0010]
    buckets: dict[tuple, list[pd.DataFrame]] = {}

    for target, hold, span, min_events, win_floor, edge_floor in itertools.product(
        targets, holds, spans, min_events_values, win_floors, edge_floors
    ):
        buckets[(target, hold, span, min_events, win_floor, edge_floor)] = []

    for pair in args.pairs:
        dataframe = load_pair(data_dir, pair)
        for side, shock in (("long", 0.025), ("short", 0.060)):
            base_signal = make_signals(dataframe, btc, 30, shock, 2.0, side)
            for target, hold in itertools.product(targets, holds):
                inputs = screen_trade_inputs(dataframe, base_signal, side, hold)
                for span, min_events, win_floor, edge_floor in itertools.product(
                    spans, min_events_values, win_floors, edge_floors
                ):
                    gated_inputs = adaptive_filter_inputs(
                        inputs,
                        target,
                        args.cost,
                        hold,
                        span,
                        min_events,
                        win_floor,
                        edge_floor,
                    )
                    trades = apply_target(gated_inputs, target, args.cost, args.leverage)
                    trades["pair"] = pair
                    buckets[(target, hold, span, min_events, win_floor, edge_floor)].append(trades)

    results = []
    for params, parts in buckets.items():
        combined = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        scores = {name: metrics(combined, *window) for name, window in WINDOWS.items()}
        sides = {name: side_metrics(combined, *window) for name, window in WINDOWS.items()}
        dev = scores["development"]
        dev_gate = (
            dev["winrate"] >= 0.70
            and dev["tpd"] >= 2
            and (dev["return"] >= 1.0 or dev["daily"] >= 0.005)
        )
        score = (
            min(dev["winrate"], 0.85) * 4
            + min(dev["daily"], 0.01) * 250
            + min(dev["tpd"], 6) * 0.06
            + min(dev["pf"], 3) * 0.2
            - (0 if dev_gate else 5)
        )
        results.append((score, params, scores, sides))

    results.sort(key=lambda item: item[0], reverse=True)
    print(
        "rank,target,hold,span,min_events,win_floor,edge_floor,window,trades,tpd,winrate,return,daily,pf,long,short"
    )
    for rank, (_, params, scores, sides) in enumerate(results[: args.top], 1):
        target, hold, span, min_events, win_floor, edge_floor = params
        for window, result in scores.items():
            long_count, short_count = sides[window]
            print(
                f"{rank},{target:.4f},{hold},{span},{min_events},{win_floor:.2f},"
                f"{edge_floor:.4f},{window},{result['trades']},{result['tpd']:.3f},"
                f"{result['winrate']:.4f},{result['return']:.4f},{result['daily']:.5f},"
                f"{result['pf']:.3f},{long_count},{short_count}"
            )


if __name__ == "__main__":
    main()
