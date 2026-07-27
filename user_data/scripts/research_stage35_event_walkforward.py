"""Walk-forward event model for volatility-normalized relative reversals.

This is a research-only screen. Parameters are selected on the development
window and reported unchanged on the untouched sample-out window.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier


try:
    from user_data.scripts.research_stage31_tp_horizon import DEFAULT_PAIRS
except ModuleNotFoundError:
    from research_stage31_tp_horizon import DEFAULT_PAIRS


DEVELOPMENT = (pd.Timestamp("2024-07-01", tz="UTC"), pd.Timestamp("2025-07-01", tz="UTC"))
SAMPLE_OUT = (pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2026-07-01", tz="UTC"))

FEATURES = [
    "shock_z",
    "signed_ret_1",
    "signed_ret_3",
    "signed_ret_12",
    "signed_rel_3",
    "signed_rel_12",
    "signed_rel_48",
    "signed_ema_24",
    "signed_ema_96",
    "signed_btc_3",
    "signed_btc_12",
    "atr_pct",
    "volume_ratio",
    "range_pct",
    "rejection_wick",
    "close_position",
    "hour_sin",
    "hour_cos",
    "side",
]


@dataclass(frozen=True)
class ExitProfile:
    target: float
    stop: float
    hold: int

    @property
    def name(self) -> str:
        return f"tp{self.target:.4f}_sl{self.stop:.4f}_h{self.hold}"


PROFILES = (
    ExitProfile(0.006, 0.006, 12),
    ExitProfile(0.008, 0.008, 12),
    ExitProfile(0.010, 0.010, 18),
    ExitProfile(0.008, 0.012, 18),
)


def load_pair(data_dir: Path, pair: str) -> pd.DataFrame:
    path = data_dir / "binance" / "futures" / f"{pair}_USDT_USDT-1m-futures.feather"
    dataframe = pd.read_feather(path, columns=["date", "open", "high", "low", "close", "volume"])
    dataframe = dataframe.set_index("date").sort_index()
    return (
        dataframe.resample("5min", label="left", closed="left")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
    )


def future_outcomes(
    dataframe: pd.DataFrame,
    signal_indices: np.ndarray,
    side: int,
    profile: ExitProfile,
    cost: float,
    leverage: float,
) -> pd.DataFrame:
    """Enter at the next bar open and conservatively resolve intrabar ties."""
    entry_indices = signal_indices + 1
    valid = entry_indices + profile.hold <= len(dataframe)
    signal_indices = signal_indices[valid]
    entry_indices = entry_indices[valid]
    if not len(entry_indices):
        return pd.DataFrame(columns=["row_index", "entry_date", "exit_date", "profit"])

    entry = dataframe["open"].to_numpy()[entry_indices]
    offsets = np.arange(profile.hold)
    paths = entry_indices[:, None] + offsets
    high = dataframe["high"].to_numpy()[paths]
    low = dataframe["low"].to_numpy()[paths]
    if side == 1:
        tp_hits = high >= entry[:, None] * (1 + profile.target)
        stop_hits = low <= entry[:, None] * (1 - profile.stop)
    else:
        tp_hits = low <= entry[:, None] * (1 - profile.target)
        stop_hits = high >= entry[:, None] * (1 + profile.stop)

    no_hit = profile.hold
    first_tp = np.where(tp_hits.any(axis=1), tp_hits.argmax(axis=1), no_hit)
    first_stop = np.where(stop_hits.any(axis=1), stop_hits.argmax(axis=1), no_hit)
    stop_first = (first_stop <= first_tp) & (first_stop < profile.hold)
    tp_first = (first_tp < first_stop) & (first_tp < profile.hold)
    exit_offsets = np.where(stop_first, first_stop, np.where(tp_first, first_tp, profile.hold - 1))
    exit_indices = entry_indices + exit_offsets

    close = dataframe["close"].to_numpy()
    timeout = close[exit_indices] / entry - 1
    if side == -1:
        timeout = entry / close[exit_indices] - 1
    underlying = np.where(
        stop_first,
        -profile.stop,
        np.where(tp_first, profile.target, timeout),
    )
    profit = np.maximum(leverage * (underlying - 2 * cost), -0.99)
    dates = dataframe.index.to_numpy()
    return pd.DataFrame(
        {
            "row_index": signal_indices,
            "entry_date": dates[entry_indices],
            "exit_date": dates[exit_indices],
            "profit": profit,
        }
    )


def make_pair_candidates(
    dataframe: pd.DataFrame,
    btc: pd.DataFrame,
    pair: str,
    profile: ExitProfile,
    args: argparse.Namespace,
) -> pd.DataFrame:
    btc_close = btc["close"].reindex(dataframe.index).ffill()
    close = dataframe["close"]
    returns = {period: close.pct_change(period) for period in (1, 3, 12, 48)}
    btc_returns = {period: btc_close.pct_change(period) for period in (3, 12, 48)}
    relative = {period: returns[period] - btc_returns[period] for period in (3, 12, 48)}
    relative_scale = relative[3].rolling(args.z_window, min_periods=args.z_window).std()
    relative_z = relative[3] / relative_scale.replace(0, np.nan)

    ema_24 = close.ewm(span=24, adjust=False, min_periods=24).mean()
    ema_96 = close.ewm(span=96, adjust=False, min_periods=96).mean()
    previous_close = close.shift()
    true_range = pd.concat(
        [
            dataframe["high"] - dataframe["low"],
            (dataframe["high"] - previous_close).abs(),
            (dataframe["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_pct = true_range.ewm(alpha=1 / 24, adjust=False, min_periods=24).mean() / close
    volume_median = dataframe["volume"].rolling(288, min_periods=288).median()
    volume_ratio = dataframe["volume"] / volume_median.replace(0, np.nan)
    candle_range = (dataframe["high"] - dataframe["low"]).replace(0, np.nan)
    raw_close_position = (close - dataframe["low"]) / candle_range
    lower_wick = dataframe[["open", "close"]].min(axis=1) - dataframe["low"]
    upper_wick = dataframe["high"] - dataframe[["open", "close"]].max(axis=1)
    hour = dataframe.index.hour + dataframe.index.minute / 60

    base = pd.DataFrame(index=dataframe.index)
    base["atr_pct"] = atr_pct
    base["volume_ratio"] = volume_ratio
    base["range_pct"] = candle_range / close
    base["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    base["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    all_rows = []
    for side in (1, -1):
        if args.mode == "reversion":
            shock_z = -side * relative_z
            event = (shock_z.shift(1) >= args.event_z) & (shock_z < shock_z.shift(1))
        else:
            shock_z = side * relative_z
            event = (shock_z >= args.event_z) & (shock_z.shift(1) < args.event_z)
        directional_return = side * returns[1]
        close_position = raw_close_position if side == 1 else 1 - raw_close_position
        rejection_wick = (lower_wick if side == 1 else upper_wick) / candle_range
        signals = (
            event
            & (directional_return > 0)
            & (close_position >= args.close_position)
            & (volume_ratio >= args.volume_floor)
            & (dataframe["volume"] > 0)
        ).fillna(False)
        signal_indices = np.flatnonzero(signals.to_numpy())
        outcomes = future_outcomes(
            dataframe,
            signal_indices,
            side,
            profile,
            args.cost,
            args.leverage,
        )
        if outcomes.empty:
            continue
        rows = base.iloc[outcomes["row_index"].to_numpy()].copy().reset_index(names="signal_date")
        row_indices = outcomes["row_index"].to_numpy()
        rows["shock_z"] = shock_z.iloc[row_indices].to_numpy()
        rows["signed_ret_1"] = side * returns[1].iloc[row_indices].to_numpy()
        rows["signed_ret_3"] = side * returns[3].iloc[row_indices].to_numpy()
        rows["signed_ret_12"] = side * returns[12].iloc[row_indices].to_numpy()
        rows["signed_rel_3"] = side * relative[3].iloc[row_indices].to_numpy()
        rows["signed_rel_12"] = side * relative[12].iloc[row_indices].to_numpy()
        rows["signed_rel_48"] = side * relative[48].iloc[row_indices].to_numpy()
        rows["signed_ema_24"] = side * (close / ema_24 - 1).iloc[row_indices].to_numpy()
        rows["signed_ema_96"] = side * (close / ema_96 - 1).iloc[row_indices].to_numpy()
        rows["signed_btc_3"] = side * btc_returns[3].iloc[row_indices].to_numpy()
        rows["signed_btc_12"] = side * btc_returns[12].iloc[row_indices].to_numpy()
        rows["rejection_wick"] = rejection_wick.iloc[row_indices].to_numpy()
        rows["close_position"] = close_position.iloc[row_indices].to_numpy()
        rows["side"] = side
        rows["pair"] = pair
        rows["entry_date"] = outcomes["entry_date"].to_numpy()
        rows["exit_date"] = outcomes["exit_date"].to_numpy()
        rows["profit"] = outcomes["profit"].to_numpy()
        rows["winner"] = (rows["profit"] > 0).astype(np.int8)
        all_rows.append(
            rows[["signal_date", "entry_date", "exit_date", "pair", "profit", "winner", *FEATURES]]
        )
    if not all_rows:
        return pd.DataFrame()
    return pd.concat(all_rows, ignore_index=True).dropna()


def build_dataset(
    data_dir: Path,
    pairs: list[str],
    profile: ExitProfile,
    args: argparse.Namespace,
) -> pd.DataFrame:
    btc = load_pair(data_dir, "BTC")
    parts = []
    for number, pair in enumerate(pairs, 1):
        dataframe = load_pair(data_dir, pair)
        rows = make_pair_candidates(dataframe, btc, pair, profile, args)
        if not rows.empty:
            parts.append(rows)
        print(f"loaded,{profile.name},{number}/{len(pairs)},{pair},{len(rows)}", flush=True)
    return pd.concat(parts, ignore_index=True).sort_values("signal_date")


def walk_forward_predictions(dataset: pd.DataFrame) -> pd.DataFrame:
    periods = pd.date_range("2024-07-01", "2026-07-01", freq="QS-JAN", tz="UTC")
    predictions = []
    for start, end in pairwise(periods):
        train_start = start - pd.Timedelta(days=365)
        train_end = start - pd.Timedelta(days=2)
        train = dataset[
            (dataset["signal_date"] >= train_start) & (dataset["exit_date"] < train_end)
        ]
        test = dataset[(dataset["signal_date"] >= start) & (dataset["signal_date"] < end)].copy()
        if train.empty or test.empty:
            continue
        model = HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_iter=140,
            max_leaf_nodes=15,
            min_samples_leaf=100,
            l2_regularization=12.0,
            random_state=35,
        )
        model.fit(train[FEATURES], train["winner"])
        test["probability"] = model.predict_proba(test[FEATURES])[:, 1]
        predictions.append(test)
        print(f"trained,{start.date()},{len(train)},{len(test)}", flush=True)
    return pd.concat(predictions, ignore_index=True).sort_values("entry_date")


def execute_portfolio(candidates: pd.DataFrame, floor: float, max_slots: int) -> pd.DataFrame:
    selected = candidates[candidates["probability"] >= floor].sort_values(
        ["entry_date", "probability"], ascending=[True, False]
    )
    open_positions: list[tuple[pd.Timestamp, str]] = []
    accepted = []
    for row in selected.itertuples():
        open_positions = [position for position in open_positions if position[0] >= row.entry_date]
        if len(open_positions) >= max_slots or row.pair in {
            position[1] for position in open_positions
        }:
            continue
        accepted.append(row.Index)
        open_positions.append((row.exit_date, row.pair))
    return selected.loc[accepted].sort_values("entry_date")


def score(
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
        "long": int((selected["side"] == 1).sum()),
        "short": int((selected["side"] == -1).sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="user_data/data")
    parser.add_argument("--pairs", nargs="+", default=DEFAULT_PAIRS)
    parser.add_argument("--cost", type=float, default=0.0007)
    parser.add_argument("--leverage", type=float, default=5.0)
    parser.add_argument("--stake-fraction", type=float, default=0.09)
    parser.add_argument("--max-slots", type=int, default=10)
    parser.add_argument("--mode", choices=("reversion", "momentum"), default="reversion")
    parser.add_argument("--event-z", type=float, default=1.5)
    parser.add_argument("--z-window", type=int, default=2016)
    parser.add_argument("--close-position", type=float, default=0.55)
    parser.add_argument("--volume-floor", type=float, default=0.50)
    parser.add_argument("--profiles", nargs="+", default=[profile.name for profile in PROFILES])
    args = parser.parse_args()

    profiles = [profile for profile in PROFILES if profile.name in args.profiles]
    if len(profiles) != len(args.profiles):
        raise SystemExit(f"Unknown profile. Available: {[profile.name for profile in PROFILES]}")
    print("profile,floor,window,trades,tpd,winrate,return,daily,pf,max_dd,long,short")
    for profile in profiles:
        dataset = build_dataset(Path(args.data_dir), args.pairs, profile, args)
        predictions = walk_forward_predictions(dataset)
        for floor in np.arange(0.50, 0.801, 0.025):
            trades = execute_portfolio(predictions, float(floor), args.max_slots)
            for window_name, window in (("development", DEVELOPMENT), ("sample_out", SAMPLE_OUT)):
                result = score(trades, *window, args.stake_fraction)
                print(
                    f"{profile.name},{floor:.3f},{window_name},{result['trades']},"
                    f"{result['tpd']:.3f},{result['wr']:.4f},{result['return']:.4f},"
                    f"{result['daily']:.5f},{result['pf']:.3f},{result['dd']:.4f},"
                    f"{result['long']},{result['short']}"
                )


if __name__ == "__main__":
    main()
