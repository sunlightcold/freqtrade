# Stage 17 Adaptive Scalp Research

Date: 2026-06-11

Goal: improve the Stage-15 high-turnover 1m futures strategy for visible
short-term returns while explicitly testing fee/slippage sensitivity.

## 2026-06-15 Status

Rejected for the user's current adoption target. The current requirement is a
clearly high-frequency long/short strategy with stable annualized return above
100% under a 1000 USDT dry-run wallet and 0.05% one-side fee assumptions.

Latest 1000U replay for 2026-06-01..2026-06-12 produced 11 trades, about 1.1
trades/day, +0.14% total return, 5.08% CAGR, and 1.12 profit factor. That is a
short-cycle experimental scalp, not a qualifying high-frequency strategy.

## Implementation

New files:

- `user_data/strategies/Intp20Stage17AdaptiveScalpStrategy.py`
- `user_data/config_binance_stage17_turbo_adaptive_scalp_20pair_200u_dryrun.json`

Supporting tool change:

- `user_data/scripts/run_offline_futures_backtest.py` now supports `--fee`
  for one-side fee stress tests.

Strategy classes:

- `Intp20Stage17AdaptiveScalpStrategy`
- `Intp20Stage17TurboAdaptiveScalpStrategy`

Design:

- Inherits Stage-15 aggressive high-turnover scalp logic.
- Blocks only the two weak MKR added scalp streams:
  - `s15_06_mkr_vstretch_l_mc_h8m_l5`
  - `s15_07_mkr_maoff_s_ma_h5m_l5`
- Keeps APT because it is positive in the normal-cost walk-forward windows.
- Adds adaptive loss exits for short reversion tags that caused the 2026-05
  giveback:
  - `s13_02_dot_rsi_s_lc_h24_l4`
  - `s9_08_xtz_rsi_s_lc_h24_l4`
  - `s13_05_uni_rsi_s_lc_h24_l4`
  - `s9_16_ltc_vwap_s_lc_h18_l5`
- Turbo variant modestly boosts the strongest AAVE, OP, XRP, DOGE, and APT
  stress-surviving scalp tags.

## Backtest Comparison

All runs used 20 Binance USDT futures pairs, wallet 200 USDT, stake 18 USDT,
max open trades 10, isolated futures, no DCA/martingale.

Normal-cost runs use the offline Binance futures taker fee of 0.05% per side.
Stress-cost runs use `--fee 0.001`, equivalent to 0.10% per side.

| Window | Strategy | Fee/side | Return | Trades | Avg duration | Max DD | Profit factor |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-05 | Stage15 Aggressive | 0.05% | 3.18% | 69 | 1:37 | 3.10% | - |
| 2026-05 | Stage17 Turbo | 0.05% | 7.47% | 69 | 1:32 | 2.09% | 1.99 |
| 2026-05 | Stage15 Aggressive | 0.10% | 0.26% | 69 | 1:37 | 3.31% | 1.02 |
| 2026-05 | Stage17 Turbo | 0.10% | 4.86% | 69 | 1:32 | 2.58% | 1.57 |
| 2026-01..05 | Stage15 Aggressive | 0.05% | 54.87% | 427 | 1:31 | 3.58% | - |
| 2026-01..05 | Stage17 Turbo | 0.05% | 55.58% | 427 | 1:28 | 4.99% | 1.92 |
| 2026-01..05 | Stage15 Aggressive | 0.10% | 34.69% | 427 | 1:31 | 4.90% | 1.50 |
| 2026-01..05 | Stage17 Turbo | 0.10% | 35.06% | 427 | 1:28 | 5.86% | 1.51 |
| 2024 | Stage15 Aggressive | 0.05% | 138.87% | 1763 | 1:18 | 11.82% | 1.53 |
| 2024 | Stage17 Turbo | 0.05% | 133.96% | 1719 | 1:17 | 9.98% | 1.38 |
| 2024 | Stage15 Aggressive | 0.10% | 54.07% | 1763 | 1:18 | 30.53% | 1.14 |
| 2024 | Stage17 Turbo | 0.10% | 49.17% | 1719 | 1:16 | 27.60% | 1.13 |
| 2025 | Stage15 Aggressive | 0.05% | 142.37% | 1426 | 1:19 | 8.12% | 1.53 |
| 2025 | Stage17 Turbo | 0.05% | 142.99% | 1381 | 1:17 | 8.70% | 1.52 |
| 2025 | Stage15 Aggressive | 0.10% | 73.15% | 1426 | 1:19 | 13.58% | 1.24 |
| 2025 | Stage17 Turbo | 0.10% | 74.38% | 1381 | 1:16 | 14.13% | 1.24 |

## Decision

Stage17 Turbo is the better short-term dry-run candidate when the priority is
visible recent performance. It materially improved the 2026-05 month and stayed
positive under a 0.10% per-side cost stress.

Stage15 Aggressive remains slightly better for the 2024 normal-cost return and
slightly better for 2026 YTD drawdown. Stage17 is therefore not a strict
replacement in every regime; it is a more adaptive, higher short-term-return
candidate.

For live use, treat Stage17 Turbo as an aggressive dry-run candidate first.
Backtests still do not fully model funding, queue priority, partial fills,
latency, or skipped limit orders.
