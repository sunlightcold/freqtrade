# Stage 13 Validated 20-Pair Dry-Run Universe

Generated from native Freqtrade futures backtests for `Intp20Stage13Validated20Strategy` on 1m data.

## Source Results

| window | result_zip |
| --- | --- |
| 2023H2 | user_data/backtest_results/backtest-result-2026-06-10_19-01-12.zip |
| 2024 | user_data/backtest_results/backtest-result-2026-06-10_18-58-20.zip |
| 2025 | user_data/backtest_results/backtest-result-2026-06-10_18-51-48.zip |
| 2026_01_05 | user_data/backtest_results/backtest-result-2026-06-10_18-47-07.zip |

## Admission Rule

Only pairs with native Freqtrade portfolio evidence are promoted to the dry-run whitelist. Template-scan candidates alone are not enough. The final dry-run configuration uses a 10,000 USDT wallet, 1,000 USDT fixed stake, isolated futures, and `max_open_trades = 8`.

## Final 20 Pairs

MKR, SOL, XLM, AAVE, XTZ, XRP, ETH, SUI, ETC, LTC, COMP, OP, APT, DOGE, DOT, ICP, NEAR, FET, UNI, MANA

Base Stage-12 universe: MKR, SOL, XLM, AAVE, XTZ, XRP, ETH, SUI, ETC, LTC, COMP, OP, APT, DOGE.

Stage-13 additions: DOT, ICP, NEAR, FET, UNI, MANA.

## Portfolio Windows

| window | starting_balance | final_balance | profit_pct | cagr_pct | daily_simple_pct | daily_compound_pct | daily_0p5_hit_rate_pct | trades | long_trades | short_trades | profit_factor | max_drawdown_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023H2 | 10000.0 | 10595.7873 | 5.9579 | 10.5292 | 0.0282 | 0.0274 | 19.8113 | 617 | 282 | 335 | 1.0567 | 9.9525 |
| 2024 | 10000.0 | 19045.2637 | 90.4526 | 90.1177 | 0.2471 | 0.1762 | 32.7869 | 1429 | 686 | 743 | 1.3521 | 7.7093 |
| 2025 | 10000.0 | 18581.6323 | 85.8163 | 85.8163 | 0.2351 | 0.1699 | 28.2192 | 1204 | 611 | 593 | 1.4226 | 6.792 |
| 2026_01_05 | 10000.0 | 13562.2589 | 35.6226 | 109.8978 | 0.2375 | 0.2033 | 28.0 | 373 | 151 | 222 | 1.7377 | 4.1362 |

The current validated set does not reach the requested 0.5% average daily target in every window. The strongest full-year windows are near 0.25% simple daily return on starting balance, while 2023H2 is much weaker. Treat this as a dry-run candidate, not a return guarantee.

## Pair Ranking

