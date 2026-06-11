# Stage20 Adaptive Regime Newcoin

## Design

Stage20 keeps the Stage18/19 base stack and adds a causal online-learning layer for generic 1m new-coin/high-beta entries.  The layer uses only information available at the candle being evaluated: OHLCV regime quality, BTC market context, and rolling post-fee memory shifted by the configured holding horizon.

The current production profile is deliberately not pair/month fitted:

- Stage19 pair-prefix add-ons are disabled.
- Stage20 short-learning entries are observation-only because the short template was weak in both 2025 and 2026 windows.
- Stage20 pullback-learning entries are observation-only because the pull template stayed negative after the non-fitting filters.
- Stage20 momentum-long entries remain tradable, but confirmation, stake, leverage, and exit logic use the momentum family memory only, not a blended max that can borrow pullback statistics.
- No DCA, no martingale, no position adjustment.

## Simulation Profile

- Exchange: Binance USDT futures, isolated margin
- Timeframe: 1m
- Pairs: 38 static futures pairs
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
