from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path


STRATEGY = "Intp20Stage13LiquidExpansionStrategy"

WINDOWS = [
    ("2023H2", Path("user_data/backtest_results/backtest-result-2026-06-10_18-39-34.zip")),
    ("2024", Path("user_data/backtest_results/backtest-result-2026-06-10_18-35-40.zip")),
    ("2025", Path("user_data/backtest_results/backtest-result-2026-06-10_18-25-57.zip")),
    ("2026_01_05", Path("user_data/backtest_results/backtest-result-2026-06-10_18-29-04.zip")),
]


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


def row_float(row: dict, key: str) -> float:
    value = row.get(key, 0.0)
    return float(value or 0.0)


def row_int(row: dict, key: str) -> int:
    value = row.get(key, 0)
    return int(value or 0)


def pair_base(pair: str) -> str:
    return pair.split("/")[0]


def main() -> None:
    out_dir = Path("user_data/research")
    out_dir.mkdir(parents=True, exist_ok=True)

    pair_window_rows: list[dict] = []
    tag_window_rows: list[dict] = []
    portfolio_rows: list[dict] = []

    for window, path in WINDOWS:
        result = load_result(path)
        portfolio_rows.append(
            {
                "window": window,
                "backtest_start": result["backtest_start"],
                "backtest_end": result["backtest_end"],
                "starting_balance": result.get("starting_balance", ""),
                "final_balance": result.get("final_balance", ""),
                "total_trades": result.get("total_trades", 0),
                "profit_total_abs": result.get("profit_total_abs", 0.0),
                "profit_total_pct": result.get("profit_total", 0.0) * 100,
                "cagr_pct": result.get("cagr", 0.0) * 100,
                "profit_factor": result.get("profit_factor", 0.0),
                "max_drawdown_account_pct": result.get("max_drawdown_account", 0.0) * 100,
                "max_drawdown_abs": result.get("max_drawdown_abs", 0.0),
                "trade_count_long": result.get("trade_count_long", 0),
                "trade_count_short": result.get("trade_count_short", 0),
            }
        )

        stop_loss_by_tag: dict[str, int] = {}
        for row in result.get("exit_reason_summary", []):
            key = row.get("key", "")
            if key == "stop_loss":
                # Mixed tag stats contain the tag/stop_loss combination more reliably.
                continue

        for row in result.get("results_per_enter_tag", []):
            tag = row.get("key", "")
            if not tag or tag == "TOTAL":
                continue
            tag_window_rows.append(
                {
                    "window": window,
                    "tag": tag,
                    "trades": row_int(row, "trades"),
                    "profit_total_abs": row_float(row, "profit_total_abs"),
                    "profit_total_pct": row_float(row, "profit_total") * 100,
                    "profit_mean_pct": row_float(row, "profit_mean") * 100,
                    "wins": row_int(row, "wins"),
                    "losses": row_int(row, "losses"),
                    "winrate_pct": row_float(row, "winrate") * 100,
                    "profit_factor": row_float(row, "profit_factor"),
                }
            )

        for row in result.get("results_per_pair", []):
            pair = row.get("key", "")
            if not pair or pair == "TOTAL":
                continue
            pair_window_rows.append(
                {
                    "window": window,
                    "pair": pair,
                    "base": pair_base(pair),
                    "trades": row_int(row, "trades"),
                    "profit_total_abs": row_float(row, "profit_total_abs"),
                    "profit_total_pct": row_float(row, "profit_total") * 100,
                    "profit_mean_pct": row_float(row, "profit_mean") * 100,
                    "wins": row_int(row, "wins"),
                    "losses": row_int(row, "losses"),
                    "winrate_pct": row_float(row, "winrate") * 100,
                    "profit_factor": row_float(row, "profit_factor"),
                }
            )

    by_pair: dict[str, dict] = {}
    for row in pair_window_rows:
        item = by_pair.setdefault(
            row["pair"],
            {
                "pair": row["pair"],
                "base": row["base"],
                "main_profit_abs": 0.0,
                "main_trades": 0,
                "main_losing_windows": 0,
                "oos_2023h2_profit_abs": 0.0,
                "oos_2023h2_trades": 0,
            },
        )
        prefix = "oos_2023h2" if row["window"] == "2023H2" else row["window"]
        item[f"{prefix}_profit_abs"] = row["profit_total_abs"]
        item[f"{prefix}_profit_pct"] = row["profit_total_pct"]
        item[f"{prefix}_trades"] = row["trades"]
        if row["window"] == "2023H2":
            item["oos_2023h2_profit_abs"] = row["profit_total_abs"]
            item["oos_2023h2_trades"] = row["trades"]
        else:
            item["main_profit_abs"] += row["profit_total_abs"]
            item["main_trades"] += row["trades"]
            if row["profit_total_abs"] < 0:
                item["main_losing_windows"] += 1

    rank_rows = sorted(by_pair.values(), key=lambda x: x["main_profit_abs"], reverse=True)

    files = [
        (out_dir / "stage13_candidate_pair_window_matrix.csv", pair_window_rows),
        (out_dir / "stage13_candidate_tag_window_matrix.csv", tag_window_rows),
        (out_dir / "stage13_candidate_portfolio_windows.csv", portfolio_rows),
        (out_dir / "stage13_candidate_pair_rank.csv", rank_rows),
    ]
    for path, rows in files:
        if not rows:
            continue
        fieldnames = list(rows[0].keys())
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        print(path)


if __name__ == "__main__":
    main()
