# Stage20 Adaptive Regime Newcoin

## 2026-06-15 Status

Rejected for the user's current adoption target. The current requirement is a
clearly high-frequency long/short strategy with stable annualized return above
100% under a 1000 USDT dry-run wallet and 0.05% one-side fee assumptions.

Latest 1000U replay for 2026-06-01..2026-06-12 produced 9 trades, about 0.9
trades/day, +0.33% total return, 12.92% CAGR, and 4.67 profit factor. It traded
both long and short, but the trade frequency and annualized return are not
acceptable for adoption.

## Design

Stage20 keeps the Stage18/19 base stack and adds a causal online-learning layer for generic 1m new-coin/high-beta entries.  The layer uses only information available at the candle being evaluated: OHLCV regime quality, BTC market context, and rolling post-fee memory shifted by the configured holding horizon.

The current production profile is deliberately not pair/month fitted:

- Stage19 pair-prefix add-ons are disabled.
- Stage20 production entries are narrowed to fast liquidity-sweep long/short signals.
- Wider pulse, vwap-reversion, and loose pullback experiments remain research-only because they were fee-sensitive or unstable in split-window checks.
- No DCA, no martingale, no position adjustment.

## Simulation Profile

- Exchange: Binance USDT futures, isolated margin
- Timeframe: 1m
- Pairs: expanded static futures pair set focused on new and high-beta contracts
- Local research config: `user_data/config_binance_stage20_adaptive_regime_newcoin_38pair_200u_dryrun.json`
- Server dry-run config: `server-deploy/user_data/config_binance_stage20_adaptive_regime_newcoin_38pair_1000u_dryrun.json`
- Server wallet/stake: 1000 USDT wallet, 90 USDT stake, max 10 open trades
- Fee: `0.0005`
- Funding rate in backtests: `0`

## Latest Backtests

All runs used `--fee 0.0005`, 1m data, no timeframe detail, and cache disabled.

| Window | Return | Trades | Profit factor | Max drawdown | Stage20 learned-entry contribution |
| --- | ---: | ---: | ---: | ---: | --- |
| 2026-05 | +7.41% | 73 | 1.8857 | 1.94% | `s20_momo_l`: +1.12%, 2 trades |
| 2026-01..05 | +55.61% | 436 | 1.9231 | 4.79% | `s20_momo_l`: -0.49%, 7 trades |
| 2025 full year | +136.12% | 1436 | 1.4763 | 9.56% | `s20_momo_l`: +6.69%, 49 trades |

2025 monthly profit was positive in ten of twelve months.  October and December were negative, so this is still a high-risk strategy despite the improved drawdown versus the earlier Stage20 draft.

## Operational Notes

Stage20 is intended for dry-run forward testing first.  The learning layer can still go quiet for long periods when the regime and memory filters do not promote a generic template.  Daily trade count is therefore not guaranteed; forcing daily trades would be a fitting/overtrading choice rather than a robust learning rule.

To deploy on the server, use the `server-deploy` README Stage20 section.  Do not upload files manually; update with `git pull --ff-only`, set `.env`, and restart with `docker compose --profile stage20 up -d`.
