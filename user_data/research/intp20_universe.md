# INTP20 Futures Research Universe

This universe is the first-pass research pool for dual-account Binance futures
experiments. The selection is intentionally mechanical: pairs must have complete
local Binance futures data for `1m`, `15m`, and `1h` over the 2023-06-02 to
2026-05-31 study window, then pass a liquidity/volatility/trend screen.

The goal is not to declare these pairs permanently superior. It is to start from
a falsifiable, reproducible set before splitting long-only and short-only bots
across two Binance subaccounts.

## Selected Pairs

| Rank | Pair | Research role |
| ---: | --- | --- |
| 1 | SOL/USDT:USDT | High-liquidity, high-trend beta |
| 2 | BTC/USDT:USDT | Benchmark liquidity and market regime anchor |
| 3 | ETH/USDT:USDT | Benchmark liquidity and alt-market regime anchor |
| 4 | XRP/USDT:USDT | High-liquidity momentum/mean-reversion candidate |
| 5 | DOGE/USDT:USDT | High-volatility retail beta |
| 6 | BNB/USDT:USDT | Large-cap exchange-token beta |
| 7 | SUI/USDT:USDT | High-volatility newer large-cap beta |
| 8 | BCH/USDT:USDT | High-trend legacy beta |
| 9 | TRX/USDT:USDT | Low-volatility trend candidate |
| 10 | OP/USDT:USDT | High-volatility L2 beta |
| 11 | AVAX/USDT:USDT | High-volatility L1 beta |
| 12 | LINK/USDT:USDT | Liquid oracle beta |
| 13 | APT/USDT:USDT | High-volatility L1 beta |
| 14 | XLM/USDT:USDT | Legacy momentum candidate |
| 15 | LTC/USDT:USDT | Legacy high-liquidity beta |
| 16 | AAVE/USDT:USDT | DeFi beta |
| 17 | MKR/USDT:USDT | DeFi beta with strong trend history |
| 18 | ETC/USDT:USDT | Legacy beta |
| 19 | COMP/USDT:USDT | DeFi beta, lower liquidity |
| 20 | XTZ/USDT:USDT | Lower-liquidity mean-reversion candidate |

## Screen Metrics

The screen used local `1h` candles to rank complete-data candidates:

- `coverage`: data completeness across the study window.
- `median_quote_vol`: median `close * volume`, used as the liquidity proxy.
- `realized_vol`: annualized realized volatility from 1h returns.
- `atr_proxy`: median `(high - low) / close`, used as tradable movement proxy.
- `trend_abs`: absolute start-to-end move over the study window.

All selected pairs had complete `1m`, `15m`, and `1h` local futures data for the
study window. The 10 other downloaded 15m candidates are intentionally excluded
from this first-pass pool until matching `1m` and `1h` data is available.

## Dual-Account Use

Binance futures through Freqtrade requires one-way position mode for a single
account, so true same-pair hedge exposure should be implemented as two bots:

- Long bot on Binance subaccount A.
- Short bot on Binance subaccount B.

Both bots can use this same pair universe, but they should write to separate
SQLite databases and expose different API ports.
