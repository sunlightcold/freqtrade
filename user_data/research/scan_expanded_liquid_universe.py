from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import talib.abstract as ta


DATA_DIR = Path("user_data/data/binance/futures")
OUT_DIR = Path("user_data/research")

EXPANDED_BASES = [
    "ADA",
    "DOT",
    "ATOM",
    "ARB",
    "NEAR",
    "UNI",
    "FIL",
    "INJ",
    "ALGO",
    "HBAR",
    "FET",
    "GALA",
    "RUNE",
    "ICP",
    "SAND",
    "MANA",
    "1000SHIB",
    "1000PEPE",
]

WINDOWS = {
    "2023H2": ("2023-06-02", "2024-01-01"),
    "2024": ("2024-01-01", "2025-01-01"),
    "2025": ("2025-01-01", "2026-01-01"),
    "2026_01_05": ("2026-01-01", "2026-06-01"),
}


@dataclass(frozen=True)
class Rule:
    template: str
    side: str
    regime: str
    hold: int
    leverage: float
    params: dict


RULES = [
    Rule("panic_snapback", "long", "market_contra", 12, 4.0, {"atr_ceiling": 0.055, "atr_floor": 0.001, "range_mult": 0.85, "rsi_fast": 28, "shock": 0.004, "volume_z": 0.8, "wick_body": 1.4}),
    Rule("panic_snapback", "short", "market_contra", 12, 4.0, {"atr_ceiling": 0.055, "atr_floor": 0.001, "range_mult": 0.85, "rsi_fast": 28, "shock": 0.004, "volume_z": 0.8, "wick_body": 1.4}),
    Rule("rsi_reversion", "long", "local_chop", 24, 4.0, {"atr_ceiling": 0.024, "atr_floor": 0.0006, "band_pad": 0.998, "bb_width": 0.0035, "macro_limit": 0.045, "mfi_low": 35, "rsi_2_long": 8, "rsi_2_short": 92, "stoch_low": 28, "volume_mult": 0.7}),
    Rule("rsi_reversion", "short", "local_chop", 24, 4.0, {"atr_ceiling": 0.024, "atr_floor": 0.0006, "band_pad": 0.998, "bb_width": 0.0035, "macro_limit": 0.045, "mfi_low": 35, "rsi_2_long": 8, "rsi_2_short": 92, "stoch_low": 28, "volume_mult": 0.7}),
    Rule("micro_momentum", "long", "market_chop", 18, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0015, "roc_fast": 0.0015, "roc_slow": 0.002, "rsi_cap": 74, "rsi_fast": 58, "slope": 0.0004, "volume_mult": 1.0, "volume_z": 0.4, "width_mult": 0.9}),
    Rule("micro_momentum", "short", "market_chop", 18, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0015, "roc_fast": 0.0015, "roc_slow": 0.002, "rsi_cap": 74, "rsi_fast": 58, "slope": 0.0004, "volume_mult": 1.0, "volume_z": 0.4, "width_mult": 0.9}),
    Rule("vwap_reclaim", "long", "market_contra", 18, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0012, "macro_pullback": 0.045, "range_mult": 0.8, "rsi_reset": 38, "volume_mult": 1.0, "vwap_pad": 0.0008}),
    Rule("vwap_reclaim", "short", "market_contra", 18, 5.0, {"atr_ceiling": 0.030, "atr_floor": 0.0012, "macro_pullback": 0.045, "range_mult": 0.8, "rsi_reset": 38, "volume_mult": 1.0, "vwap_pad": 0.0008}),
    Rule("range_breakout", "long", "market_aligned", 24, 4.0, {"atr_ceiling": 0.030, "atr_floor": 0.0006, "range_mult": 0.65, "roc_fast": 0.0006, "rsi_max": 76, "rsi_min": 45, "slope": 0.0002, "squeeze_mult": 0.8, "volume_z": 0.7}),
    Rule("range_breakout", "short", "market_aligned", 24, 4.0, {"atr_ceiling": 0.030, "atr_floor": 0.0006, "range_mult": 0.65, "roc_fast": 0.0006, "rsi_max": 76, "rsi_min": 45, "slope": 0.0002, "squeeze_mult": 0.8, "volume_z": 0.7}),
    Rule("stoch_turn", "long", "local_trend", 24, 4.0, {"atr_ceiling": 0.030, "atr_floor": 0.0006, "cci_low": -70, "range_mult": 0.7, "roc_limit": 0.018, "turn_level": 24, "volume_mult": 0.7}),
    Rule("stoch_turn", "short", "local_trend", 24, 4.0, {"atr_ceiling": 0.030, "atr_floor": 0.0006, "cci_low": -70, "range_mult": 0.7, "roc_limit": 0.018, "turn_level": 24, "volume_mult": 0.7}),
]


