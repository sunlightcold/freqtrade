from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path


STRATEGY = "Intp20Stage13Validated20Strategy"
STARTING_BALANCE = 10_000.0
DAILY_TARGET_PCT = 0.5

WINDOWS = [
    ("2023H2", Path("user_data/backtest_results/backtest-result-2026-06-10_19-01-12.zip")),
    ("2024", Path("user_data/backtest_results/backtest-result-2026-06-10_18-58-20.zip")),
    ("2025", Path("user_data/backtest_results/backtest-result-2026-06-10_18-51-48.zip")),
    ("2026_01_05", Path("user_data/backtest_results/backtest-result-2026-06-10_18-47-07.zip")),
]

FINAL_PAIRS = [
    "MKR/USDT:USDT",
    "SOL/USDT:USDT",
    "XLM/USDT:USDT",
    "AAVE/USDT:USDT",
    "XTZ/USDT:USDT",
    "XRP/USDT:USDT",
    "ETH/USDT:USDT",
    "SUI/USDT:USDT",
    "ETC/USDT:USDT",
    "LTC/USDT:USDT",
    "COMP/USDT:USDT",
    "OP/USDT:USDT",
    "APT/USDT:USDT",
    "DOGE/USDT:USDT",
    "DOT/USDT:USDT",
    "ICP/USDT:USDT",
    "NEAR/USDT:USDT",
    "FET/USDT:USDT",
    "UNI/USDT:USDT",
    "MANA/USDT:USDT",
]

EXCLUDED_CANDIDATES = {
    "SAND": "native windows had ugly stop-loss behavior",
    "FIL": "native windows had ugly stop-loss behavior",
    "1000PEPE": "native windows had ugly stop-loss behavior",
    "RUNE": "unstable native windows",
    "ADA": "weak 2026 native validation",
    "ARB": "unstable native windows",
    "1000SHIB": "marginal edge versus the final six additions",
}


