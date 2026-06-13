"""
Download Binance USD-M futures OHLCV archives without loading Binance markets.

Freqtrade's regular ``download-data`` command must load exchange markets first.
In environments where ``exchangeInfo`` is blocked or times out, this script
downloads documented public archive files from data.binance.vision and stores
them in Freqtrade's normal feather format.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import aiohttp
import pandas as pd
from pandas import DataFrame

from freqtrade.constants import DEFAULT_DATAFRAME_COLUMNS
from freqtrade.data.history.datahandlers.featherdatahandler import FeatherDataHandler
from freqtrade.enums import CandleType
from freqtrade.exchange.binance_public_data import Http404, get_daily_ohlcv


logger = logging.getLogger(__name__)


def parse_timerange(timerange: str) -> tuple[date, date]:
    """
    Parse a Freqtrade-style timerange into [start, end) UTC dates.

    Examples:
      20260601-20260613 -> 2026-06-01 through 2026-06-12
      20260601-         -> 2026-06-01 through today UTC
    """
    if "-" not in timerange:
        raise SystemExit("--timerange must use Freqtrade format, e.g. 20260601-20260613")

    start_raw, end_raw = timerange.split("-", 1)
    if not start_raw:
        raise SystemExit("--timerange requires a start date, e.g. 20260601-")

    start = datetime.strptime(start_raw, "%Y%m%d").date()
    end = datetime.now(UTC).date() + timedelta(days=1)
    if end_raw:
        end = datetime.strptime(end_raw, "%Y%m%d").date()

    if end <= start:
        raise SystemExit(f"--timerange end must be after start: {timerange}")
    return start, end


def iter_dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current < end:
        yield current
        current += timedelta(days=1)


def normalize_pair(raw: str) -> str:
    value = raw.strip().upper()
    if not value:
        raise ValueError("empty pair")

    if "/" in value:
        base, rest = value.split("/", 1)
        quote = rest.split(":", 1)[0]
        if quote != "USDT":
            raise ValueError(f"Only USDT futures pairs are supported: {raw}")
        return f"{base}/USDT:USDT"

    if value.endswith("USDT"):
        value = value[:-4]
    return f"{value}/USDT:USDT"


def pair_to_binance_symbol(pair: str) -> str:
    base = normalize_pair(pair).split("/", 1)[0]
    return f"{base}USDT"


def pairs_from_config(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    pairs = data.get("exchange", {}).get("pair_whitelist") or []
    return [normalize_pair(pair) for pair in pairs]


def build_pairs(args: argparse.Namespace) -> list[str]:
    pairs: list[str] = []
    if args.config:
        pairs.extend(pairs_from_config(Path(args.config)))
    if args.pairs:
        pairs.extend(normalize_pair(pair) for pair in args.pairs)

    seen = set()
    unique_pairs = []
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            unique_pairs.append(pair)
    if not unique_pairs:
        raise SystemExit("Provide --pairs or --config with exchange.pair_whitelist")
    return unique_pairs


def normalize_ohlcv(df: DataFrame) -> DataFrame:
    if df.empty:
        return DataFrame(columns=DEFAULT_DATAFRAME_COLUMNS)

    df = df.loc[:, DEFAULT_DATAFRAME_COLUMNS].copy()
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.as_unit("ms")
    for column in ("open", "high", "low", "close", "volume"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates(subset=["date"], keep="last")
    return df.sort_values("date").reset_index(drop=True)


async def download_pair_timeframe(
    session: aiohttp.ClientSession,
    pair: str,
    timeframe: str,
    start: date,
    end: date,
    semaphore: asyncio.Semaphore,
    retries: int,
    retry_delay: float,
) -> tuple[DataFrame, int]:
    symbol = pair_to_binance_symbol(pair)

    async def fetch_day(day: date) -> DataFrame | None:
        async with semaphore:
            try:
                return await get_daily_ohlcv(
                    symbol,
                    timeframe,
                    CandleType.FUTURES,
                    day,
                    session,
                    retry_count=retries,
                    retry_delay=retry_delay,
                )
            except Http404:
                return None

    tasks = [asyncio.create_task(fetch_day(day)) for day in iter_dates(start, end)]
    frames: list[DataFrame] = []
    missing = 0
    for task in asyncio.as_completed(tasks):
        result = await task
        if result is None or result.empty:
            missing += 1
        else:
            frames.append(result)

    if not frames:
        return DataFrame(columns=DEFAULT_DATAFRAME_COLUMNS), missing
    return normalize_ohlcv(pd.concat(frames, ignore_index=True)), missing


def merge_with_existing(
    handler: FeatherDataHandler,
    pair: str,
    timeframe: str,
    downloaded: DataFrame,
    replace: bool,
) -> DataFrame:
    if replace:
        return normalize_ohlcv(downloaded)

    existing = handler._ohlcv_load(pair, timeframe, None, CandleType.FUTURES)
    if existing.empty:
        return normalize_ohlcv(downloaded)
    return normalize_ohlcv(pd.concat([existing, downloaded], ignore_index=True))


async def run(args: argparse.Namespace) -> None:
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    start, end = parse_timerange(args.timerange)
    pairs = build_pairs(args)
    userdir = Path(args.userdir)
    datadir = Path(args.datadir) if args.datadir else userdir / "data" / args.exchange
    handler = FeatherDataHandler(datadir)
    semaphore = asyncio.Semaphore(args.max_concurrency)

    print(
        f"Downloading {len(pairs)} pair(s), timeframes={','.join(args.timeframes)}, "
        f"range={start.isoformat()}..{end.isoformat()} exclusive, datadir={datadir}"
    )

    connector = aiohttp.TCPConnector(limit=args.max_concurrency)
    async with aiohttp.ClientSession(connector=connector, trust_env=True) as session:
        for pair in pairs:
            for timeframe in args.timeframes:
                downloaded, missing = await download_pair_timeframe(
                    session,
                    pair,
                    timeframe,
                    start,
                    end,
                    semaphore,
                    args.retries,
                    args.retry_delay,
                )
                if downloaded.empty:
                    print(f"{pair} {timeframe}: no archive data found, missing_days={missing}")
                    continue

                merged = merge_with_existing(handler, pair, timeframe, downloaded, args.replace)
                handler.ohlcv_store(pair, timeframe, merged, CandleType.FUTURES)
                first = merged.iloc[0]["date"].strftime("%Y-%m-%d %H:%M")
                last = merged.iloc[-1]["date"].strftime("%Y-%m-%d %H:%M")
                print(
                    f"{pair} {timeframe}: downloaded={len(downloaded)}, stored={len(merged)}, "
                    f"missing_days={missing}, first={first}, last={last}"
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Binance Vision USD-M futures OHLCV to Freqtrade feather files."
    )
    parser.add_argument("--userdir", default="user_data")
    parser.add_argument("--datadir", default=None)
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("-c", "--config", default=None)
    parser.add_argument("--pairs", nargs="+", default=None)
    parser.add_argument("--timeframes", nargs="+", default=["1m"])
    parser.add_argument("--timerange", required=True)
    parser.add_argument("--max-concurrency", type=int, default=8)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-delay", type=float, default=0.25)
    parser.add_argument("--replace", action="store_true", help="Replace existing local data.")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
