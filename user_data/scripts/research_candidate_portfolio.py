"""
Build a coarse portfolio from fast-screener candidate CSV rows.

The fast screener ranks single candidate rules. This tool reloads the selected
candidate rules, regenerates trades, combines them chronologically, and scores
the portfolio with a configurable per-trade capital slot.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

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


def parse_value(raw: str):
    try:
        value = float(raw)
    except ValueError:
        return raw
    if value.is_integer():
        return int(value)
    return value


def parse_params(raw: str) -> dict:
    params = {}
    if not raw:
        return params
    for item in raw.split(","):
        key, _, value = item.partition("=")
        params[key] = parse_value(value)
    return params


def read_candidates(path: Path) -> pd.DataFrame:
    dataframe = pd.read_csv(path)
    numeric_columns = [
        "rank",
        "hold",
        "tp",
        "sl",
        "trades",
        "trades_per_day",
        "total_profit",
        "daily",
        "min_slice_daily",
        "positive_slices",
        "max_dd",
        "robust_score",
    ]
    for column in numeric_columns:
        if column in dataframe:
            dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")
    return dataframe


def dedupe_candidates(dataframe: pd.DataFrame, max_per_pair: int) -> pd.DataFrame:
    dataframe = dataframe.copy()
    dataframe["dedupe_key"] = dataframe.apply(
        lambda row: (
            row["scope"],
            row["template"],
            row["side"],
            row.get("regime", "any"),
            row["hold"],
        ),
        axis=1,
    )
    dataframe = (
        dataframe.sort_values(["daily", "min_slice_daily"], ascending=False)
        .drop_duplicates("dedupe_key")
        .drop(columns=["dedupe_key"])
    )
    if max_per_pair <= 0:
        return dataframe
    return dataframe.groupby("scope", group_keys=False).head(max_per_pair)


def selected_rows(args: argparse.Namespace) -> pd.DataFrame:
    dataframe = read_candidates(Path(args.candidate_file))
    dataframe = dataframe[
        (dataframe["positive_slices"] >= args.min_positive_slices)
        & (dataframe["min_slice_daily"] >= args.min_slice_daily)
        & (dataframe["daily"] >= args.min_daily)
        & (dataframe["trades_per_day"] >= args.min_trades_per_day)
        & (dataframe["max_dd"] <= args.max_dd)
    ]
    dataframe = dedupe_candidates(dataframe, args.max_per_pair)
    dataframe = dataframe.sort_values(args.sort_by, ascending=False).head(args.top)
    return dataframe.reset_index(drop=True)


def slice_scores(trades: pd.DataFrame) -> dict[str, dict]:
    scores = {}
    for name, (start, end) in SLICES.items():
        dates = pd.to_datetime(trades["date"], utc=True)
        sliced = trades[
            (dates >= pd.Timestamp(start, tz="UTC"))
            & (dates <= pd.Timestamp(end, tz="UTC"))
        ]
        scores[name] = score_trades(sliced)
    return scores


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


def build_trades(args: argparse.Namespace, rows: pd.DataFrame) -> pd.DataFrame:
    data_dir = Path(args.data_dir)
    needs_market = rows["regime"].astype(str).str.startswith("market_").any()
    market_dataframe = (
        load_prepared_pair(data_dir, "BTC", args.timeframe, args.timerange)
        if needs_market
        else None
    )
    data_cache: dict[str, pd.DataFrame] = {}
    all_trades = []

    for index, row in rows.iterrows():
        pair = row["scope"]
        if pair not in data_cache:
            data_cache[pair] = load_pair_with_regime(
                data_dir,
                pair,
                args.timeframe,
                args.timerange,
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
            continue

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
            continue

        candidate_id = (
            f"{args.timeframe}:{pair}:{candidate.template}:"
            f"{candidate.side}:{candidate.regime}:h{hold}:#{index + 1}"
        )
        trades["raw_profit"] = trades["profit"]
        trades["profit"] = trades["profit"] * args.slot_fraction
        trades["pair"] = pair
        trades["candidate_id"] = candidate_id
        trades["template"] = candidate.template
        trades["side"] = candidate.side
        trades["regime"] = candidate.regime
        trades["hold"] = hold
        all_trades.append(trades)

    if not all_trades:
        return pd.DataFrame(columns=["date", "profit", "candidate_id", "pair"])
    return pd.concat(all_trades, ignore_index=True).sort_values("date")


def print_score(name: str, score: dict) -> None:
    print(
        f"{name},trades={score['trades']},profit={score['profit']:.4f},"
        f"daily={score['daily']:.5f},tpd={score['trades_per_day']:.3f},"
        f"winrate={score['winrate']:.4f},pf={score['pf']:.3f},"
        f"max_dd={score['max_dd']:.4f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Score a portfolio of screener candidates.")
    parser.add_argument("--candidate-file", required=True)
    parser.add_argument("--data-dir", default="user_data/data")
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--timerange", default=None)
    parser.add_argument("--top", type=int, default=12)
    parser.add_argument("--max-per-pair", type=int, default=2)
    parser.add_argument("--sort-by", default="daily")
    parser.add_argument("--min-positive-slices", type=int, default=3)
    parser.add_argument("--min-daily", type=float, default=0.0)
    parser.add_argument("--min-slice-daily", type=float, default=0.0)
    parser.add_argument("--min-trades-per-day", type=float, default=0.03)
    parser.add_argument("--max-dd", type=float, default=0.75)
    parser.add_argument("--min-signals", type=int, default=20)
    parser.add_argument("--fee", type=float, default=0.0005)
    parser.add_argument("--leverage", type=float, default=4.0)
    parser.add_argument("--slot-fraction", type=float, default=0.125)
    parser.add_argument("--export-trades", default=None)
    parser.add_argument("--export-selected", default=None)
    args = parser.parse_args()

    rows = selected_rows(args)
    if args.export_selected:
        rows.to_csv(args.export_selected, index=False)

    print("selected_candidates")
    for index, row in rows.iterrows():
        print(
            f"{index + 1},{row['scope']},{row['template']},{row['side']},"
            f"{row.get('regime', 'any')},hold={int(row['hold'])},"
            f"daily={row['daily']:.5f},min_daily={row['min_slice_daily']:.5f},"
            f"tpd={row['trades_per_day']:.3f},dd={row['max_dd']:.4f}"
        )

    trades = build_trades(args, rows)
    if args.export_trades:
        trades.to_csv(args.export_trades, index=False)

    print("portfolio_scores")
    total = score_trades(trades)
    print_score("total", total)
    for name, score in slice_scores(trades).items():
        print_score(name, score)

    print("candidate_scores")
    for candidate_id, group in trades.groupby("candidate_id"):
        print_score(candidate_id, score_trades(group))


if __name__ == "__main__":
    main()