def load_result(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        json_names = [
            name
            for name in archive.namelist()
            if name.endswith(".json") and not name.endswith("_config.json")
        ]
        if not json_names:
            raise ValueError(f"No result json found in {path}")
        payload = json.loads(archive.read(json_names[0]))
    return payload["strategy"][STRATEGY]


def pct(value: float | int | None) -> float:
    return float(value or 0.0) * 100.0


def row_float(row: dict, key: str) -> float:
    return float(row.get(key) or 0.0)


def row_int(row: dict, key: str) -> int:
    return int(row.get(key) or 0)


def pair_base(pair: str) -> str:
    return pair.split("/")[0]


def round_float(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def window_days(result: dict) -> int:
    days = result.get("backtest_days")
    if days:
        return int(days)
    return len(result.get("periodic_breakdown", {}).get("day", []))


def daily_target_stats(result: dict) -> dict:
    target_abs = STARTING_BALANCE * (DAILY_TARGET_PCT / 100.0)
    days = result.get("periodic_breakdown", {}).get("day", [])
    if not days:
        return {
            "target_abs": target_abs,
            "calendar_days": 0,
            "target_days": 0,
            "target_hit_rate_pct": 0.0,
        }
    target_days = sum(1 for row in days if row_float(row, "profit_abs") >= target_abs)
    return {
        "target_abs": target_abs,
        "calendar_days": len(days),
        "target_days": target_days,
        "target_hit_rate_pct": target_days / len(days) * 100.0,
    }


def pair_summary(result: dict, key: str) -> dict:
    value = result.get(key) or {}
    if not isinstance(value, dict):
        return {"pair": "", "profit_pct": 0.0}
    return {
        "pair": value.get("key", ""),
        "profit_pct": round_float(pct(value.get("profit_total")), 4),
    }


def portfolio_row(window: str, result: dict) -> dict:
    days = window_days(result)
    profit_pct = pct(result.get("profit_total"))
    target = daily_target_stats(result)
    daily_compound = ((1.0 + (result.get("profit_total") or 0.0)) ** (1.0 / days) - 1.0) * 100.0 if days else 0.0
    total_trades = row_int(result, "total_trades")
    wins = row_int(result, "wins")
    losses = row_int(result, "losses")
    winrate = wins / total_trades * 100.0 if total_trades else 0.0
    best_pair = pair_summary(result, "best_pair")
    worst_pair = pair_summary(result, "worst_pair")

    return {
        "window": window,
        "backtest_start": result.get("backtest_start", ""),
        "backtest_end": result.get("backtest_end", ""),
        "days": days,
        "starting_balance": row_float(result, "starting_balance"),
        "final_balance": round_float(row_float(result, "final_balance"), 4),
        "profit_abs": round_float(row_float(result, "profit_total_abs"), 4),
        "profit_pct": round_float(profit_pct, 4),
        "cagr_pct": round_float(pct(result.get("cagr")), 4),
        "daily_simple_pct": round_float(profit_pct / days if days else 0.0, 4),
        "daily_compound_pct": round_float(daily_compound, 4),
        "daily_0p5_target_abs": round_float(target["target_abs"], 4),
        "daily_0p5_target_days": target["target_days"],
        "daily_0p5_hit_rate_pct": round_float(target["target_hit_rate_pct"], 4),
        "trades": total_trades,
        "trades_per_day": round_float(total_trades / days if days else 0.0, 4),
        "wins": wins,
        "losses": losses,
        "winrate_pct": round_float(winrate, 4),
        "profit_factor": round_float(row_float(result, "profit_factor"), 4),
        "long_trades": row_int(result, "trade_count_long"),
        "short_trades": row_int(result, "trade_count_short"),
        "long_profit_abs": round_float(row_float(result, "profit_total_long_abs"), 4),
        "short_profit_abs": round_float(row_float(result, "profit_total_short_abs"), 4),
        "long_profit_pct": round_float(pct(result.get("profit_total_long")), 4),
        "short_profit_pct": round_float(pct(result.get("profit_total_short")), 4),
        "max_drawdown_pct": round_float(pct(result.get("max_drawdown_account")), 4),
        "max_drawdown_abs": round_float(row_float(result, "max_drawdown_abs"), 4),
        "market_change_pct": round_float(pct(result.get("market_change")), 4),
        "best_pair": best_pair["pair"],
        "best_pair_profit_pct": best_pair["profit_pct"],
        "worst_pair": worst_pair["pair"],
        "worst_pair_profit_pct": worst_pair["profit_pct"],
        "best_trade": result.get("best_trade", ""),
        "worst_trade": result.get("worst_trade", ""),
    }


def pair_rows(window: str, result: dict) -> list[dict]:
    rows: list[dict] = []
    for row in result.get("results_per_pair", []):
        pair = row.get("key", "")
        if not pair or pair == "TOTAL":
            continue
        rows.append(
            {
                "window": window,
                "pair": pair,
                "base": pair_base(pair),
                "trades": row_int(row, "trades"),
                "profit_abs": round_float(row_float(row, "profit_total_abs"), 4),
                "profit_pct": round_float(pct(row.get("profit_total")), 4),
                "avg_profit_pct": round_float(pct(row.get("profit_mean")), 4),
                "cagr_pct": round_float(pct(row.get("cagr")), 4),
                "wins": row_int(row, "wins"),
                "losses": row_int(row, "losses"),
                "winrate_pct": round_float(row_float(row, "winrate") * 100.0, 4),
                "profit_factor": round_float(row_float(row, "profit_factor"), 4),
                "max_drawdown_pct": round_float(pct(row.get("max_drawdown_account")), 4),
                "max_drawdown_abs": round_float(row_float(row, "max_drawdown_abs"), 4),
            }
        )
    return rows


def build_pair_rank(rows: list[dict]) -> list[dict]:
    by_pair: dict[str, dict] = {}
    for row in rows:
        item = by_pair.setdefault(
            row["pair"],
            {
                "pair": row["pair"],
                "base": row["base"],
                "total_profit_abs": 0.0,
                "total_profit_pct_points": 0.0,
                "total_trades": 0,
                "profitable_windows": 0,
                "losing_windows": 0,
                "windows_with_trades": 0,
                "zero_trade_windows": 0,
                "min_window_profit_abs": row["profit_abs"],
                "min_window_profit_pct": row["profit_pct"],
                "min_window_trades": row["trades"],
            },
        )
        window = row["window"]
        item["total_profit_abs"] += row["profit_abs"]
        item["total_profit_pct_points"] += row["profit_pct"]
        item["total_trades"] += row["trades"]
        item["profitable_windows"] += 1 if row["profit_abs"] > 0 else 0
        item["losing_windows"] += 1 if row["profit_abs"] < 0 else 0
        item["windows_with_trades"] += 1 if row["trades"] > 0 else 0
        item["zero_trade_windows"] += 1 if row["trades"] == 0 else 0
        item["min_window_profit_abs"] = min(item["min_window_profit_abs"], row["profit_abs"])
        item["min_window_profit_pct"] = min(item["min_window_profit_pct"], row["profit_pct"])
        item["min_window_trades"] = min(item["min_window_trades"], row["trades"])
        item[f"{window}_profit_abs"] = row["profit_abs"]
        item[f"{window}_profit_pct"] = row["profit_pct"]
        item[f"{window}_trades"] = row["trades"]

    rank_rows = list(by_pair.values())
    for item in rank_rows:
        item["total_profit_abs"] = round_float(item["total_profit_abs"], 4)
        item["total_profit_pct_points"] = round_float(item["total_profit_pct_points"], 4)
    return sorted(rank_rows, key=lambda item: item["total_profit_abs"], reverse=True)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(path)


def markdown_table(rows: list[dict], columns: list[str]) -> str:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return "\n".join(lines)


def write_markdown(path: Path, portfolio_rows: list[dict], pair_rank_rows: list[dict]) -> None:
    pair_list = ", ".join(pair_base(pair) for pair in FINAL_PAIRS)
    excluded = "\n".join(f"- {base}: {reason}" for base, reason in EXCLUDED_CANDIDATES.items())
    source_rows = [
        {
            "window": window,
            "result_zip": str(result_path).replace("\\", "/"),
        }
        for window, result_path in WINDOWS
    ]
    source_table = markdown_table(source_rows, ["window", "result_zip"])
    portfolio_table = markdown_table(
        portfolio_rows,
        [
            "window",
            "starting_balance",
            "final_balance",
            "profit_pct",
            "cagr_pct",
            "daily_simple_pct",
            "daily_compound_pct",
            "daily_0p5_hit_rate_pct",
            "trades",
            "long_trades",
            "short_trades",
            "profit_factor",
            "max_drawdown_pct",
        ],
    )
    rank_table = markdown_table(
        pair_rank_rows,
        [
            "base",
            "total_profit_abs",
            "total_profit_pct_points",
            "total_trades",
            "profitable_windows",
            "losing_windows",
            "windows_with_trades",
            "zero_trade_windows",
            "min_window_profit_pct",
            "min_window_trades",
            "2023H2_profit_pct",
            "2024_profit_pct",
            "2025_profit_pct",
            "2026_01_05_profit_pct",
        ],
    )

    content = f"""# Stage 13 Validated 20-Pair Dry-Run Universe

Generated from native Freqtrade futures backtests for `{STRATEGY}` on 1m data.

## Source Results

{source_table}

## Admission Rule

Only pairs with native Freqtrade portfolio evidence are promoted to the dry-run whitelist. Template-scan candidates alone are not enough. The final dry-run configuration uses a 10,000 USDT wallet, 1,000 USDT fixed stake, isolated futures, and `max_open_trades = 8`.

## Final 20 Pairs

{pair_list}

Base Stage-12 universe: MKR, SOL, XLM, AAVE, XTZ, XRP, ETH, SUI, ETC, LTC, COMP, OP, APT, DOGE.

Stage-13 additions: DOT, ICP, NEAR, FET, UNI, MANA.

## Portfolio Windows

{portfolio_table}

The current validated set does not reach the requested 0.5% average daily target in every window. The strongest full-year windows are near 0.25% simple daily return on starting balance, while 2023H2 is much weaker. Treat this as a dry-run candidate, not a return guarantee.

## Pair Ranking

{rank_table}

## Excluded Expansion Candidates

{excluded}

## Dry-Run Command

```powershell
.\\.venv\\Scripts\\freqtrade.exe trade -c user_data\\config_binance_stage13_validated_20pair_dryrun.json --strategy {STRATEGY}
```

## Validation Commands

```powershell
.\\.venv\\Scripts\\python.exe user_data\\scripts\\run_offline_futures_backtest.py -c user_data\\config_binance_stage13_validated_20pair_dryrun.json --strategy {STRATEGY} --timerange 20230602-20240101 --breakdown year --export trades --cache none
.\\.venv\\Scripts\\python.exe user_data\\scripts\\run_offline_futures_backtest.py -c user_data\\config_binance_stage13_validated_20pair_dryrun.json --strategy {STRATEGY} --timerange 20240101-20250101 --breakdown year --export trades --cache none
.\\.venv\\Scripts\\python.exe user_data\\scripts\\run_offline_futures_backtest.py -c user_data\\config_binance_stage13_validated_20pair_dryrun.json --strategy {STRATEGY} --timerange 20250101-20260101 --breakdown year --export trades --cache none
.\\.venv\\Scripts\\python.exe user_data\\scripts\\run_offline_futures_backtest.py -c user_data\\config_binance_stage13_validated_20pair_dryrun.json --strategy {STRATEGY} --timerange 20260101-20260601 --breakdown year --export trades --cache none
```
"""
    path.write_text(content, encoding="utf-8", newline="\n")
    print(path)


def main() -> None:
    out_dir = Path("user_data/research")
    out_dir.mkdir(parents=True, exist_ok=True)

    portfolio_rows: list[dict] = []
    all_pair_rows: list[dict] = []
    for window, path in WINDOWS:
        result = load_result(path)
        portfolio_rows.append(portfolio_row(window, result))
        all_pair_rows.extend(pair_rows(window, result))

    pair_rank_rows = build_pair_rank(all_pair_rows)

    write_csv(out_dir / "stage13_validated20_portfolio_windows.csv", portfolio_rows)
    write_csv(out_dir / "stage13_validated20_pair_window_matrix.csv", all_pair_rows)
    write_csv(out_dir / "stage13_validated20_pair_rank.csv", pair_rank_rows)
    write_markdown(out_dir / "stage13_dryrun_universe.md", portfolio_rows, pair_rank_rows)


if __name__ == "__main__":
    main()
