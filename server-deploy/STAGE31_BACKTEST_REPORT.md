# Stage31 Relative Shock Validation

## Verdict

Stage31 is an experimental dry-run strategy. It does **not** pass the full target.

| Requirement | Result | Status |
| --- | ---: | --- |
| One strategy, 20 pairs | 20 pairs | PASS |
| At least one year per pair | 365 days per validation window | PASS |
| Long and short | 952 long / 93 short in the latest window | PASS |
| At least 3 trades/day | 2.86 latest; 4.80 prior year | FAIL |
| At least 80% win rate | 60.48% latest; 53.85% prior year | FAIL |
| At least 100% annual portfolio return | 125.71% latest; 56.71% prior year | FAIL across years |
| At least 0.5% average profit/day | 0.344% latest; 0.155% prior year | FAIL |
| Every pair at least 100% annual return | 0 of 20 | FAIL |

There is no claim or guarantee that backtest returns will continue in dry-run or live trading.

## Method

- Binance USDT perpetual 1-minute OHLCV.
- Starting wallet: 1000 USDT.
- Isolated futures, 3x leverage, 90 USDT margin per trade, at most 10 positions.
- Normal cost: 0.05% per entry/exit side.
- Stress cost: 0.07% per side, representing 0.05% fee plus 0.02% slippage.
- Funding is set to zero because historical mark/funding data is unavailable locally.
- Entries execute on the candle after the completed signal candle.
- One uniform parameter set is used for every pair.
- Long positions close after 60 minutes, shorts after 30 minutes, with a -60% leveraged emergency stop.

## Portfolio Results

| Window | Cost/side | Trades/day | Long/short | Win rate | Return | Max drawdown | Profit factor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024-07-01..2025-07-01 | 0.05% | 4.80 | 1559 / 194 | 53.85% | +56.71% | 36.96% | 1.119 |
| 2025-07-01..2026-07-01 | 0.05% | 2.86 | 952 / 93 | 60.48% | +125.71% | 37.06% | 1.543 |
| 2025-07-01..2026-07-01 stress | 0.07% | 2.86 | 952 / 93 | 59.71% | +114.73% | 38.25% | 1.487 |

## Latest Per-Pair Results

Results below use 2025-07-01..2026-07-01 and 0.05% per side. Profit is contribution to the shared 1000 USDT portfolio, not standalone per-pair CAGR.

| Pair | Trades | Win rate | Profit USDT | Portfolio contribution |
| --- | ---: | ---: | ---: | ---: |
| 1000PEPE | 60 | 75.0% | +178.70 | +17.87% |
| COMP | 75 | 62.7% | +126.54 | +12.65% |
| INJ | 108 | 57.4% | +105.64 | +10.56% |
| NEAR | 102 | 67.6% | +101.90 | +10.19% |
| OP | 93 | 57.0% | +96.19 | +9.62% |
| APT | 55 | 63.6% | +90.57 | +9.06% |
| FET | 146 | 58.9% | +85.26 | +8.53% |
| ETC | 19 | 63.2% | +66.26 | +6.63% |
| ETH | 4 | 100.0% | +64.67 | +6.47% |
| DOGE | 37 | 67.6% | +59.72 | +5.97% |
| XTZ | 47 | 53.2% | +58.44 | +5.84% |
| AVAX | 27 | 51.9% | +47.78 | +4.78% |
| FIL | 116 | 52.6% | +42.79 | +4.28% |
| SOL | 13 | 69.2% | +40.90 | +4.09% |
| HBAR | 24 | 75.0% | +30.91 | +3.09% |
| LTC | 23 | 56.5% | +27.94 | +2.79% |
| DOT | 32 | 62.5% | +24.11 | +2.41% |
| 1000SHIB | 8 | 37.5% | +14.00 | +1.40% |
| BCH | 36 | 55.6% | +7.80 | +0.78% |
| ADA | 20 | 55.0% | -13.02 | -1.30% |

## Reproduce

```bash
python user_data/scripts/run_offline_futures_backtest.py \
  -c user_data/config_binance_stage31_relative_shock_20pair_1000u_dryrun.json \
  --strategy Intp20Stage31RelativeShockStrategy \
  --timerange 20250701-20260701 \
  --fee 0.0005 \
  --no-timeframe-detail \
  --cache none \
  --export trades
```

## Deployment

Deployment is blocked. Stage31 failed the current acceptance gates and
`apply-stage31-single.sh` exits without changing the running environment.
