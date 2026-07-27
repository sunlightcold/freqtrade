"""Quarterly walk-forward classifier with a realistic fixed-stake portfolio."""

from __future__ import annotations

import argparse
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
from research_stage31_tp_horizon import DEFAULT_PAIRS
from research_stage33_cross_sectional import load_pair
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor


FEATURES = [
    "signed_ret_1",
    "signed_ret_4",
    "signed_ret_16",
    "signed_ret_96",
    "signed_ema_16",
    "signed_ema_96",
    "vol_16",
    "vol_96",
    "range_pct",
    "close_pos",
    "volume_z",
    "signed_cs_4",
    "signed_cs_16",
    "signed_cs_96",
    "signed_btc_16",
    "signed_btc_96",
    "side",
]


def future_outcomes(
    dataframe: pd.DataFrame,
    sample_indices: np.ndarray,
    side: int,
    hold: int,
    target: float,
    stop: float,
    cost: float,
    leverage: float,
) -> pd.DataFrame:
    entry_indices = sample_indices + 1
    valid = entry_indices + hold < len(dataframe)
    sample_indices = sample_indices[valid]
    entry_indices = entry_indices[valid]
    entry = dataframe["close"].to_numpy()[entry_indices]
    offsets = np.arange(1, hold + 1)
    paths = entry_indices[:, None] + offsets
    high = dataframe["high"].to_numpy()[paths]
    low = dataframe["low"].to_numpy()[paths]
    if side == 1:
        tp_hits = high >= entry[:, None] * (1 + target)
        sl_hits = low <= entry[:, None] * (1 - stop)
    else:
        tp_hits = low <= entry[:, None] * (1 - target)
        sl_hits = high >= entry[:, None] * (1 + stop)
    no_hit = hold + 1
    first_tp = np.where(tp_hits.any(axis=1), tp_hits.argmax(axis=1) + 1, no_hit)
    first_sl = np.where(sl_hits.any(axis=1), sl_hits.argmax(axis=1) + 1, no_hit)
    sl_first = (first_sl <= first_tp) & (first_sl <= hold)
    tp_first = (first_tp < first_sl) & (first_tp <= hold)
    exit_offsets = np.where(sl_first, first_sl, np.where(tp_first, first_tp, hold))
    exit_indices = entry_indices + exit_offsets
    close = dataframe["close"].to_numpy()
    timeout_return = close[exit_indices] / entry - 1
    if side == -1:
        timeout_return = entry / close[exit_indices] - 1
    underlying = np.where(sl_first, -stop, np.where(tp_first, target, timeout_return))
    net_profit = leverage * (underlying - 2 * cost)
    dates = dataframe.index.to_numpy()
    return pd.DataFrame(
        {
            "row_index": sample_indices,
            "entry_date": dates[entry_indices],
            "exit_date": dates[exit_indices],
            "profit": np.maximum(net_profit, -0.99),
        }
    )


def zscore(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sub(frame.mean(axis=1), axis=0).div(frame.std(axis=1).replace(0, np.nan), axis=0)


def build_dataset(pair_data: dict[str, pd.DataFrame], args: argparse.Namespace) -> pd.DataFrame:
    pairs = list(pair_data)
    common_index = pair_data[pairs[0]].index
    for dataframe in pair_data.values():
        common_index = common_index.intersection(dataframe.index)
    pair_data = {pair: dataframe.reindex(common_index) for pair, dataframe in pair_data.items()}
    closes = pd.DataFrame({pair: dataframe["close"] for pair, dataframe in pair_data.items()})
    returns = {period: closes / closes.shift(period) - 1 for period in (1, 4, 16, 96)}
    cross_section = {period: zscore(returns[period]) for period in (4, 16, 96)}
    btc = (
        closes["BTC"]
        if "BTC" in closes
        else load_pair(Path(args.data_dir), "BTC")["close"].reindex(common_index)
    )
    btc_returns = {period: btc / btc.shift(period) - 1 for period in (16, 96)}
    sample_indices = np.arange(96, len(common_index) - args.hold - 1, args.sample_every)
    all_rows = []

    for pair, dataframe in pair_data.items():
        close = dataframe["close"]
        one_bar = close.pct_change()
        ema_16 = close.ewm(span=16, adjust=False).mean()
        ema_96 = close.ewm(span=96, adjust=False).mean()
        volume_mean = dataframe["volume"].rolling(96).mean()
        volume_std = dataframe["volume"].rolling(96).std().replace(0, np.nan)
        base = pd.DataFrame(index=common_index)
        base["ret_1"] = returns[1][pair]
        base["ret_4"] = returns[4][pair]
        base["ret_16"] = returns[16][pair]
        base["ret_96"] = returns[96][pair]
        base["ema_16"] = close / ema_16 - 1
        base["ema_96"] = close / ema_96 - 1
        base["vol_16"] = one_bar.rolling(16).std()
        base["vol_96"] = one_bar.rolling(96).std()
        base["range_pct"] = (dataframe["high"] - dataframe["low"]) / close
        base["close_pos"] = (close - dataframe["low"]) / (
            dataframe["high"] - dataframe["low"]
        ).replace(0, np.nan)
        base["volume_z"] = (dataframe["volume"] - volume_mean) / volume_std
        base["cs_4"] = cross_section[4][pair]
        base["cs_16"] = cross_section[16][pair]
        base["cs_96"] = cross_section[96][pair]
        base["btc_16"] = btc_returns[16]
        base["btc_96"] = btc_returns[96]

        for side in (1, -1):
            outcomes = future_outcomes(
                dataframe,
                sample_indices,
                side,
                args.hold,
                args.target,
                args.stop,
                args.cost,
                args.leverage,
            )
            rows = base.iloc[outcomes["row_index"].to_numpy()].reset_index(names="signal_date")
            for name in (
                "ret_1",
                "ret_4",
                "ret_16",
                "ret_96",
                "ema_16",
                "ema_96",
                "cs_4",
                "cs_16",
                "cs_96",
                "btc_16",
                "btc_96",
            ):
                rows[f"signed_{name}"] = rows.pop(name) * side
            rows["side"] = side
            rows["pair"] = pair
            rows["entry_date"] = outcomes["entry_date"].to_numpy()
            rows["exit_date"] = outcomes["exit_date"].to_numpy()
            rows["profit"] = outcomes["profit"].to_numpy()
            rows["winner"] = (rows["profit"] > 0).astype(int)
            all_rows.append(
                rows[
                    [
                        "signal_date",
                        "entry_date",
                        "exit_date",
                        "pair",
                        "profit",
                        "winner",
                        *FEATURES,
                    ]
                ]
            )
    return pd.concat(all_rows, ignore_index=True).dropna().sort_values("signal_date")


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
            learning_rate=0.06,
            max_iter=100,
            max_leaf_nodes=15,
            min_samples_leaf=120,
            l2_regularization=8.0,
            random_state=42,
        )
        model.fit(train[FEATURES], train["winner"])
        test["probability"] = model.predict_proba(test[FEATURES])[:, 1]
        profit_model = HistGradientBoostingRegressor(
            loss="squared_error",
            learning_rate=0.05,
            max_iter=120,
            max_leaf_nodes=15,
            min_samples_leaf=120,
            l2_regularization=12.0,
            random_state=43,
        )
        profit_model.fit(train[FEATURES], train["profit"])
        test["expected_profit"] = profit_model.predict(test[FEATURES])
        predictions.append(test)
        print(f"trained,{start.date()},{len(train)},{len(test)}")
    return pd.concat(predictions, ignore_index=True).sort_values("entry_date")


