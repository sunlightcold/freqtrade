"""Path-aware exit research for the high-win-rate Stage31 entry family."""

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
except ModuleNotFoundError:
    from research_stage31_tp_horizon import DEFAULT_PAIRS, WINDOWS, make_signals


@dataclass(frozen=True)
class ExitProfile:
    target: float
    stop: float
    checkpoint: int
    checkpoint_floor: float
    hold: int


@dataclass
class EventPaths:
    pair: str
    side: str
    entry_dates: np.ndarray
    path_dates: np.ndarray
    favorable: np.ndarray
    adverse: np.ndarray
    close_return: np.ndarray


def load_pair(data_dir: Path, pair: str) -> pd.DataFrame:
    path = data_dir / "binance" / "futures" / f"{pair}_USDT_USDT-1m-futures.feather"
    return (
        pd.read_feather(path, columns=["date", "open", "high", "low", "close", "volume"])
        .set_index("date")
        .sort_index()
    )


def build_event_paths(
    dataframe: pd.DataFrame,
    signals: pd.Series,
    pair: str,
    side: str,
    max_hold: int,
) -> EventPaths:
    signal_indices = np.flatnonzero(signals.fillna(False).to_numpy())
    entry_indices = signal_indices + 1
    valid = entry_indices + max_hold <= len(dataframe)
    entry_indices = entry_indices[valid]
    offsets = np.arange(max_hold)
    paths = entry_indices[:, None] + offsets
    entry = dataframe["open"].to_numpy()[entry_indices]
    high = dataframe["high"].to_numpy()[paths]
    low = dataframe["low"].to_numpy()[paths]
    close = dataframe["close"].to_numpy()[paths]
    if side == "long":
        favorable = high / entry[:, None] - 1
        adverse = low / entry[:, None] - 1
        close_return = close / entry[:, None] - 1
    else:
        favorable = entry[:, None] / low - 1
        adverse = entry[:, None] / high - 1
        close_return = entry[:, None] / close - 1
    dates = dataframe.index.to_numpy()
    return EventPaths(
        pair=pair,
        side=side,
        entry_dates=dates[entry_indices],
        path_dates=dates[paths],
        favorable=favorable.astype(np.float32),
        adverse=adverse.astype(np.float32),
        close_return=close_return.astype(np.float32),
    )


