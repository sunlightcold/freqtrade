"""
Run a Binance USDT futures backtest without loading markets from the Binance API.

This keeps strategy research reproducible in restricted networks where Binance
exchangeInfo requests timeout, while still using Freqtrade's native Backtesting engine.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from freqtrade.commands.arguments import Arguments
from freqtrade.commands.optimize_commands import setup_optimize_configuration
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting
from freqtrade.resolvers import ExchangeResolver


DEFAULT_PAIRS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "BNB/USDT:USDT",
    "XRP/USDT:USDT",
    "AVAX/USDT:USDT",
    "LINK/USDT:USDT",
    "MKR/USDT:USDT",
    "BCH/USDT:USDT",
    "TRX/USDT:USDT",
]

PRICE_TICKS = {
    "BTC": 0.01,
    "ETH": 0.01,
    "SOL": 0.01,
    "BNB": 0.01,
    "XRP": 0.0001,
    "DOGE": 0.00001,
    "ADA": 0.0001,
    "AVAX": 0.001,
    "LINK": 0.001,
    "LTC": 0.01,
    "MKR": 0.1,
    "BCH": 0.01,
    "TRX": 0.00001,
    "XLM": 0.00001,
    "APT": 0.0001,
    "COMP": 0.01,
    "ETC": 0.001,
    "XTZ": 0.0001,
    "AAVE": 0.01,
    "SUI": 0.0001,
    "OP": 0.0001,
    "NEAR": 0.001,
    "ICP": 0.001,
    "UNI": 0.001,
    "FET": 0.0001,
    "RUNE": 0.001,
    "DOT": 0.001,
    "ATOM": 0.001,
    "ARB": 0.0001,
    "FIL": 0.001,
    "INJ": 0.001,
    "ALGO": 0.0001,
    "HBAR": 0.00001,
    "GALA": 0.00001,
    "SAND": 0.0001,
    "MANA": 0.0001,
    "1000SHIB": 0.000001,
    "1000PEPE": 0.0000001,
}

AMOUNT_TICKS = {
    "BTC": 0.001,
    "ETH": 0.001,
    "SOL": 0.1,
    "BNB": 0.01,
    "XRP": 0.1,
    "DOGE": 1.0,
    "ADA": 1.0,
    "AVAX": 0.1,
    "LINK": 0.1,
    "LTC": 0.001,
    "MKR": 0.001,
    "BCH": 0.001,
    "TRX": 1.0,
    "XLM": 1.0,
    "APT": 0.1,
    "COMP": 0.001,
    "ETC": 0.01,
    "XTZ": 0.1,
    "AAVE": 0.01,
    "SUI": 0.1,
    "OP": 0.1,
    "NEAR": 0.1,
    "ICP": 0.01,
    "UNI": 0.1,
    "FET": 1.0,
    "RUNE": 0.1,
    "DOT": 0.1,
    "ATOM": 0.01,
    "ARB": 0.1,
    "FIL": 0.1,
    "INJ": 0.01,
    "ALGO": 1.0,
    "HBAR": 1.0,
    "GALA": 1.0,
    "SAND": 1.0,
    "MANA": 1.0,
    "1000SHIB": 1.0,
    "1000PEPE": 1.0,
}


def build_binance_usdt_futures_market(pair: str) -> dict:
    base = pair.split("/")[0]
    quote = "USDT"
    market_id = f"{base}{quote}"
    return {
        "id": market_id,
        "lowercaseId": market_id.lower(),
        "symbol": pair,
        "base": base,
        "quote": quote,
        "settle": quote,
        "baseId": base,
        "quoteId": quote,
        "settleId": quote,
        "type": "swap",
        "spot": False,
        "margin": False,
        "swap": True,
        "future": False,
        "option": False,
        "active": True,
        "contract": True,
        "linear": True,
        "inverse": False,
        "contractSize": 1.0,
        "expiry": None,
        "expiryDatetime": None,
        "strike": None,
        "optionType": None,
        "maker": 0.0002,
        "taker": 0.0005,
        "precision": {
            "amount": AMOUNT_TICKS.get(base, 0.001),
            "price": PRICE_TICKS.get(base, 0.01),
            "cost": None,
            "base": None,
            "quote": None,
        },
        "limits": {
            "leverage": {"min": 1.0, "max": 20.0},
            "amount": {"min": AMOUNT_TICKS.get(base, 0.001), "max": None},
            "price": {"min": PRICE_TICKS.get(base, 0.01), "max": None},
            "cost": {"min": 5.0, "max": None},
        },
        "info": {
            "symbol": market_id,
            "pair": market_id,
            "contractType": "PERPETUAL",
            "marginAsset": quote,
        },
    }


def inject_offline_markets(config: dict):
    exchange = ExchangeResolver.load_exchange(
        config,
        validate=False,
        load_leverage_tiers=False,
    )
    pairs = config["exchange"].get("pair_whitelist") or DEFAULT_PAIRS
    markets = {pair: build_binance_usdt_futures_market(pair) for pair in pairs}
    exchange._api.set_markets(markets)
    exchange._api_async.set_markets(markets)
    exchange._markets = markets
    exchange._last_markets_refresh = 1
    exchange.fill_leverage_tiers()
    return exchange


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline Binance futures backtesting.")
    parser.add_argument("-c", "--config", default="user_data/config_martingale.json")
    parser.add_argument("--strategy", default=None)
    parser.add_argument("--timerange", default="20230602-20260531")
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--timeframe-detail", default=None)
    parser.add_argument(
        "--no-timeframe-detail",
        action="store_true",
        help="Disable detail timeframe for faster broad universe screening.",
    )
    parser.add_argument(
        "--pairs",
        nargs="+",
        default=None,
        help="Optional pair whitelist overriding the config, e.g. BTC/USDT:USDT ETH/USDT:USDT.",
    )
    parser.add_argument("--stake-amount", default=None)
    parser.add_argument("--max-open-trades", type=int, default=None)
    parser.add_argument("--dry-run-wallet", default=None)
    parser.add_argument("--export", default="trades")
    parser.add_argument("--breakdown", nargs="+", default=["month", "year"])
    parser.add_argument("--cache", default="none")
    parser.add_argument(
        "--enable-protections",
        action="store_true",
        help="Enable strategy protections during backtesting.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cli_args = [
        "backtesting",
        "-c",
        str(Path(args.config)),
        "--timerange",
        args.timerange,
        "--export",
        args.export,
        "--cache",
        args.cache,
    ]
    if args.strategy:
        cli_args.extend(["--strategy", args.strategy])
    if args.timeframe:
        cli_args.extend(["--timeframe", args.timeframe])
    if not args.no_timeframe_detail and args.timeframe_detail:
        cli_args.extend(["--timeframe-detail", args.timeframe_detail])
    if args.stake_amount:
        cli_args.extend(["--stake-amount", args.stake_amount])
    if args.max_open_trades is not None:
        cli_args.extend(["--max-open-trades", str(args.max_open_trades)])
    if args.dry_run_wallet:
        cli_args.extend(["--dry-run-wallet", args.dry_run_wallet])
    if args.breakdown:
        cli_args.append("--breakdown")
        cli_args.extend(args.breakdown)
    if args.enable_protections:
        cli_args.append("--enable-protections")

    parsed = Arguments(cli_args).get_parsed_arg()
    config = setup_optimize_configuration(parsed, RunMode.BACKTEST)
    if args.pairs:
        config["exchange"]["pair_whitelist"] = args.pairs
    exchange = inject_offline_markets(config)
    backtesting = Backtesting(config, exchange=exchange)
    backtesting.start()


if __name__ == "__main__":
    main()
