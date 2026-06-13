"""
Run offline futures backtests in smaller date windows and summarize the results.

This avoids loading a full year of 1m data for a broad pair universe in one
Freqtrade process. Each window is a fresh process, so pandas/Freqtrade memory is
released before the next window starts.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DATE_FMT = "%Y%m%d"


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime

    @property
    def timerange(self) -> str:
        return f"{self.start:{DATE_FMT}}-{self.end:{DATE_FMT}}"


def add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return value.replace(year=year, month=month)


def build_windows(start: str, end: str, months: int) -> list[Window]:
    if months < 1:
        raise ValueError("--months-per-window must be >= 1")
    cursor = datetime.strptime(start, DATE_FMT)
    final = datetime.strptime(end, DATE_FMT)
    if cursor >= final:
        raise ValueError("--start must be before --end")

    windows: list[Window] = []
    while cursor < final:
        next_end = min(add_months(cursor, months), final)
        windows.append(Window(cursor, next_end))
        cursor = next_end
    return windows


def result_dir_for_config(config: Path, override: Path | None) -> Path:
    if override:
        return override
    return config.resolve().parent / "backtest_results"


def latest_result_zip(results_dir: Path, started_at: float) -> Path:
    candidates = [
        path
        for path in results_dir.glob("backtest-result-*.zip")
        if path.stat().st_mtime >= started_at
    ]
    if not candidates:
        raise FileNotFoundError(f"No backtest result zip found in {results_dir}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def load_strategy_result(path: Path, strategy: str | None) -> tuple[str, dict[str, Any]]:
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


def metric(result: dict[str, Any], key: str, default: Any = None) -> Any:
    return result.get(key, default)


def summarize_window(
    window: Window,
    strategy: str,
    result_path: Path,
    result: dict[str, Any],
    seconds: float,
) -> dict[str, Any]:
    return {
        "timerange": window.timerange,
        "strategy": strategy,
        "result_file": str(result_path),
        "seconds": round(seconds, 2),
        "backtest_start": metric(result, "backtest_start"),
        "backtest_end": metric(result, "backtest_end"),
        "backtest_days": metric(result, "backtest_days"),
        "total_trades": metric(result, "total_trades", 0),
        "trades_per_day": metric(result, "trades_per_day"),
        "profit_total": metric(result, "profit_total", 0.0),
        "profit_total_pct": round(float(metric(result, "profit_total", 0.0)) * 100, 4),
        "profit_total_abs": metric(result, "profit_total_abs", 0.0),
        "cagr": metric(result, "cagr"),
        "profit_factor": metric(result, "profit_factor"),
        "winrate": metric(result, "winrate"),
        "winrate_pct": round(float(metric(result, "winrate", 0.0)) * 100, 4),
        "max_drawdown_account": metric(result, "max_drawdown_account"),
        "max_drawdown_pct": round(float(metric(result, "max_drawdown_account", 0.0)) * 100, 4),
        "trade_count_long": metric(result, "trade_count_long", 0),
        "trade_count_short": metric(result, "trade_count_short", 0),
        "market_change": metric(result, "market_change"),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    compounded = 1.0
    for row in rows:
        compounded *= 1.0 + float(row.get("profit_total") or 0.0)

    total_trades = sum(int(row.get("total_trades") or 0) for row in rows)
    total_days = sum(float(row.get("backtest_days") or 0.0) for row in rows)
    profit_abs = sum(float(row.get("profit_total_abs") or 0.0) for row in rows)
    positive_windows = sum(1 for row in rows if float(row.get("profit_total") or 0.0) > 0)
    negative_windows = sum(1 for row in rows if float(row.get("profit_total") or 0.0) < 0)
    no_trade_windows = sum(1 for row in rows if int(row.get("total_trades") or 0) == 0)
    worst_window = min(rows, key=lambda row: float(row.get("profit_total") or 0.0), default=None)
    best_window = max(rows, key=lambda row: float(row.get("profit_total") or 0.0), default=None)
    max_dd = max(float(row.get("max_drawdown_account") or 0.0) for row in rows) if rows else 0.0

    return {
        "windows": len(rows),
        "positive_windows": positive_windows,
        "negative_windows": negative_windows,
        "no_trade_windows": no_trade_windows,
        "total_days": round(total_days, 2),
        "total_trades": total_trades,
        "trades_per_day": round(total_trades / total_days, 4) if total_days else 0.0,
        "sum_profit_total_abs": round(profit_abs, 4),
        "window_reset_compounded_profit": round(compounded - 1.0, 6),
        "window_reset_compounded_profit_pct": round((compounded - 1.0) * 100, 4),
        "max_window_drawdown": round(max_dd, 6),
        "max_window_drawdown_pct": round(max_dd * 100, 4),
        "best_window": best_window["timerange"] if best_window else None,
        "best_window_profit_pct": best_window["profit_total_pct"] if best_window else None,
        "worst_window": worst_window["timerange"] if worst_window else None,
        "worst_window_profit_pct": worst_window["profit_total_pct"] if worst_window else None,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def tail_file(path: Path, lines: int = 80) -> str:
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run split offline futures backtests.")
    parser.add_argument("-c", "--config", required=True, type=Path)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--start", required=True, help="Inclusive start date, YYYYMMDD.")
    parser.add_argument("--end", required=True, help="Exclusive end date, YYYYMMDD.")
    parser.add_argument("--months-per-window", type=int, default=1)
    parser.add_argument("--fee", type=float, default=0.0005)
    parser.add_argument("--cache", default="none")
    parser.add_argument("--export", default="trades")
    parser.add_argument("--results-dir", type=Path, default=None)
    parser.add_argument("--summary-dir", type=Path, default=Path("user_data/backtest_results/split"))
    parser.add_argument("--show-child-output", action="store_true")
    parser.add_argument("--no-timeframe-detail", action="store_true")
    parser.add_argument("--stop-on-failure", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    windows = build_windows(args.start, args.end, args.months_per_window)
    config = args.config
    results_dir = result_dir_for_config(config, args.results_dir)
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    basename = f"split-backtest-{args.strategy}-{args.start}-{args.end}-{stamp}"
    log_dir = args.summary_dir / "logs" / basename
    log_dir.mkdir(parents=True, exist_ok=True)

    for index, window in enumerate(windows, start=1):
        cmd = [
            sys.executable,
            "user_data/scripts/run_offline_futures_backtest.py",
            "-c",
            str(config),
            "--strategy",
            args.strategy,
            "--timerange",
            window.timerange,
            "--fee",
            str(args.fee),
            "--cache",
            args.cache,
            "--export",
            args.export,
        ]
        if args.no_timeframe_detail:
            cmd.append("--no-timeframe-detail")

        print(f"[{index}/{len(windows)}] running {window.timerange}", flush=True)
        started_at = time.time()
        log_path = log_dir / f"{window.timerange}.log"
        if args.show_child_output:
            completed = subprocess.run(cmd, text=True)
        else:
            with log_path.open("w", encoding="utf-8", errors="replace") as log_handle:
                completed = subprocess.run(
                    cmd,
                    text=True,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                )
        seconds = time.time() - started_at
        if completed.returncode != 0:
            failure = {
                "timerange": window.timerange,
                "returncode": completed.returncode,
                "seconds": round(seconds, 2),
                "log_file": str(log_path),
            }
            failures.append(failure)
            print(f"[{index}/{len(windows)}] failed {failure}", flush=True)
            if not args.show_child_output:
                print(tail_file(log_path), flush=True)
            if args.stop_on_failure:
                break
            continue

        result_path = latest_result_zip(results_dir, started_at)
        strategy, result = load_strategy_result(result_path, args.strategy)
        row = summarize_window(window, strategy, result_path, result, seconds)
        row["log_file"] = str(log_path)
        rows.append(row)
        print(
            "[{}/{}] done {} trades={} profit={:.2f}% dd={:.2f}%".format(
                index,
                len(windows),
                window.timerange,
                row["total_trades"],
                row["profit_total_pct"],
                row["max_drawdown_pct"],
            ),
            flush=True,
        )

    json_path = args.summary_dir / f"{basename}.json"
    csv_path = args.summary_dir / f"{basename}.csv"
    payload = {
        "config": str(config),
        "strategy": args.strategy,
        "start": args.start,
        "end": args.end,
        "months_per_window": args.months_per_window,
        "fee": args.fee,
        "aggregate": aggregate(rows),
        "windows": rows,
        "failures": failures,
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(csv_path, rows)

    print("summary_json," + str(json_path))
    print("summary_csv," + str(csv_path))
    print(json.dumps(payload["aggregate"], indent=2, ensure_ascii=False))

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