def resolve_paths(
    favorable: np.ndarray,
    adverse: np.ndarray,
    close_return: np.ndarray,
    profile: ExitProfile,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    favorable = favorable[:, : profile.hold]
    adverse = adverse[:, : profile.hold]
    close_return = close_return[:, : profile.hold]
    tp_hits = favorable >= profile.target
    stop_hits = adverse <= -profile.stop
    no_hit = profile.hold
    first_tp = np.where(tp_hits.any(axis=1), tp_hits.argmax(axis=1), no_hit)
    first_stop = np.where(stop_hits.any(axis=1), stop_hits.argmax(axis=1), no_hit)
    stop_first = (first_stop <= first_tp) & (first_stop < profile.hold)
    tp_first = (first_tp < first_stop) & (first_tp < profile.hold)
    first_barrier = np.minimum(first_tp, first_stop)

    checkpoint_offset = profile.checkpoint - 1
    checkpoint_return = close_return[:, checkpoint_offset]
    checkpoint_exit = (first_barrier > checkpoint_offset) & (
        checkpoint_return <= profile.checkpoint_floor
    )
    exit_offsets = np.where(
        stop_first,
        first_stop,
        np.where(
            tp_first,
            first_tp,
            np.where(checkpoint_exit, checkpoint_offset, profile.hold - 1),
        ),
    )
    underlying = np.where(
        stop_first,
        -profile.stop,
        np.where(
            tp_first,
            profile.target,
            np.where(
                checkpoint_exit,
                checkpoint_return,
                close_return[:, profile.hold - 1],
            ),
        ),
    )
    reason = np.where(
        stop_first,
        "stop",
        np.where(tp_first, "target", np.where(checkpoint_exit, "checkpoint", "horizon")),
    )
    return exit_offsets.astype(np.int32), underlying, reason


def trades_for_profile(
    events: list[EventPaths],
    profile: ExitProfile,
    cost: float,
    leverage: float,
) -> pd.DataFrame:
    parts = []
    for event in events:
        if not len(event.entry_dates):
            continue
        exit_offsets, underlying, reason = resolve_paths(
            event.favorable,
            event.adverse,
            event.close_return,
            profile,
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
        accepted = np.asarray(accepted, dtype=np.int32)
        parts.append(
            pd.DataFrame(
                {
                    "pair": event.pair,
                    "side": event.side,
                    "entry_date": event.entry_dates[accepted],
                    "exit_date": exit_dates[accepted],
                    "profit": np.maximum(
                        leverage * (underlying[accepted] - 2 * cost),
                        -0.99,
                    ),
                    "reason": reason[accepted],
                }
            )
        )
    return pd.concat(parts, ignore_index=True).sort_values("entry_date")


def execute_portfolio(trades: pd.DataFrame, max_slots: int) -> pd.DataFrame:
    open_positions: list[tuple[pd.Timestamp, str]] = []
    accepted = []
    for row in trades.sort_values(["entry_date", "pair"]).itertuples():
        open_positions = [position for position in open_positions if position[0] >= row.entry_date]
        if len(open_positions) >= max_slots or row.pair in {
            position[1] for position in open_positions
        }:
            continue
        accepted.append(row.Index)
        open_positions.append((row.exit_date, row.pair))
    return trades.loc[accepted].sort_values("entry_date")


def metrics(
    trades: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    stake_fraction: float,
) -> dict[str, float | int]:
    selected = trades[(trades["entry_date"] >= start) & (trades["entry_date"] < end)]
    days = (end - start).days
    if selected.empty:
        return {
            "trades": 0,
            "tpd": 0.0,
            "wr": 0.0,
            "return": 0.0,
            "daily": 0.0,
            "pf": 0.0,
            "dd": 0.0,
            "long": 0,
            "short": 0,
        }
    pnl = selected["profit"] * stake_fraction
    equity = 1 + pnl.cumsum()
    drawdown = equity / equity.cummax() - 1
    gains = pnl[pnl > 0].sum()
    losses = -pnl[pnl < 0].sum()
    total_return = float(pnl.sum())
    return {
        "trades": len(selected),
        "tpd": len(selected) / days,
        "wr": float((pnl > 0).mean()),
        "return": total_return,
        "daily": total_return / days,
        "pf": float(gains / losses) if losses else 99.0,
        "dd": float(-drawdown.min()),
        "long": int((selected["side"] == "long").sum()),
        "short": int((selected["side"] == "short").sum()),
    }


def development_score(result: dict[str, float | int]) -> float:
    pf = float(result["pf"])
    daily = float(result["daily"])
    winrate = float(result["wr"])
    frequency = float(result["tpd"])
    score = (
        min(winrate, 0.80) * 4
        + min(frequency, 10.0) * 0.08
        + min(pf, 2.0) * 1.5
        + max(min(daily, 0.01), -0.01) * 300
    )
    if pf < 1 or daily <= 0:
        score -= 5
    return score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="user_data/data")
    parser.add_argument("--pairs", nargs="+", default=DEFAULT_PAIRS)
    parser.add_argument("--cost", type=float, default=0.0007)
    parser.add_argument("--leverage", type=float, default=5.0)
    parser.add_argument("--stake-fraction", type=float, default=0.09)
    parser.add_argument("--max-slots", type=int, default=10)
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    profiles = [
        ExitProfile(target, stop, checkpoint, floor, hold)
        for target, stop, checkpoint, floor, hold in itertools.product(
            (0.0075, 0.0100),
            (0.0125, 0.0200, 0.0300),
            (10, 20, 30),
            (-0.0050, 0.0, 0.0025),
            (60, 120),
        )
        if checkpoint < hold
    ]
    max_hold = max(profile.hold for profile in profiles)
    data_dir = Path(args.data_dir)
    btc_close = load_pair(data_dir, "BTC")["close"]
    events = []
    for number, pair in enumerate(args.pairs, 1):
        dataframe = load_pair(data_dir, pair)
        for side, shock in (("long", 0.025), ("short", 0.060)):
            signals = make_signals(dataframe, btc_close, 30, shock, 2.0, side)
            event = build_event_paths(dataframe, signals, pair, side, max_hold)
            events.append(event)
            print(
                f"loaded,{number}/{len(args.pairs)},{pair},{side},{len(event.entry_dates)}",
                flush=True,
            )

    development = WINDOWS["development"]
    ranked = []
    for number, profile in enumerate(profiles, 1):
        trades = execute_portfolio(
            trades_for_profile(events, profile, args.cost, args.leverage),
            args.max_slots,
        )
        result = metrics(trades, *development, args.stake_fraction)
        ranked.append((development_score(result), profile, trades, result))
        if number % 20 == 0:
            print(f"searched,{number}/{len(profiles)}", flush=True)
    ranked.sort(key=lambda item: item[0], reverse=True)

    print(
        "rank,target,stop,checkpoint,floor,hold,window,trades,tpd,winrate,return,daily,pf,max_dd,long,short"
    )
    for rank, (_, profile, trades, _) in enumerate(ranked[: args.top], 1):
        for window_name, window in WINDOWS.items():
            result = metrics(trades, *window, args.stake_fraction)
            print(
                f"{rank},{profile.target:.4f},{profile.stop:.4f},{profile.checkpoint},"
                f"{profile.checkpoint_floor:.4f},{profile.hold},{window_name},"
                f"{result['trades']},{result['tpd']:.3f},{result['wr']:.4f},"
                f"{result['return']:.4f},{result['daily']:.5f},{result['pf']:.3f},"
                f"{result['dd']:.4f},{result['long']},{result['short']}"
            )


if __name__ == "__main__":
    main()
