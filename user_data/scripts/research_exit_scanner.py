"""
Local exit scanner for already-promising candidate rules.

This is the second stage after a coarse/greedy portfolio search: keep the entry
rules fixed, then rescore only their exit style, hold length, take-profit, and
stoploss combinations. It avoids exploding the full template grid again.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from research_candidate_portfolio import parse_params, read_candidates
from research_fast_screener import (
    Candidate,
    SLICES,
    add_robust_score,
    attach_market_regime,
    load_prepared_pair,
    result_to_row,
    score_trades,
    signals_for,
    simulate,
    simulate_fixed_hold,
)


def candidate_key(row: pd.Series) -> str:
    return "|".join(
        str(row.get(column, ""))
        for column in ("scope", "template", "side", "regime", "params")
    )


def dedupe_entries(dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe = dataframe.copy()
    dataframe["candidate_key"] = dataframe.apply(candidate_key, axis=1)
    return dataframe.drop_duplicates("candidate_key").reset_index(drop=True)


def slice_scores(trades: pd.DataFrame) -> dict[str, dict]:
    scores = {}
    for name, (start, end) in SLICES.items():
        if trades.empty:
            sliced = trades
        else:
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


def evaluate(
    dataframe: pd.DataFrame,
    row: pd.Series,
    signals: pd.Series,
    hold: int,
    tp: float,
    sl: float,
    args: argparse.Namespace,
) -> dict | None:
    candidate = Candidate(
        template=row["template"],
        side=row["side"],
        params=parse_params(row["params"]),
        regime=row.get("regime", "any"),
    )
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
        return None

    trades["pair"] = row["scope"]
    per_slice = slice_scores(trades)
    total = score_trades(trades)
    add_robust_score(total, per_slice)
    return {
        "candidate": candidate,
        "scope": row["scope"],
        "hold": hold,
        "tp": tp,
        "sl": sl,
        "total": total,
        "slices": per_slice,
    }


def scan_row(
    row: pd.Series,
    dataframe: pd.DataFrame,
    args: argparse.Namespace,
) -> list[dict]:
    candidate = Candidate(
        template=row["template"],
        side=row["side"],
        params=parse_params(row["params"]),
        regime=row.get("regime", "any"),
    )
    signals = signals_for(candidate, dataframe)
    if int(signals.sum()) < args.min_signals:
        return []

    results = []
    if args.include_fixed:
        for hold in args.holds:
            result = evaluate(dataframe, row, signals, hold, 0.0, 0.0, args)
            if result:
                results.append(result)

    if args.include_bracket:
        for hold in args.holds:
            for tp in args.tps:
                for sl in args.sls:
                    result = evaluate(dataframe, row, signals, hold, tp, sl, args)
                    if result:
                        results.append(result)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan exits for selected candidate entries.")
    parser.add_argument("--candidate-file", required=True)
    parser.add_argument("--data-dir", default="user_data/data")
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--timerange", default=None)
    parser.add_argument("--top", type=int, default=160)
    parser.add_argument("--sort-by", default="robust_score")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--fee", type=float, default=0.0005)
    parser.add_argument("--leverage", type=float, default=4.0)
    parser.add_argument("--min-signals", type=int, default=10)
    parser.add_argument("--holds", nargs="+", type=int, default=[6, 12, 24, 36])
    parser.add_argument("--tps", nargs="+", type=float, default=[0.005, 0.008, 0.012, 0.016])
    parser.add_argument("--sls", nargs="+", type=float, default=[0.005, 0.008, 0.012, 0.016])
    parser.add_argument("--include-fixed", action="store_true")
    parser.add_argument("--include-bracket", action="store_true")
    parser.add_argument("--export-csv", default=None)
    args = parser.parse_args()

    if not args.include_fixed and not args.include_bracket:
        args.include_fixed = True
        args.include_bracket = True

    rows = dedupe_entries(read_candidates(Path(args.candidate_file)))
    rows = rows.sort_values(args.sort_by, ascending=False)
    if args.limit > 0:
        rows = rows.head(args.limit)

    data_dir = Path(args.data_dir)
    needs_market = rows["regime"].astype(str).str.startswith("market_").any()
    market_dataframe = (
        load_prepared_pair(data_dir, "BTC", args.timeframe, args.timerange)
        if needs_market
        else None
    )
    data_cache: dict[str, pd.DataFrame] = {}
    results = []

    for _, row in rows.iterrows():
        pair = row["scope"]
        if pair not in data_cache:
            data_cache[pair] = load_pair_with_regime(
                data_dir,
                pair,
                args.timeframe,
                args.timerange,
                market_dataframe,
            )
        results.extend(scan_row(row, data_cache[pair], args))

    results.sort(key=lambda item: item["total"]["robust_score"], reverse=True)
    out_rows = [
        result_to_row(index, result, args.leverage)
        for index, result in enumerate(results[: args.top], 1)
    ]
    if args.export_csv:
        pd.DataFrame(out_rows).to_csv(args.export_csv, index=False)

    print(
        "rank,scope,template,side,hold,tp,sl,trades,tpd,total_profit,daily,"
        "min_daily,regime,min_tpd,positive_slices,winrate,pf,max_dd,score,params"
    )
    for row in out_rows:
        print(
            f"{row['rank']},{row['scope']},{row['template']},{row['side']},"
            f"{row['hold']},{row['tp']:.4f},{row['sl']:.4f},"
            f"{row['trades']},{row['trades_per_day']:.3f},"
            f"{row['total_profit']:.4f},{row['daily']:.5f},"
            f"{row['min_slice_daily']:.5f},{row['regime']},"
            f"{row['min_slice_trades_per_day']:.3f},"
            f"{row['positive_slices']},{row['winrate']:.4f},"
            f"{row['pf']:.3f},{row['max_dd']:.4f},"
            f"{row['robust_score']:.4f},{row['params']}"
        )


if __name__ == "__main__":
    main()
