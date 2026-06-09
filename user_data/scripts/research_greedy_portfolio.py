"""
Greedy portfolio builder for high-frequency candidate research.

The fast screener ranks one rule at a time. This tool rebuilds each selected
candidate's trades, then adds candidates only when the combined portfolio score
improves. It is still a coarse research model and every result must be checked
with native Freqtrade backtests before being treated as usable.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from research_candidate_portfolio import parse_params, read_candidates
from research_fast_screener import (
    Candidate,
    SLICES,
    attach_market_regime,
    load_prepared_pair,
    score_trades,
    signals_for,
    simulate,
    simulate_fixed_hold,
)


NUMERIC_COLUMNS = [
    "rank",
    "hold",
    "tp",
    "sl",
    "trades",
    "trades_per_day",
    "total_profit",
    "daily",
    "min_slice_daily",
    "min_slice_trades_per_day",
    "positive_slices",
    "max_dd",
    "robust_score",
]


def slice_trades(trades: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    if trades.empty:
        return trades
    dates = pd.to_datetime(trades["date"], utc=True)
    return trades[
        (dates >= pd.Timestamp(start, tz="UTC"))
        & (dates <= pd.Timestamp(end, tz="UTC"))
    ]


def portfolio_scores(trades: pd.DataFrame) -> tuple[dict, dict[str, dict]]:
    trades = trades.sort_values("date") if not trades.empty else trades
    total = score_trades(trades)
    slices = {
        name: score_trades(slice_trades(trades, start, end))
        for name, (start, end) in SLICES.items()
    }
    active_slices = [score for score in slices.values() if score["trades"] > 0]
    slice_dailies = [score["daily"] for score in slices.values()]
    slice_profits = [score["profit"] for score in slices.values()]
    total["min_slice_daily"] = float(min(slice_dailies))
    total["min_slice_profit"] = float(min(slice_profits))
    total["min_slice_trades_per_day"] = float(
        min(score["trades_per_day"] for score in active_slices)
        if active_slices
        else 0.0
    )
    total["positive_slices"] = int(sum(score["profit"] > 0 for score in slices.values()))
    return total, slices


def objective(score: dict, args: argparse.Namespace) -> float:
    daily_shortfall = max(0.0, args.target_daily - score["daily"])
    min_daily_shortfall = max(0.0, args.target_daily - score["min_slice_daily"])
    tpd_shortfall = max(0.0, args.target_trades_per_day - score["trades_per_day"])
    min_tpd_shortfall = max(0.0, args.min_slice_trades_per_day - score["min_slice_trades_per_day"])
    return (
        score["daily"] * args.daily_weight
        + score["min_slice_daily"] * args.min_daily_weight
        + score["profit"] * args.profit_weight
        + score["min_slice_profit"] * args.min_profit_weight
        + min(score["trades_per_day"], args.tpd_cap) * args.tpd_weight
        + score["positive_slices"] * args.positive_slice_weight
        - score["max_dd"] * args.dd_weight
        - daily_shortfall * args.daily_shortfall_weight
        - min_daily_shortfall * args.min_daily_shortfall_weight
        - tpd_shortfall * args.tpd_shortfall_weight
        - min_tpd_shortfall * args.min_tpd_shortfall_weight
    )


def candidate_key(row: pd.Series) -> str:
    return "|".join(
        str(row.get(column, ""))
        for column in (
            "scope",
            "template",
            "side",
            "regime",
            "hold",
            "tp",
            "sl",
            "params",
        )
    )


def read_candidate_files(paths: list[str], limit_per_file: int, sort_by: str) -> pd.DataFrame:
    frames = []
    for path in paths:
        frame = read_candidates(Path(path))
        for column in NUMERIC_COLUMNS:
            if column in frame:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame["source_file"] = Path(path).name
        frame = frame.sort_values(sort_by, ascending=False).head(limit_per_file)
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    dataframe = pd.concat(frames, ignore_index=True)
    dataframe["candidate_key"] = dataframe.apply(candidate_key, axis=1)
    return dataframe.drop_duplicates("candidate_key").reset_index(drop=True)


def filter_candidates(dataframe: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    filtered = dataframe.copy()
    filtered = filtered[
        (filtered["positive_slices"] >= args.min_positive_slices)
        & (filtered["daily"] >= args.min_candidate_daily)
        & (filtered["min_slice_daily"] >= args.min_candidate_slice_daily)
        & (filtered["trades_per_day"] >= args.min_candidate_trades_per_day)
        & (filtered["max_dd"] <= args.max_candidate_dd)
    ]
    filtered = filtered.sort_values(args.sort_by, ascending=False)
    if args.candidate_pool > 0:
        filtered = filtered.head(args.candidate_pool)
    return filtered.reset_index(drop=True)


def load_pair_with_regime(
    data_dir: Path,
    pair: str,
    timeframe: str,
    timerange: str | None,
    market_dataframe: pd.DataFrame | None,
) -> pd.DataFrame:
    dataframe = (
        market_dataframe.copy()
        if pair == "BTC" and market_dataframe is not None
        else load_prepared_pair(data_dir, pair, timeframe, timerange)
    )
    pair_data = {pair: dataframe}
    if market_dataframe is not None and pair != "BTC":
        pair_data["BTC"] = market_dataframe
    attach_market_regime(pair_data)
    return dataframe


def build_candidate_trades(
    row: pd.Series,
    data_cache: dict[str, pd.DataFrame],
    data_dir: Path,
    timeframe: str,
    timerange: str | None,
    market_dataframe: pd.DataFrame | None,
    args: argparse.Namespace,
) -> pd.DataFrame:
    pair = row["scope"]
    if pair not in data_cache:
        data_cache[pair] = load_pair_with_regime(
            data_dir,
            pair,
            timeframe,
            timerange,
            market_dataframe,
        )

    candidate = Candidate(
        template=row["template"],
        side=row["side"],
        params=parse_params(row["params"]),
        regime=row.get("regime", "any"),
    )
    dataframe = data_cache[pair]
    signals = signals_for(candidate, dataframe)
    if int(signals.sum()) < args.min_signals:
        return pd.DataFrame()

    hold = int(row["hold"])
    tp = float(row.get("tp", 0.0) or 0.0)
    sl = float(row.get("sl", 0.0) or 0.0)
    if tp > 0 and sl > 0:
        trades = simulate(
            dataframe,
            signals,
            candidate.side,
            hold,
            tp,
            sl,
            args.fee,
            args.leverage,
        )
    else:
        trades = simulate_fixed_hold(
            dataframe,
            signals,
            candidate.side,
            hold,
            args.fee,
            args.leverage,
        )
    if trades.empty:
        return trades

    label = (
        f"{timeframe}:{pair}:{candidate.template}:{candidate.side}:"
        f"{candidate.regime}:h{hold}:tp{tp}:sl{sl}"
    )
    trades = trades.copy()
    trades["raw_profit"] = trades["profit"]
    trades["profit"] = trades["profit"] * args.slot_fraction
    trades["candidate_id"] = label
    trades["pair"] = pair
    trades["template"] = candidate.template
    trades["side"] = candidate.side
    trades["regime"] = candidate.regime
    trades["hold"] = hold
    trades["tp"] = tp
    trades["sl"] = sl
    return trades


def add_trades(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    if left.empty:
        return right.sort_values("date")
    if right.empty:
        return left.sort_values("date")
    return pd.concat([left, right], ignore_index=True).sort_values("date")


def pair_limit_ok(row: pd.Series, selected: pd.DataFrame, args: argparse.Namespace) -> bool:
    if selected.empty:
        return True
    same_pair = selected["scope"] == row["scope"]
    if args.max_per_pair > 0 and int(same_pair.sum()) >= args.max_per_pair:
        return False
    same_pair_side = same_pair & (selected["side"] == row["side"])
    if args.max_per_pair_side > 0 and int(same_pair_side.sum()) >= args.max_per_pair_side:
        return False
    return True


def greedy_select(candidates: pd.DataFrame, trades_by_key: dict[str, pd.DataFrame], args: argparse.Namespace):
    selected_rows = []
    selected_trades = pd.DataFrame()
    selected_frame = pd.DataFrame()
    score, slices = portfolio_scores(selected_trades)
    best_objective = objective(score, args)
    history = []

    while len(selected_rows) < args.max_candidates:
        best = None
        best_candidate_objective = best_objective
        best_candidate_score = None
        best_candidate_slices = None
        best_candidate_trades = None

        for _, row in candidates.iterrows():
            key = row["candidate_key"]
            if key in {item["candidate_key"] for item in selected_rows}:
                continue
            if not pair_limit_ok(row, selected_frame, args):
                continue

            trades = trades_by_key.get(key, pd.DataFrame())
            if trades.empty:
                continue
            combined = add_trades(selected_trades, trades)
            candidate_score, candidate_slices = portfolio_scores(combined)
            if candidate_score["positive_slices"] < args.min_portfolio_positive_slices:
                continue
            if candidate_score["max_dd"] > args.max_portfolio_dd:
                continue
            if candidate_score["min_slice_daily"] < args.min_portfolio_slice_daily:
                continue

            candidate_objective = objective(candidate_score, args)
            if candidate_objective > best_candidate_objective + args.min_objective_improvement:
                best = row
                best_candidate_objective = candidate_objective
                best_candidate_score = candidate_score
                best_candidate_slices = candidate_slices
                best_candidate_trades = combined

        if best is None:
            break

        selected_rows.append(best.to_dict())
        selected_frame = pd.DataFrame(selected_rows)
        selected_trades = best_candidate_trades
        best_objective = best_candidate_objective
        score = best_candidate_score
        slices = best_candidate_slices
        history.append(
            {
                "step": len(selected_rows),
                "objective": best_objective,
                "profit": score["profit"],
                "daily": score["daily"],
                "min_slice_daily": score["min_slice_daily"],
                "trades": score["trades"],
                "trades_per_day": score["trades_per_day"],
                "min_slice_trades_per_day": score["min_slice_trades_per_day"],
                "max_dd": score["max_dd"],
                "positive_slices": score["positive_slices"],
                "added": best["candidate_key"],
            }
        )

    return selected_frame, selected_trades, score, slices, pd.DataFrame(history)


def print_score(name: str, score: dict) -> None:
    print(
        f"{name},trades={score['trades']},profit={score['profit']:.4f},"
        f"daily={score['daily']:.5f},tpd={score['trades_per_day']:.3f},"
        f"winrate={score['winrate']:.4f},pf={score['pf']:.3f},"
        f"max_dd={score['max_dd']:.4f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Greedy portfolio selector.")
    parser.add_argument("--candidate-files", nargs="+", required=True)
    parser.add_argument("--data-dir", default="user_data/data")
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--timerange", default=None)
    parser.add_argument("--sort-by", default="robust_score")
    parser.add_argument("--limit-per-file", type=int, default=300)
    parser.add_argument("--candidate-pool", type=int, default=400)
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--max-per-pair", type=int, default=3)
    parser.add_argument("--max-per-pair-side", type=int, default=2)
    parser.add_argument("--min-positive-slices", type=int, default=2)
    parser.add_argument("--min-candidate-daily", type=float, default=-0.001)
    parser.add_argument("--min-candidate-slice-daily", type=float, default=-0.002)
    parser.add_argument("--min-candidate-trades-per-day", type=float, default=0.02)
    parser.add_argument("--max-candidate-dd", type=float, default=0.80)
    parser.add_argument("--min-signals", type=int, default=10)
    parser.add_argument("--fee", type=float, default=0.0005)
    parser.add_argument("--leverage", type=float, default=4.0)
    parser.add_argument("--slot-fraction", type=float, default=0.125)
    parser.add_argument("--target-daily", type=float, default=0.005)
    parser.add_argument("--target-trades-per-day", type=float, default=2.0)
    parser.add_argument("--min-slice-trades-per-day", type=float, default=0.30)
    parser.add_argument("--min-portfolio-positive-slices", type=int, default=3)
    parser.add_argument("--min-portfolio-slice-daily", type=float, default=0.0)
    parser.add_argument("--max-portfolio-dd", type=float, default=0.35)
    parser.add_argument("--min-objective-improvement", type=float, default=0.000001)
    parser.add_argument("--daily-weight", type=float, default=260.0)
    parser.add_argument("--min-daily-weight", type=float, default=420.0)
    parser.add_argument("--profit-weight", type=float, default=0.02)
    parser.add_argument("--min-profit-weight", type=float, default=0.20)
    parser.add_argument("--tpd-weight", type=float, default=0.030)
    parser.add_argument("--tpd-cap", type=float, default=8.0)
    parser.add_argument("--positive-slice-weight", type=float, default=0.20)
    parser.add_argument("--dd-weight", type=float, default=1.20)
    parser.add_argument("--daily-shortfall-weight", type=float, default=25.0)
    parser.add_argument("--min-daily-shortfall-weight", type=float, default=45.0)
    parser.add_argument("--tpd-shortfall-weight", type=float, default=0.03)
    parser.add_argument("--min-tpd-shortfall-weight", type=float, default=0.05)
    parser.add_argument("--export-selected", default=None)
    parser.add_argument("--export-trades", default=None)
    parser.add_argument("--export-history", default=None)
    args = parser.parse_args()

    raw_candidates = read_candidate_files(args.candidate_files, args.limit_per_file, args.sort_by)
    candidates = filter_candidates(raw_candidates, args)
    data_dir = Path(args.data_dir)
    needs_market = candidates["regime"].astype(str).str.startswith("market_").any()
    market_dataframe = (
        load_prepared_pair(data_dir, "BTC", args.timeframe, args.timerange)
        if needs_market
        else None
    )
    data_cache: dict[str, pd.DataFrame] = {}
    trades_by_key = {}

    for _, row in candidates.iterrows():
        trades_by_key[row["candidate_key"]] = build_candidate_trades(
            row,
            data_cache,
            data_dir,
            args.timeframe,
            args.timerange,
            market_dataframe,
            args,
        )

    selected, trades, score, slices, history = greedy_select(candidates, trades_by_key, args)

    if args.export_selected:
        selected.to_csv(args.export_selected, index=False)
    if args.export_trades:
        trades.to_csv(args.export_trades, index=False)
    if args.export_history:
        history.to_csv(args.export_history, index=False)

    print(f"candidate_pool,raw={len(raw_candidates)},filtered={len(candidates)},selected={len(selected)}")
    print("portfolio_scores")
    print_score("total", score)
    for name, slice_score in slices.items():
        print_score(name, slice_score)

    print("selected_candidates")
    for index, row in selected.iterrows():
        print(
            f"{index + 1},{row['scope']},{row['template']},{row['side']},"
            f"{row.get('regime', 'any')},hold={int(row['hold'])},"
            f"tp={float(row.get('tp', 0.0) or 0.0):.4f},"
            f"sl={float(row.get('sl', 0.0) or 0.0):.4f},"
            f"daily={float(row['daily']):.5f},"
            f"min_daily={float(row['min_slice_daily']):.5f},"
            f"tpd={float(row['trades_per_day']):.3f},"
            f"dd={float(row['max_dd']):.4f}"
        )

    if not history.empty:
        last = history.iloc[-1]
        print(
            "final,"
            f"objective={last['objective']:.6f},"
            f"daily={last['daily']:.5f},"
            f"min_daily={last['min_slice_daily']:.5f},"
            f"tpd={last['trades_per_day']:.3f},"
            f"min_tpd={last['min_slice_trades_per_day']:.3f},"
            f"dd={last['max_dd']:.4f}"
        )


if __name__ == "__main__":
    main()
