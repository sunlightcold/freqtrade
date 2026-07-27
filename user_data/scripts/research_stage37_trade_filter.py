"""Leakage-free event filter for native Stage31 backtest trades."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor


FEATURES = [
    "shock",
    "signed_ret_1",
    "signed_ret_5",
    "signed_ret_15",
    "signed_ret_30",
    "signed_ret_60",
    "signed_ret_240",
    "signed_btc_5",
    "signed_btc_30",
    "signed_btc_240",
    "volume_ratio",
    "atr_pct",
    "range_pct",
    "signed_body",
    "close_position",
    "rejection_wick",
    "signed_ema_24",
    "signed_ema_240",
    "signed_rsi",
    "hour_sin",
    "hour_cos",
    "side",
]


def load_trades(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        result_name = next(
            name
            for name in archive.namelist()
            if name.endswith(".json") and not name.endswith("_config.json")
        )
        payload = json.loads(archive.read(result_name))
    result = next(iter(payload["strategy"].values()))
    trades = pd.DataFrame(result["trades"])
    trades["entry_date"] = pd.to_datetime(trades["open_date"], utc=True)
    trades["exit_date"] = pd.to_datetime(trades["close_date"], utc=True)
    trades["signal_date"] = trades["entry_date"] - pd.Timedelta(minutes=1)
    trades["side"] = np.where(trades["is_short"], -1, 1)
    trades["winner"] = (trades["profit_abs"] > 0).astype(np.int8)
    trades["tail_loss"] = (trades["profit_ratio"] <= -0.10).astype(np.int8)
    trades["base"] = trades["pair"].str.split("/").str[0]
    return trades


def load_pair(data_dir: Path, pair: str) -> pd.DataFrame:
    path = data_dir / "binance" / "futures" / f"{pair}_USDT_USDT-1m-futures.feather"
    return (
        pd.read_feather(path, columns=["date", "open", "high", "low", "close", "volume"])
        .set_index("date")
        .sort_index()
    )


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    relative_strength = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + relative_strength)


def pair_features(dataframe: pd.DataFrame, btc_close: pd.Series) -> pd.DataFrame:
    close = dataframe["close"]
    aligned_btc = btc_close.reindex(dataframe.index)
    pair_returns = {period: close.pct_change(period) for period in (1, 5, 15, 30, 60, 240)}
    btc_returns = {period: aligned_btc.pct_change(period) for period in (5, 30, 240)}
    relative_30 = pair_returns[30] - btc_returns[30]
    previous_close = close.shift()
    true_range = pd.concat(
        [
            dataframe["high"] - dataframe["low"],
            (dataframe["high"] - previous_close).abs(),
            (dataframe["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    candle_range = (dataframe["high"] - dataframe["low"]).replace(0, np.nan)
    raw_close_position = (close - dataframe["low"]) / candle_range
    ema_24 = close.ewm(span=24, adjust=False).mean()
    ema_240 = close.ewm(span=240, adjust=False).mean()
    hour = dataframe.index.hour + dataframe.index.minute / 60
    result = pd.DataFrame(index=dataframe.index)
    result["relative_30"] = relative_30
    for period, values in pair_returns.items():
        result[f"ret_{period}"] = values
    for period, values in btc_returns.items():
        result[f"btc_{period}"] = values
    result["volume_ratio"] = dataframe["volume"] / dataframe["volume"].rolling(240).median()
    result["atr_pct"] = true_range.ewm(alpha=1 / 24, adjust=False).mean() / close
    result["range_pct"] = candle_range / close
    result["body"] = (close - dataframe["open"]) / close
    result["raw_close_position"] = raw_close_position
    result["lower_wick"] = (
        dataframe[["open", "close"]].min(axis=1) - dataframe["low"]
    ) / candle_range
    result["upper_wick"] = (
        dataframe["high"] - dataframe[["open", "close"]].max(axis=1)
    ) / candle_range
    result["ema_24"] = close / ema_24 - 1
    result["ema_240"] = close / ema_240 - 1
    result["rsi"] = (rsi(close) - 50) / 50
    result["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    result["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    return result


def attach_features(trades: pd.DataFrame, data_dir: Path) -> pd.DataFrame:
    btc_close = load_pair(data_dir, "BTC")["close"]
    parts = []
    for pair, pair_trades in trades.groupby("base", sort=False):
        features = pair_features(load_pair(data_dir, pair), btc_close)
        selected = features.reindex(pair_trades["signal_date"])
        selected.index = pair_trades.index
        rows = pair_trades.copy()
        side = rows["side"]
        rows["shock"] = -side * selected["relative_30"]
        for period in (1, 5, 15, 30, 60, 240):
            rows[f"signed_ret_{period}"] = side * selected[f"ret_{period}"]
        for period in (5, 30, 240):
            rows[f"signed_btc_{period}"] = side * selected[f"btc_{period}"]
        rows["volume_ratio"] = selected["volume_ratio"]
        rows["atr_pct"] = selected["atr_pct"]
        rows["range_pct"] = selected["range_pct"]
        rows["signed_body"] = side * selected["body"]
        rows["close_position"] = np.where(
            side == 1,
            selected["raw_close_position"],
            1 - selected["raw_close_position"],
        )
        rows["rejection_wick"] = np.where(
            side == 1,
            selected["lower_wick"],
            selected["upper_wick"],
        )
        rows["signed_ema_24"] = side * selected["ema_24"]
        rows["signed_ema_240"] = side * selected["ema_240"]
        rows["signed_rsi"] = side * selected["rsi"]
        rows["hour_sin"] = selected["hour_sin"]
        rows["hour_cos"] = selected["hour_cos"]
        parts.append(rows)
    return pd.concat(parts).dropna(subset=FEATURES).sort_values("entry_date")


def fit_models(train: pd.DataFrame) -> tuple:
    common = {
        "learning_rate": 0.04,
        "max_iter": 120,
        "max_leaf_nodes": 7,
        "min_samples_leaf": 40,
        "l2_regularization": 20.0,
    }
    winner = HistGradientBoostingClassifier(**common, random_state=37)
    profit = HistGradientBoostingRegressor(**common, loss="absolute_error", random_state=38)
    tail = HistGradientBoostingClassifier(**common, random_state=39)
    winner.fit(train[FEATURES], train["winner"])
    profit.fit(train[FEATURES], train["profit_ratio"])
    tail.fit(train[FEATURES], train["tail_loss"])
    return winner, profit, tail


def predict_score(models: tuple, dataframe: pd.DataFrame) -> np.ndarray:
    winner, profit, tail = models
    win_probability = winner.predict_proba(dataframe[FEATURES])[:, 1]
    expected_profit = profit.predict(dataframe[FEATURES])
    tail_probability = tail.predict_proba(dataframe[FEATURES])[:, 1]
    return expected_profit + 0.04 * (win_probability - 0.5) - 0.20 * tail_probability


def metrics(dataframe: pd.DataFrame, days: int) -> dict[str, float | int]:
    if dataframe.empty:
        return {
            "trades": 0,
            "tpd": 0.0,
            "wr": 0.0,
            "return": 0.0,
            "pf": 0.0,
            "dd": 0.0,
            "long": 0,
            "short": 0,
            "tails": 0,
        }
    ordered = dataframe.sort_values("exit_date")
    pnl = ordered["profit_abs"]
    equity = 1000 + pnl.cumsum()
    drawdown = equity / equity.cummax() - 1
    gains = pnl[pnl > 0].sum()
    losses = -pnl[pnl < 0].sum()
    return {
        "trades": len(dataframe),
        "tpd": len(dataframe) / days,
        "wr": float((pnl > 0).mean()),
        "return": float(pnl.sum() / 1000),
        "pf": float(gains / losses) if losses else 99.0,
        "dd": float(-drawdown.min()),
        "long": int((dataframe["side"] == 1).sum()),
        "short": int((dataframe["side"] == -1).sum()),
        "tails": int(dataframe["tail_loss"].sum()),
    }


def print_result(label: str, keep: float, result: dict[str, float | int]) -> None:
    print(
        f"{label},{keep:.2f},{result['trades']},{result['tpd']:.3f},{result['wr']:.4f},"
        f"{result['return']:.4f},{result['pf']:.3f},{result['dd']:.4f},"
        f"{result['long']},{result['short']},{result['tails']}"
    )


def selection_score(result: dict[str, float | int]) -> float:
    return (
        min(float(result["wr"]), 0.75) * 4
        + min(float(result["tpd"]), 4.0) * 0.3
        + min(float(result["return"]), 1.5) * 1.5
        + min(float(result["pf"]), 2.5)
        - max(0.0, 2.0 - float(result["tpd"])) * 4
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("development_zip", type=Path)
    parser.add_argument("sample_out_zip", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("user_data/data"))
    args = parser.parse_args()

    development = attach_features(load_trades(args.development_zip), args.data_dir)
    sample_out = attach_features(load_trades(args.sample_out_zip), args.data_dir)
    split = pd.Timestamp("2025-01-01", tz="UTC")
    initial_train = development[development["exit_date"] < split]
    validation = development[development["entry_date"] >= split].copy()
    initial_models = fit_models(initial_train)
    initial_scores = predict_score(initial_models, initial_train)
    validation["score"] = predict_score(initial_models, validation)

    print("window,keep,trades,tpd,winrate,return,pf,max_dd,long,short,tail_losses")
    candidates = []
    for keep in np.arange(0.40, 1.001, 0.05):
        threshold = float(np.quantile(initial_scores, 1 - keep))
        selected = validation[validation["score"] >= threshold]
        result = metrics(selected, 181)
        print_result("validation", float(keep), result)
        candidates.append((selection_score(result), float(keep), result))
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected_keep = candidates[0][1]

    final_models = fit_models(development)
    development_scores = predict_score(final_models, development)
    threshold = float(np.quantile(development_scores, 1 - selected_keep))
    sample_out["score"] = predict_score(final_models, sample_out)
    selected = sample_out[sample_out["score"] >= threshold]
    print_result("sample_out", selected_keep, metrics(selected, 365))


if __name__ == "__main__":
    main()
