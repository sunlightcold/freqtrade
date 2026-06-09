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

## 2026-06-09 Direction Study

Backtests used Binance futures local data from 2023-06-02 to 2026-05-31 with
`15m` signals and `1m` detail data. The first full 20-pair split showed that
blindly trading every direction is not attractive:

| Slice | Strategy | Total return | CAGR | Max drawdown | Profit factor |
| --- | --- | ---: | ---: | ---: | ---: |
| Long all 20 | `Intp20LongOnlyDcaStrategy` | 24.78% | 7.70% | 41.13% | 1.11 |
| Short all 20 | `Intp20ShortOnlyDcaStrategy` | -21.39% | -7.74% | 27.35% | 0.84 |

The focused split keeps only the positive-expectancy side groups found in the
first pass:

| Slice | Strategy | Total return | CAGR | Max drawdown | Profit factor |
| --- | --- | ---: | ---: | ---: | ---: |
| Long focus | `Intp20LongFocusDcaStrategy` | 101.20% | 26.38% | 5.09% | 2.99 |
| Short focus | `Intp20ShortFocusDcaStrategy` | 29.08% | 8.92% | 8.07% | 1.85 |

Focused long pool:

- `AVAX`, `LTC`, `SOL`, `XLM`, `DOGE`, `MKR`, `XTZ`, `ETH`, `APT`, `BTC`, `ETC`

Focused short pool:

- `DOGE`, `BCH`, `XRP`, `APT`, `XTZ`

These results support a two-subaccount Binance setup: run the long focus strategy
on the long subaccount, and the short focus strategy on the short subaccount. It
does not justify trading every one of the 20 pairs on both sides.

## 2026-06-09 Walk-Forward Check

To reduce data-fitting risk, the study was split into:

- Training: 2023-06-02 to 2024-12-31.
- Validation: 2025-01-01 to 2025-12-31.
- Holdout test: 2026-01-01 to 2026-05-31.

The first walk-forward rule selected pairs that were positive in training, then
tested those selected pairs out of sample. This exposed weak generalization:

| Slice | Selection rule | Validation return | Validation DD | Test return | Test DD |
| --- | --- | ---: | ---: | ---: | ---: |
| Long | Positive in training only | 3.93% | 16.79% | 10.20% | 0.00% |
| Short | Positive in training only | -25.37% | 31.44% | 4.55% | 12.20% |

The stricter rule requires positive contribution in both training and validation
before testing on 2026 holdout data:

| Slice | Strategy | Training return | Validation return | Holdout return | Holdout DD |
| --- | --- | ---: | ---: | ---: | ---: |
| Long robust | `Intp20LongRobustDcaStrategy` | 44.44% | 25.63% | 6.25% | 0.00% |
| Short robust | `Intp20ShortRobustDcaStrategy` | 3.25% | 18.58% | -0.03% | 7.28% |

Robust long pool:

- `AVAX`, `BTC`, `DOGE`, `ETC`, `ETH`, `LTC`, `MKR`, `XLM`

Robust short pool:

- `AAVE`, `BCH`, `COMP`, `DOGE`, `TRX`, `XTZ`

Interpretation:

- The long side still has research value after walk-forward filtering.
- The short side is not strong enough as a standalone return engine; use it only
  as a small hedge candidate until live/dry-run evidence improves.
- The earlier focus pools are higher-return in-sample candidates, but the robust
  pools are the cleaner anti-overfit candidates.

## 2026-06-09 Moonshot CAGR Study

The 200% CAGR target was tested as a high-risk research objective, not as a
deployable promise. The useful retained candidates are:

| Slice | Strategy | Full return | CAGR | Max drawdown | Profit factor |
| --- | --- | ---: | ---: | ---: | ---: |
| Long moonshot | `Intp20LongMoonshotDcaStrategy` | 205.58% | 45.36% | 24.27% | 1.66 |
| Short moonshot | `Intp20ShortMoonshotDcaStrategy` | 81.60% | 22.11% | 16.59% | 1.83 |

Walk-forward check for the long moonshot profile:

| Window | Return | CAGR | Max drawdown | Trades | Profit factor |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2023-06-02..2024-12-31 | 119.39% | 64.81% | 24.05% | 162 | 1.61 |
| 2025-01-01..2025-12-31 | 38.62% | 38.74% | 15.75% | 79 | 1.33 |
| 2026-01-01..2026-05-31 | 34.96% | 107.41% | 0.00% | 20 | 0.00 |

Walk-forward check for the short moonshot profile:

| Window | Return | CAGR | Max drawdown | Trades | Profit factor |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2023-06-02..2024-12-31 | 27.14% | 16.50% | 16.59% | 45 | 1.58 |
| 2025-01-01..2025-12-31 | 22.33% | 22.39% | 14.50% | 45 | 1.44 |
| 2026-01-01..2026-05-31 | 18.65% | 51.60% | 0.00% | 11 | 0.00 |

Rejected experiments:

- `stake_amount=unlimited` with the DCA moonshot profile reduced effective
  average stake and produced only 24.12% full-period return.
- Full-wallet compounding at up to 20x leverage produced only 9.22% full-period
  return with 91.80% max drawdown.
- Using `1m` as the main timeframe on the best high-beta pairs lost 99.42% with
  99.57% max drawdown.
- Adding 15m momentum-continuation entries lost 29.51% and failed in the first
  month of the study.
- Raising fixed `stake_amount` above the wallet is rejected by Freqtrade; using
  the legal 10000 USDT maximum left too little available margin after early
  losses and finished at -7.80%.

Conclusion: the best reproducible moonshot candidate did not reach 200% CAGR.
The long moonshot profile is a higher-return, higher-drawdown research variant,
but the tested path to 200% CAGR required either near-account-death drawdowns or
failed outright. Treat 200% CAGR as an unproven target that needs a materially
different signal engine, not just more leverage.

## 2026-06-09 Nextgen Capital-Weighted Study

The next-stage study kept the moonshot long signal engine, then tested whether
capital allocation and pair pruning could improve return quality without losing
too much upside. The useful retained long candidate is:

| Slice | Strategy | Pair pool | Stake | Full return | CAGR | Max drawdown | Profit factor |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Long nextgen reliable | `Intp20LongNextGenWeightedDcaStrategy` | `MKR`, `AVAX`, `LTC`, `DOGE`, `BTC`, `XLM` | 9900 | 232.64% | 49.55% | 16.58% | 3.22 |

Rejected or secondary long variants:

| Variant | Change | Full return | CAGR | Max drawdown | Profit factor | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Top7 weighted | Adds `SOL` | 236.80% | 50.17% | 20.76% | 2.50 | Secondary: higher return, weaker risk quality |
| Top6 no XLM | Keeps `SOL`, removes `XLM` | 228.12% | 48.87% | 20.35% | 2.71 | Reject: worse than no-SOL top6 |
| Top5 weighted | Removes both `SOL` and `XLM` | 221.90% | 47.92% | 16.41% | 3.77 | Secondary: best PF, but lower return |
| Stake 10000 top7 | Max fixed stake | -0.43% | -0.14% | 15.92% | 0.98 | Reject: first loss stalls the bot |

The selected top6 preset drops `SOL`: it sacrifices about 4.16 percentage points
of full-period return versus top7, but improves max drawdown by 4.18 percentage
points and improves profit factor from 2.50 to 3.22.

The short-account next-stage preset is:

| Slice | Strategy | Pair pool | Stake | Full return | CAGR | Max drawdown | Profit factor |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Short risk-adjusted | `Intp20ShortRiskAdjustedDcaStrategy` | `DOGE`, `BCH`, `XRP`, `APT` | 8500 | 73.22% | 20.20% | 12.76% | 2.14 |

Rejected short variants:

- `stake_amount=9000` stopped after the first DOGE stoploss and ended at
  -14.95%.
- A pair-weighted short variant at `stake_amount=8500` returned only 73.27% and
  worsened max drawdown to 14.35%, so it was not retained.

Deployment interpretation:

- Use `config_binance_20pair_long_nextgen_weighted.json` as the default long
  subaccount research preset.
- Use `config_binance_20pair_short_risk_adjusted.json` as the short hedge preset.
- These are still research profiles. The long side is the real return engine;
  the short side remains a modest hedge engine and should not be sized as if it
  has the same expectancy as the long side.