def execute_portfolio(
    candidates: pd.DataFrame,
    probability_floor: float,
    edge_floor: float,
    max_slots: int,
) -> pd.DataFrame:
    selected = candidates[
        (candidates["probability"] >= probability_floor)
        & (candidates["expected_profit"] >= edge_floor)
    ].copy()
    selected = selected.sort_values(
        ["entry_date", "expected_profit", "probability"],
        ascending=[True, False, False],
    )
    open_positions: list[tuple[pd.Timestamp, str]] = []
    accepted = []
    for row in selected.itertuples():
        open_positions = [position for position in open_positions if position[0] > row.entry_date]
        open_pairs = {position[1] for position in open_positions}
        if len(open_positions) >= max_slots or row.pair in open_pairs:
            continue
        accepted.append(row.Index)
        open_positions.append((row.exit_date, row.pair))
    return selected.loc[accepted].sort_values("exit_date")


def score(
    trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, stake_fraction: float
) -> dict:
    selected = trades[(trades["entry_date"] >= start) & (trades["entry_date"] < end)].copy()
    if selected.empty:
        return {
            "trades": 0,
            "tpd": 0.0,
            "winrate": 0.0,
            "return": 0.0,
            "daily": 0.0,
            "pf": 0.0,
            "long": 0,
            "short": 0,
            "dd": 0.0,
        }
    pnl = selected["profit"] * stake_fraction
    equity = 1 + pnl.cumsum()
    drawdown = equity / equity.cummax() - 1
    gains = pnl[pnl > 0].sum()
    losses = -pnl[pnl < 0].sum()
    days = (end - start).days
    total_return = float(pnl.sum())
    return {
        "trades": len(selected),
        "tpd": len(selected) / days,
        "winrate": float((pnl > 0).mean()),
        "return": total_return,
        "daily": total_return / days,
        "pf": float(gains / losses) if losses else 99.0,
        "long": int((selected["side"] == 1).sum()),
        "short": int((selected["side"] == -1).sum()),
        "dd": float(-drawdown.min()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="user_data/data")
    parser.add_argument("--pairs", nargs="+", default=DEFAULT_PAIRS)
    parser.add_argument("--sample-every", type=int, default=16)
    parser.add_argument("--hold", type=int, default=96)
    parser.add_argument("--target", type=float, default=0.012)
    parser.add_argument("--stop", type=float, default=0.030)
    parser.add_argument("--cost", type=float, default=0.0007)
    parser.add_argument("--leverage", type=float, default=5.0)
    parser.add_argument("--stake-fraction", type=float, default=0.09)
    parser.add_argument("--max-slots", type=int, default=10)
    args = parser.parse_args()

    pair_data = {pair: load_pair(Path(args.data_dir), pair) for pair in args.pairs}
    dataset = build_dataset(pair_data, args)
    predictions = walk_forward_predictions(dataset)
    development = (pd.Timestamp("2024-07-01", tz="UTC"), pd.Timestamp("2025-07-01", tz="UTC"))
    sample_out = (pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2026-07-01", tz="UTC"))
    print("probability,edge_floor,window,trades,tpd,winrate,return,daily,pf,long,short,max_dd")
    for probability_floor in (0.65, 0.70, 0.75):
        for edge_floor in (-0.02, -0.01, 0.0, 0.01, 0.02, 0.03):
            trades = execute_portfolio(predictions, probability_floor, edge_floor, args.max_slots)
            for name, window in (("development", development), ("sample_out", sample_out)):
                result = score(trades, *window, args.stake_fraction)
                print(
                    f"{probability_floor:.2f},{edge_floor:.3f},{name},{result['trades']},"
                    f"{result['tpd']:.3f},{result['winrate']:.4f},{result['return']:.4f},"
                    f"{result['daily']:.5f},{result['pf']:.3f},{result['long']},"
                    f"{result['short']},{result['dd']:.4f}"
                )


if __name__ == "__main__":
    main()
