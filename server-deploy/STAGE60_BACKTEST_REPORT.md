# Stage60 Blended Shock Backtest Report

## Decision

Stage60 passes the requested portfolio gates in three separate one-year native Freqtrade
backtests. It is approved for dry-run only. It is not approved for live money.

The pass criteria were:

- Binance USDT perpetual futures, long and short
- at least 20 configured pairs
- at least 2 completed trades per day on average
- at least 70% trade win rate
- at least 100% annualized portfolio return, or 0.5% average portfolio return per day

## Reproducible setup

- Strategy: `Intp20Stage60BlendedShockStrategy`
- Timeframe: `1m`
- Wallet: `1000 USDT`
- Stake: `100 USDT`
- Concurrent positions: `9`
- Leverage: `4x`, isolated
- Configured universe: 41 fixed pairs
- Cost: `0.07%` per side (`0.05%` fee plus a `0.02%` slippage allowance)
- Effective round-trip cost before funding: approximately `0.14%`
- Funding: `0` in the backtest
- Entry and exit: market orders

The exported trades record `fee_open=0.0007` and `fee_close=0.0007`. Slippage was
represented through the combined fee override; it was not modeled as a separate random
fill process.

The archived runs used the research class `Intp20Stage51Trail024x006`. Stage60 is its
deployment promotion: it inherits the same Stage31 entry implementation and fixes the
same stop, horizon, leverage, and trailing parameters. Automated tests assert this mapping.
The result archives are intentionally excluded from Git:

- `backtest-result-2026-07-27_23-16-59.zip`
- `backtest-result-2026-07-27_23-02-39.zip`
- `backtest-result-2026-07-27_23-10-32.zip`

## Native Freqtrade results

| Period | Return | CAGR | Win rate | Trades | Trades/day | Profit factor | Max drawdown | Long / short return |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023-07-01..2024-07-01 | +273.16% | 271.82% | 83.68% | 6,077 | 16.60 | 1.216 | 24.45% | +212.21% / +60.95% |
| 2024-07-01..2025-07-01 | +118.32% | 118.32% | 81.27% | 5,671 | 15.54 | 1.098 | 50.18% | +9.59% / +108.73% |
| 2025-07-01..2026-07-01 | +164.36% | 164.36% | 81.28% | 4,253 | 11.65 | 1.176 | 41.47% | +130.96% / +33.40% |

The annual-return gate passes in every period. The alternative `0.5%` daily-return gate
is not claimed. A strategy can exceed 100% CAGR while its geometric daily return remains
below 0.5%.

## Signal and exit logic

Stage60 measures each pair's 30-minute return relative to BTC. It enters only when a
threshold crossing is backed by at least twice the pair's rolling median volume:

- long after a relative drop below `-2.5%`
- short after a relative rise above `+6.0%`
- long maximum hold: 90 minutes
- short maximum hold: 120 minutes
- trailing exit activates at `+2.4%` leveraged profit and trails by `0.6%`
- hard emergency stop: `-80%` leveraged trade profit

The hard stop is intentionally wide and is not the normal exit. The time horizon and
trailing stop perform most exits.

## Universe and coverage

The fixed pool is:

`FET, 1000BONK, APT, 1000FLOKI, NEAR, APE, INJ, CRV, DOGE, DYDX, FIL, ENA, SOL,
ETHFI, ETC, JTO, AVAX, JUP, BCH, LDO, LTC, MERL, 1000PEPE, NOT, ETH, ONDO, ADA,
ORDI, COMP, PENDLE, DOT, PUMP, OP, PYTH, 1000SHIB, SEI, XTZ, TAO, HBAR, TIA, WIF`.

PUMP and MERL have shorter listing histories than the older contracts. PUMP had data in
the latest window but did not trigger a completed trade. Depending on listings available
in each historical period, 39 to 40 pairs produced trades. This is a portfolio result: it
does not mean every individual pair was profitable. The number of profitable active pairs
was 29/39, 27/40, and 30/40 respectively.

## Risk and limitations

- Maximum drawdown reached 50.18% and the weakest annual profit factor was only 1.098.
- Four-times leverage and the wide emergency stop create substantial tail and liquidation
  risk. A future loss can exceed historical drawdowns.
- Funding, order-book depth, partial fills, outages, latency, and changing exchange rules
  are not fully modeled.
- The fixed universe has listing and survivorship bias. New contracts do not have a full
  year of history before their listing date.
- Three non-overlapping annual windows reduce, but do not eliminate, overfitting risk.
- Past annualized return and win rate do not guarantee future results.

Dry-run performance must be reviewed after at least 30 days. Compare realized trade count,
win rate, fees, slippage, profit factor, and drawdown with this report before considering
any live-money decision.

## Reproduction

Run one annual interval at a time. A 41-pair year of 1-minute candles exceeded 13 GB of
working memory in local verification, so do not run this on the production Bot host while
the dry-run is active.

```bash
python user_data/scripts/run_offline_futures_backtest.py \
  --config user_data/config_binance_stage60_blended_shock_41pair_1000u_dryrun.json \
  --strategy Intp20Stage60BlendedShockStrategy \
  --timerange 20250701-20260701 \
  --fee 0.0007 \
  --cache none
```
