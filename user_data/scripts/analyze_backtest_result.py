"""
Summarize a Freqtrade backtest result zip for strategy research.

The native backtest report is intentionally rich, but it is awkward to compare
several strategy variants by hand. This helper extracts the fields that matter
for walk-forward pruning: total metrics, pair stats, enter-tag stats, and
periodic breakdowns.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Iterable


PCT_FIELDS = {
    "profit_total",
    "profit_mean",
    "profit_median",
    "max_drawdown_account",
    "market_change",
    "winrate",
}


def load_strategy_result(path: Path, strategy: str | None) -> tuple[str, dict]:
    with zipfile.ZipFile(path) as archive:
        json_names = [
            name
            for name in archive.namelist()
            if name.endswith(".json") and not name.endswith("_config.json")
        ]
        if not json_names:
            raise ValueError(f"No result json found in {path}")
        payload = json.loads(archive.read(json_names[0]))

    strategies = payload["strategy"]
    if strategy:
        if strategy not in strategies:
            raise ValueError(f"Strategy {strategy!r} not found in {path}")
        return strategy, strategies[strategy]
    if len(strategies) != 1:
        names = ", ".join(strategies)
        raise ValueError(f"Multiple strategies found, pass --strategy. Found: {names}")
    name = next(iter(strategies))
    return name, strategies[name]


def fmt_value(key: str, value: object) -> str:
    if isinstance(value, float):
        if key in PCT_FIELDS:
            return f"{value * 100:.2f}%"
        return f"{value:.4f}"
    return str(value)


def print_metrics(strategy: str, result: dict) -> None:
    metric_keys = [
        "backtest_start",
        "backtest_end",
        "backtest_days",
        "total_trades",
        "trades_per_day",
        "profit_total",
        "profit_total_abs",
        "cagr",
        "profit_factor",
        "sharpe",
        "sortino",
        "calmar",
        "max_drawdown_account",
        "max_drawdown_abs",
        "drawdown_start",
        "drawdown_end",
        "market_change",
        "trade_count_long",
        "trade_count_short",
    ]
    print(f"strategy,{strategy}")
    for key in metric_keys:
        if key in result:
            print(f"{key},{fmt_value(key, result[key])}")


def row_value(row: dict, key: str) -> object:
    value = row.get(key, "")
    if isinstance(value, float):
        if key in PCT_FIELDS or key.endswith("_pct"):
            return f"{value * 100:.2f}%"
        return f"{value:.4f}"
    return value


def print_rows(title: str, rows: Iterable[dict], limit: int) -> None:
    fields = [
        "key",
        "trades",
        "profit_mean",
        "profit_total_abs",
        "profit_total",
        "wins",
        "losses",
        "winrate",
        "profit_factor",
        "expectancy",
        "duration_avg",
    ]
    print(title)
    print(",".join(fields))
    for index, row in enumerate(rows):
        if limit > 0 and index >= limit:
            break
        print(",".join(str(row_value(row, field)) for field in fields))


def print_breakdown(result: dict, period: str) -> None:
    breakdown = result.get("periodic_breakdown", {}).get(period, [])
    if not breakdown:
        return
    print(f"{period}_breakdown")
    fields = ["date", "trades", "profit_abs", "profit_factor", "wins", "draws", "losses", "winrate"]
    print(",".join(fields))
    for row in breakdown:
        print(",".join(str(row_value(row, field)) for field in fields))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a Freqtrade backtest result zip.")
    parser.add_argument("zipfile", type=Path)
    parser.add_argument("--strategy", default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--sections",
        nargs="+",
        default=["metrics", "pairs", "tags", "month", "year"],
        choices=["metrics", "pairs", "tags", "exits", "month", "year", "weekday"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    strategy, result = load_strategy_result(args.zipfile, args.strategy)
    if "metrics" in args.sections:
        print_metrics(strategy, result)
    if "pairs" in args.sections:
        print_rows("pairs", result.get("results_per_pair", []), args.limit)
    if "tags" in args.sections:
        print_rows("enter_tags", result.get("results_per_enter_tag", []), args.limit)
    if "exits" in args.sections:
        print_rows("exit_reasons", result.get("exit_reason_summary", []), args.limit)
    for period in ("month", "year", "weekday"):
        if period in args.sections:
            print_breakdown(result, period)


if __name__ == "__main__":
    main()
