"""
Fetch no-key market hotspot data for Stage-18 strategies.

The strategy reads the JSON cache written by this script.  External requests stay
outside the strategy process so a slow public API cannot block order handling.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_PAIRS = [
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

BINANCE_FAPI = "https://fapi.binance.com"
FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1&format=json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def request_json(url: str, timeout: float) -> object:
    request = Request(url, headers={"User-Agent": "stage18-hotspot-cache/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def pair_to_symbol(pair: str) -> str:
    return pair.split("/")[0].replace(":", "") + "USDT"


def load_pairs(config_path: Path | None) -> list[str]:
    if not config_path:
        return DEFAULT_PAIRS
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        pairs = config.get("exchange", {}).get("pair_whitelist") or []
        return list(dict.fromkeys(pairs)) or DEFAULT_PAIRS
    except (OSError, json.JSONDecodeError):
        return DEFAULT_PAIRS


def as_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values.items(), key=lambda item: item[1])
    if len(ordered) == 1 or ordered[0][1] == ordered[-1][1]:
        return {symbol: 0.5 for symbol in values}
    return {symbol: index / (len(ordered) - 1) for index, (symbol, _) in enumerate(ordered)}


def fetch_fear_greed(timeout: float, errors: list[str]) -> dict:
    try:
        payload = request_json(FEAR_GREED_URL, timeout)
        item = payload.get("data", [{}])[0] if isinstance(payload, dict) else {}
        value = int(as_float(item.get("value"), 50.0))
        classification = str(item.get("value_classification") or "Neutral")
        risk_off = value <= 20 or value >= 85
        return {
            "value": value,
            "classification": classification,
            "risk_score": clamp(abs(value - 50) / 50),
            "risk_off": risk_off,
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        errors.append(f"fear_greed: {exc}")
        return {
            "value": None,
            "classification": "Unavailable",
            "risk_score": 0.5,
            "risk_off": False,
        }


def fetch_binance_snapshot(symbols: set[str], timeout: float, errors: list[str]) -> dict[str, dict]:
    tickers: dict[str, dict] = {}
    funding: dict[str, float] = {}
    open_interest: dict[str, float] = {}

    try:
        payload = request_json(f"{BINANCE_FAPI}/fapi/v1/ticker/24hr", timeout)
        if isinstance(payload, list):
            tickers = {
                str(item.get("symbol")): item
                for item in payload
                if str(item.get("symbol")) in symbols
            }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        errors.append(f"binance_24hr: {exc}")

    try:
        payload = request_json(f"{BINANCE_FAPI}/fapi/v1/premiumIndex", timeout)
        if isinstance(payload, list):
            funding = {
                str(item.get("symbol")): as_float(item.get("lastFundingRate"))
                for item in payload
                if str(item.get("symbol")) in symbols
            }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        errors.append(f"binance_premium_index: {exc}")

    for symbol in symbols:
        try:
            payload = request_json(f"{BINANCE_FAPI}/fapi/v1/openInterest?symbol={symbol}", timeout)
            if isinstance(payload, dict):
                open_interest[symbol] = as_float(payload.get("openInterest"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            errors.append(f"binance_open_interest:{symbol}: {exc}")

    return {
        symbol: {
            "ticker": tickers.get(symbol, {}),
            "funding_rate": funding.get(symbol, 0.0),
            "open_interest": open_interest.get(symbol, 0.0),
        }
        for symbol in symbols
    }


def build_scores(pairs: list[str], timeout: float) -> dict:
    errors: list[str] = []
    generated_at = utc_now()
    symbols = {pair_to_symbol(pair) for pair in pairs}
    fear_greed = fetch_fear_greed(timeout, errors)
    snapshot = fetch_binance_snapshot(symbols, timeout, errors)

    quote_volumes = {
        symbol: as_float(item["ticker"].get("quoteVolume"))
        for symbol, item in snapshot.items()
    }
    open_interest_notional = {
        symbol: as_float(item["open_interest"]) * as_float(item["ticker"].get("lastPrice"))
        for symbol, item in snapshot.items()
    }
    volume_rank = percentile_ranks(quote_volumes)
    oi_rank = percentile_ranks(open_interest_notional)
    has_binance_ticker = any(value > 0 for value in quote_volumes.values())

    pair_scores: dict[str, dict] = {}
    for pair in pairs:
        symbol = pair_to_symbol(pair)
        item = snapshot.get(symbol, {})
        ticker = item.get("ticker", {})
        change_pct = as_float(ticker.get("priceChangePercent"))
        quote_volume = as_float(ticker.get("quoteVolume"))
        funding_rate = as_float(item.get("funding_rate"))
        if has_binance_ticker:
            abs_change_score = clamp(abs(change_pct) / 12.0)
            funding_score = clamp(abs(funding_rate) / 0.0015)
            hot_score = clamp(
                0.35 * volume_rank.get(symbol, 0.5)
                + 0.30 * abs_change_score
                + 0.20 * oi_rank.get(symbol, 0.5)
                + 0.15 * funding_score
            )
            risk_score = clamp(
                0.45 * clamp(abs(change_pct) / 18.0)
                + 0.30 * funding_score
                + 0.25 * fear_greed["risk_score"]
            )
            direction_bias = max(-1.0, min(1.0, change_pct / 10.0))
        else:
            funding_score = 0.0
            hot_score = 0.5
            risk_score = 0.5
            direction_bias = 0.0
        pair_scores[pair] = {
            "symbol": symbol,
            "hot_score": round(hot_score, 4),
            "risk_score": round(risk_score, 4),
            "direction_bias": round(direction_bias, 4),
            "price_change_pct_24h": round(change_pct, 4),
            "quote_volume_24h": round(quote_volume, 4),
            "volume_rank": round(volume_rank.get(symbol, 0.5), 4),
            "open_interest_notional_rank": round(oi_rank.get(symbol, 0.5), 4),
            "funding_rate": funding_rate,
            "funding_score": round(funding_score, 4),
            "asof": generated_at,
        }

    degraded = bool(errors) or not has_binance_ticker
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "degraded": degraded,
        "source_errors": errors[:20],
        "global": {
            "fear_greed": fear_greed,
            "risk_off": bool(fear_greed["risk_off"]),
            "market_hot_score": round(
                sum(score["hot_score"] for score in pair_scores.values()) / max(len(pair_scores), 1),
                4,
            ),
        },
        "pairs": pair_scores,
    }


def write_cache(output: Path, payload: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Stage-18 no-key hotspot cache.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("user_data/hotspot/stage18_hotspot_cache.json"),
    )
    parser.add_argument("--interval-seconds", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=8.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pairs = load_pairs(args.config)
    while True:
        payload = build_scores(pairs, args.timeout)
        write_cache(args.output, payload)
        print(
            f"{payload['generated_at']} wrote {args.output} "
            f"pairs={len(payload['pairs'])} degraded={payload['degraded']}",
            flush=True,
        )
        if args.interval_seconds <= 0:
            break
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