| base | total_profit_abs | total_profit_pct_points | total_trades | profitable_windows | losing_windows | windows_with_trades | zero_trade_windows | min_window_profit_pct | min_window_trades | 2023H2_profit_pct | 2024_profit_pct | 2025_profit_pct | 2026_01_05_profit_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MKR | 3202.2172 | 32.0222 | 555 | 3 | 0 | 3 | 1 | 0.0 | 0 | 0.5867 | 11.9966 | 19.4389 | 0.0 |
| SOL | 1998.8391 | 19.9884 | 289 | 4 | 0 | 4 | 0 | 0.9725 | 24 | 1.2066 | 11.8453 | 5.964 | 0.9725 |
| AAVE | 1945.4338 | 19.4543 | 139 | 4 | 0 | 4 | 0 | 0.299 | 19 | 0.299 | 9.1019 | 5.3826 | 4.6708 |
| XLM | 1633.533 | 16.3353 | 157 | 4 | 0 | 4 | 0 | 1.1965 | 14 | 1.3539 | 10.3325 | 3.4524 | 1.1965 |
| ICP | 1459.3087 | 14.5931 | 201 | 4 | 0 | 4 | 0 | 0.573 | 28 | 0.573 | 3.3557 | 9.1848 | 1.4796 |
| DOT | 1396.9324 | 13.9693 | 159 | 3 | 1 | 4 | 0 | -2.4006 | 19 | -2.4006 | 4.0117 | 3.5173 | 8.8409 |
| XTZ | 1254.4133 | 12.5441 | 174 | 3 | 1 | 4 | 0 | -0.3562 | 25 | -0.3562 | 5.6099 | 4.3363 | 2.9541 |
| NEAR | 1230.4787 | 12.3047 | 266 | 3 | 1 | 4 | 0 | -0.2257 | 39 | -0.2257 | 3.0294 | 8.0169 | 1.4841 |
| XRP | 1130.6297 | 11.3063 | 124 | 4 | 0 | 4 | 0 | 0.2543 | 14 | 0.2543 | 1.7741 | 6.3576 | 2.9203 |
| FET | 963.8852 | 9.6389 | 332 | 4 | 0 | 4 | 0 | 0.6993 | 39 | 3.0381 | 4.2367 | 1.6648 | 0.6993 |
| ETH | 932.0935 | 9.3209 | 56 | 4 | 0 | 4 | 0 | 0.2623 | 2 | 1.1297 | 1.5766 | 6.3523 | 0.2623 |
| UNI | 742.9755 | 7.4297 | 215 | 2 | 2 | 4 | 0 | -2.8004 | 31 | -0.1989 | 5.7669 | -2.8004 | 4.6621 |
| ETC | 728.4103 | 7.284 | 67 | 4 | 0 | 4 | 0 | 0.1316 | 5 | 0.6081 | 4.7136 | 1.8307 | 0.1316 |
| OP | 714.0791 | 7.1407 | 138 | 4 | 0 | 4 | 0 | 0.0429 | 12 | 1.6758 | 0.0429 | 4.7739 | 0.6481 |
| LTC | 603.8892 | 6.0389 | 262 | 3 | 1 | 4 | 0 | -0.3672 | 17 | -0.3672 | 1.9802 | 4.2096 | 0.2163 |
| COMP | 592.7652 | 5.9277 | 45 | 2 | 2 | 4 | 0 | -0.3054 | 1 | -0.1078 | 4.0375 | 2.3034 | -0.3054 |
| SUI | 506.4985 | 5.065 | 181 | 3 | 1 | 4 | 0 | -1.9157 | 26 | -1.9157 | 3.3155 | 0.9958 | 2.6694 |
| DOGE | 338.3154 | 3.3832 | 74 | 4 | 0 | 4 | 0 | 0.339 | 5 | 1.1088 | 1.3295 | 0.6059 | 0.339 |
| APT | 274.9918 | 2.7499 | 64 | 2 | 2 | 4 | 0 | -0.2784 | 2 | -0.2486 | 2.4108 | -0.2784 | 0.8661 |
| MANA | 135.2529 | 1.3525 | 125 | 2 | 2 | 4 | 0 | -0.0556 | 19 | -0.0556 | -0.0146 | 0.5079 | 0.9148 |

## Excluded Expansion Candidates

- SAND: native windows had ugly stop-loss behavior
- FIL: native windows had ugly stop-loss behavior
- 1000PEPE: native windows had ugly stop-loss behavior
- RUNE: unstable native windows
- ADA: weak 2026 native validation
- ARB: unstable native windows
- 1000SHIB: marginal edge versus the final six additions

## Dry-Run Command

```powershell
.\.venv\Scripts\freqtrade.exe trade -c user_data\config_binance_stage13_validated_20pair_dryrun.json --strategy Intp20Stage13Validated20Strategy
```

## Validation Commands

```powershell
.\.venv\Scripts\python.exe user_data\scripts\run_offline_futures_backtest.py -c user_data\config_binance_stage13_validated_20pair_dryrun.json --strategy Intp20Stage13Validated20Strategy --timerange 20230602-20240101 --breakdown year --export trades --cache none
.\.venv\Scripts\python.exe user_data\scripts\run_offline_futures_backtest.py -c user_data\config_binance_stage13_validated_20pair_dryrun.json --strategy Intp20Stage13Validated20Strategy --timerange 20240101-20250101 --breakdown year --export trades --cache none
.\.venv\Scripts\python.exe user_data\scripts\run_offline_futures_backtest.py -c user_data\config_binance_stage13_validated_20pair_dryrun.json --strategy Intp20Stage13Validated20Strategy --timerange 20250101-20260101 --breakdown year --export trades --cache none
.\.venv\Scripts\python.exe user_data\scripts\run_offline_futures_backtest.py -c user_data\config_binance_stage13_validated_20pair_dryrun.json --strategy Intp20Stage13Validated20Strategy --timerange 20260101-20260601 --breakdown year --export trades --cache none
```