def load_5m(base: str) -> pd.DataFrame:
    path = DATA_DIR / f"{base}_USDT_USDT-1m-futures.feather"
    df = pd.read_feather(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return (
        df.set_index("date")
        .resample("5min", label="right", closed="right")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
        .reset_index()
    )


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema_8"] = ta.EMA(df, timeperiod=8)
    df["ema_20"] = ta.EMA(df, timeperiod=20)
    df["ema_50"] = ta.EMA(df, timeperiod=50)
    df["ema_200"] = ta.EMA(df, timeperiod=200)
    df["rsi_2"] = ta.RSI(df, timeperiod=2)
    df["rsi_fast"] = ta.RSI(df, timeperiod=4)
    df["rsi"] = ta.RSI(df, timeperiod=14)
    df["atr"] = ta.ATR(df, timeperiod=14)
    df["atr_pct"] = df["atr"] / df["close"]
    df["volume_mean_48"] = df["volume"].rolling(48).mean()
    df["volume_mean_96"] = df["volume"].rolling(96).mean()
    df["volume_z"] = (df["volume"] - df["volume_mean_96"]) / df["volume"].rolling(96).std()
    typical = (df["high"] + df["low"] + df["close"]) / 3
    mid = typical.rolling(20).mean()
    std = typical.rolling(20).std()
    df["bb_mid"] = mid
    df["bb_low"] = mid - 2 * std
    df["bb_high"] = mid + 2 * std
    df["bb_width"] = (df["bb_high"] - df["bb_low"]) / df["bb_mid"]
    df["bb_width_mean_96"] = df["bb_width"].rolling(96).mean()
    df["don_high_12"] = df["high"].rolling(12).max().shift(1)
    df["don_low_12"] = df["low"].rolling(12).min().shift(1)
    df["don_high_24"] = df["high"].rolling(24).max().shift(1)
    df["don_low_24"] = df["low"].rolling(24).min().shift(1)
    for period in (3, 6, 12, 24, 48):
        df[f"roc_{period}"] = df["close"] / df["close"].shift(period) - 1
    df["ema_8_slope"] = df["ema_8"] / df["ema_8"].shift(8) - 1
    df["ema_20_slope"] = df["ema_20"] / df["ema_20"].shift(12) - 1
    df["ema_50_slope"] = df["ema_50"] / df["ema_50"].shift(24) - 1
    df["range_pct"] = (df["high"] - df["low"]) / df["close"]
    df["body_pct"] = (df["close"] - df["open"]).abs() / df["close"]
    df["upper_wick_pct"] = (df["high"] - df[["open", "close"]].max(axis=1)) / df["close"]
    df["lower_wick_pct"] = (df[["open", "close"]].min(axis=1) - df["low"]) / df["close"]
    low_14 = df["low"].rolling(14).min()
    high_14 = df["high"].rolling(14).max()
    df["stoch_k"] = 100 * (df["close"] - low_14) / (high_14 - low_14)
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()
    money_flow = typical * df["volume"]
    pos = money_flow.where(typical > typical.shift(), 0.0)
    neg = money_flow.where(typical < typical.shift(), 0.0)
    money_ratio = pos.rolling(14).sum() / neg.rolling(14).sum().replace(0, np.nan)
    df["mfi"] = 100 - (100 / (1 + money_ratio))
    typical_mean = typical.rolling(20).mean()
    typical_dev = (typical - typical_mean).abs().rolling(20).mean()
    df["cci"] = (typical - typical_mean) / (0.015 * typical_dev)
    df["vwap_24"] = (typical * df["volume"]).rolling(24).sum() / df["volume"].rolling(24).sum()
    df["vwap_96"] = (typical * df["volume"]).rolling(96).sum() / df["volume"].rolling(96).sum()
    df["vwap_96_dist"] = df["close"] / df["vwap_96"] - 1
    df["local_up"] = (df["close"] > df["ema_50"]) & (df["ema_20"] > df["ema_50"]) & (df["ema_20_slope"] > 0)
    df["local_down"] = (df["close"] < df["ema_50"]) & (df["ema_20"] < df["ema_50"]) & (df["ema_20_slope"] < 0)
    df["local_chop"] = ~df["local_up"] & ~df["local_down"] & (df["bb_width"] < df["bb_width_mean_96"] * 1.10)
    df["market_bull"] = (df["close"] > df["ema_200"]) & (df["ema_50_slope"] > 0) & (df["rsi"] > 45)
    df["market_bear"] = (df["close"] < df["ema_200"]) & (df["ema_50_slope"] < 0) & (df["rsi"] < 55)
    df["market_high_vol"] = (df["atr_pct"] > df["atr_pct"].rolling(288).mean() * 1.20) | (df["bb_width"] > df["bb_width_mean_96"] * 1.25)
    df["market_chop"] = ~df["market_bull"] & ~df["market_bear"] & (df["bb_width"] < df["bb_width_mean_96"] * 1.15)
    df["market_panic_down"] = (df["roc_48"] < -0.035) | (df["roc_24"] < -0.025)
    df["market_euphoria_up"] = (df["roc_48"] > 0.035) | (df["roc_24"] > 0.025)
    return df


def merge_btc_regime(df: pd.DataFrame, btc: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "date",
        "market_bull",
        "market_bear",
        "market_high_vol",
        "market_chop",
        "market_panic_down",
        "market_euphoria_up",
    ]
    x = df.merge(btc[cols].rename(columns={c: f"btc_{c}" for c in cols if c != "date"}), on="date", how="left")
    btc_cols = [c for c in x.columns if c.startswith("btc_")]
    x[btc_cols] = x[btc_cols].ffill().fillna(False)
    return x


def regime_mask(df: pd.DataFrame, rule: Rule) -> pd.Series:
    side = rule.side
    if rule.regime == "local_trend":
        return df["local_up"] if side == "long" else df["local_down"]
    if rule.regime == "local_chop":
        return df["local_chop"]
    if rule.regime == "market_aligned":
        return df["btc_market_bull"] if side == "long" else df["btc_market_bear"]
    if rule.regime == "market_contra":
        return df["btc_market_bear"] if side == "long" else df["btc_market_bull"]
    if rule.regime == "market_chop":
        return df["btc_market_chop"]
    raise ValueError(rule.regime)


def signal(df: pd.DataFrame, rule: Rule) -> pd.Series:
    p = rule.params
    side = rule.side
    risk_ok = pd.Series(True, index=df.index)
    if rule.template == "panic_snapback":
        risk_ok = (df["atr_pct"] > p["atr_floor"]) & (df["atr_pct"] < p["atr_ceiling"]) & (df["volume_z"] > p["volume_z"]) & (df["range_pct"] > df["atr_pct"] * p["range_mult"])
        if side == "long":
            return risk_ok & (df["roc_3"] < -p["shock"]) & (df["low"] < df["don_low_12"]) & (df["lower_wick_pct"] > df["body_pct"] * p["wick_body"]) & (df["close"] > df["open"]) & (df["rsi_fast"] < p["rsi_fast"])
        return risk_ok & (df["roc_3"] > p["shock"]) & (df["high"] > df["don_high_12"]) & (df["upper_wick_pct"] > df["body_pct"] * p["wick_body"]) & (df["close"] < df["open"]) & (df["rsi_fast"] > 100 - p["rsi_fast"])
    if rule.template == "rsi_reversion":
        risk_ok = (df["atr_pct"] > p["atr_floor"]) & (df["atr_pct"] < p["atr_ceiling"]) & (df["volume"] > df["volume_mean_48"] * p["volume_mult"]) & (df["bb_width"] > p["bb_width"])
        if side == "long":
            return risk_ok & (df["low"] < df["bb_low"] * p["band_pad"]) & (df["rsi_2"] < p["rsi_2_long"]) & (df["stoch_k"] < p["stoch_low"]) & (df["mfi"] < p["mfi_low"]) & (df["roc_12"] > -p["macro_limit"]) & (df["close"] > df["low"] + (df["high"] - df["low"]) * 0.35)
        return risk_ok & (df["high"] > df["bb_high"] / p["band_pad"]) & (df["rsi_2"] > p["rsi_2_short"]) & (df["stoch_k"] > 100 - p["stoch_low"]) & (df["mfi"] > 100 - p["mfi_low"]) & (df["roc_12"] < p["macro_limit"]) & (df["close"] < df["high"] - (df["high"] - df["low"]) * 0.35)
    if rule.template == "micro_momentum":
        risk_ok = (df["atr_pct"] > p["atr_floor"]) & (df["atr_pct"] < p["atr_ceiling"]) & (df["volume"] > df["volume_mean_48"] * p["volume_mult"]) & (df["volume_z"] > p["volume_z"]) & (df["bb_width"] > df["bb_width_mean_96"] * p["width_mult"])
        if side == "long":
            return risk_ok & (df["ema_8"] > df["ema_20"]) & (df["ema_20"] > df["ema_50"]) & (df["ema_20_slope"] > p["slope"]) & (df["close"] > df["don_high_12"]) & (df["roc_3"] > p["roc_fast"]) & (df["roc_12"] > p["roc_slow"]) & (df["rsi_fast"] > p["rsi_fast"]) & (df["rsi"] < p["rsi_cap"])
        return risk_ok & (df["ema_8"] < df["ema_20"]) & (df["ema_20"] < df["ema_50"]) & (df["ema_20_slope"] < -p["slope"]) & (df["close"] < df["don_low_12"]) & (df["roc_3"] < -p["roc_fast"]) & (df["roc_12"] < -p["roc_slow"]) & (df["rsi_fast"] < 100 - p["rsi_fast"]) & (df["rsi"] > 100 - p["rsi_cap"])
    if rule.template == "vwap_reclaim":
        crossed_up = (df["close"] > df["vwap_96"]) & (df["close"].shift(1) <= df["vwap_96"].shift(1))
        crossed_down = (df["close"] < df["vwap_96"]) & (df["close"].shift(1) >= df["vwap_96"].shift(1))
        risk_ok = (df["atr_pct"] > p["atr_floor"]) & (df["atr_pct"] < p["atr_ceiling"]) & (df["volume"] > df["volume_mean_96"] * p["volume_mult"]) & (df["range_pct"] > df["atr_pct"] * p["range_mult"])
        if side == "long":
            return risk_ok & (df["ema_20"] > df["ema_50"]) & (df["roc_24"] > -p["macro_pullback"]) & (df["low"] < df["vwap_96"] * (1 - p["vwap_pad"])) & crossed_up & (df["rsi_fast"] > df["rsi_fast"].shift(1)) & (df["rsi_fast"].shift(1) < p["rsi_reset"])
        return risk_ok & (df["ema_20"] < df["ema_50"]) & (df["roc_24"] < p["macro_pullback"]) & (df["high"] > df["vwap_96"] * (1 + p["vwap_pad"])) & crossed_down & (df["rsi_fast"] < df["rsi_fast"].shift(1)) & (df["rsi_fast"].shift(1) > 100 - p["rsi_reset"])
    if rule.template == "range_breakout":
        squeezed = df["bb_width"].shift(1) < df["bb_width_mean_96"].shift(1) * p["squeeze_mult"]
        risk_ok = (df["atr_pct"] > p["atr_floor"]) & (df["atr_pct"] < p["atr_ceiling"]) & (df["volume_z"] > p["volume_z"]) & (df["range_pct"] > df["atr_pct"] * p["range_mult"]) & squeezed
        if side == "long":
            return risk_ok & (df["close"] > df["don_high_24"]) & (df["close"] > df["vwap_24"]) & (df["ema_8_slope"] > p["slope"]) & (df["roc_3"] > p["roc_fast"]) & (df["rsi"] > p["rsi_min"]) & (df["rsi"] < p["rsi_max"])
        return risk_ok & (df["close"] < df["don_low_24"]) & (df["close"] < df["vwap_24"]) & (df["ema_8_slope"] < -p["slope"]) & (df["roc_3"] < -p["roc_fast"]) & (df["rsi"] < 100 - p["rsi_min"]) & (df["rsi"] > 100 - p["rsi_max"])
    if rule.template == "stoch_turn":
        crossed_up = (df["stoch_k"] > df["stoch_d"]) & (df["stoch_k"].shift(1) <= df["stoch_d"].shift(1))
        crossed_down = (df["stoch_k"] < df["stoch_d"]) & (df["stoch_k"].shift(1) >= df["stoch_d"].shift(1))
        risk_ok = (df["atr_pct"] > p["atr_floor"]) & (df["atr_pct"] < p["atr_ceiling"]) & (df["volume"] > df["volume_mean_48"] * p["volume_mult"]) & (df["range_pct"] > df["atr_pct"] * p["range_mult"])
        if side == "long":
            return risk_ok & (df["local_up"] | df["local_chop"]) & crossed_up & (df["stoch_k"].shift(1) < p["turn_level"]) & (df["rsi_fast"] > df["rsi_fast"].shift(1)) & (df["cci"] < p["cci_low"]) & (df["roc_6"] > -p["roc_limit"])
        return risk_ok & (df["local_down"] | df["local_chop"]) & crossed_down & (df["stoch_k"].shift(1) > 100 - p["turn_level"]) & (df["rsi_fast"] < df["rsi_fast"].shift(1)) & (df["cci"] > -p["cci_low"]) & (df["roc_6"] < p["roc_limit"])
    raise ValueError(rule.template)


def evaluate_rule(df: pd.DataFrame, mask: pd.Series, rule: Rule) -> list[dict]:
    idx = np.flatnonzero(mask.fillna(False).to_numpy())
    rows = []
    last_exit = -1
    close = df["close"].to_numpy()
    dates = df["date"].to_numpy()
    for i in idx:
        exit_i = i + rule.hold
        if i <= last_exit or exit_i >= len(df):
            continue
        raw = close[exit_i] / close[i] - 1
        ret = raw if rule.side == "long" else -raw
        lev_ret = ret * rule.leverage
        rows.append({"date": pd.Timestamp(dates[i]), "profit_ratio": lev_ret})
        last_exit = exit_i
    return rows


def summarize(base: str, rule: Rule, trades: list[dict]) -> list[dict]:
    out = []
    key = f"{base}:{rule.template}:{rule.side}:{rule.regime}:h{rule.hold}:l{int(rule.leverage)}"
    for window, (start, end) in WINDOWS.items():
        start_ts = pd.Timestamp(start, tz="UTC")
        end_ts = pd.Timestamp(end, tz="UTC")
        vals = [t["profit_ratio"] for t in trades if start_ts <= t["date"] < end_ts]
        if vals:
            arr = np.array(vals)
            wins = int((arr > 0).sum())
            losses = int((arr <= 0).sum())
            pos = arr[arr > 0].sum()
            neg = -arr[arr < 0].sum()
            pf = float(pos / neg) if neg > 0 else (999.0 if pos > 0 else 0.0)
            profit = float(arr.sum())
            avg = float(arr.mean())
            winrate = wins / len(arr) * 100
        else:
            wins = losses = 0
            pf = profit = avg = winrate = 0.0
        out.append({
            "window": window,
            "base": base,
            "rule": key,
            "template": rule.template,
            "side": rule.side,
            "regime": rule.regime,
            "hold_5m": rule.hold,
            "leverage": rule.leverage,
            "trades": len(vals),
            "profit_ratio_sum": profit,
            "profit_pct_sum": profit * 100,
            "avg_trade_pct": avg * 100,
            "wins": wins,
            "losses": losses,
            "winrate_pct": winrate,
            "profit_factor": pf,
        })
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    btc = add_indicators(load_5m("BTC"))
    rows = []
    trade_rows = []
    for n, base in enumerate(EXPANDED_BASES, start=1):
        print(f"[{n}/{len(EXPANDED_BASES)}] scanning {base}")
        df = merge_btc_regime(add_indicators(load_5m(base)), btc)
        for rule in RULES:
            m = signal(df, rule) & regime_mask(df, rule)
            trades = evaluate_rule(df, m, rule)
            rows.extend(summarize(base, rule, trades))
            trade_rows.extend([
                {
                    "base": base,
                    "rule": f"{base}:{rule.template}:{rule.side}:{rule.regime}:h{rule.hold}:l{int(rule.leverage)}",
                    "template": rule.template,
                    "side": rule.side,
                    "regime": rule.regime,
                    "date": t["date"].isoformat(),
                    "profit_pct": t["profit_ratio"] * 100,
                }
                for t in trades
            ])
    summary_path = OUT_DIR / "expanded_liquid_template_scan_summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    trades_path = OUT_DIR / "expanded_liquid_template_scan_trades.csv"
    with trades_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(trade_rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(trade_rows)

    main_windows = {"2024", "2025", "2026_01_05"}
    by_rule: dict[str, dict] = {}
    for row in rows:
        if row["window"] not in main_windows:
            continue
        item = by_rule.setdefault(
            row["rule"],
            {
                "base": row["base"],
                "rule": row["rule"],
                "template": row["template"],
                "side": row["side"],
                "regime": row["regime"],
                "main_profit_pct": 0.0,
                "main_trades": 0,
                "losing_windows": 0,
                "profitable_windows": 0,
            },
        )
        item["main_profit_pct"] += row["profit_pct_sum"]
        item["main_trades"] += row["trades"]
        if row["profit_pct_sum"] < 0:
            item["losing_windows"] += 1
        if row["profit_pct_sum"] > 0:
            item["profitable_windows"] += 1
    rank_rows = sorted(by_rule.values(), key=lambda x: x["main_profit_pct"], reverse=True)
    rank_path = OUT_DIR / "expanded_liquid_template_scan_rank.csv"
    with rank_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rank_rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rank_rows)
    print(summary_path)
    print(trades_path)
    print(rank_path)


if __name__ == "__main__":
    main()
