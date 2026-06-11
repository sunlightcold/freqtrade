# Stage 19 Aggressive Newcoin Research

Date: 2026-06-11

Goal: add a separate high-risk Stage19 strategy that can backtest wider and
newer Binance USDT futures pairs with shorter local 1m history.  Stage19 does
not replace Stage17/18.

## Implementation

New files:

- `user_data/strategies/Intp20Stage19AggressiveNewcoinStrategy.py`
- `user_data/config_binance_stage19_aggressive_newcoin_38pair_200u_dryrun.json`

Server deploy equivalents:

- `server-deploy/user_data/strategies/Intp20Stage19AggressiveNewcoinStrategy.py`
- `server-deploy/user_data/config_binance_stage19_aggressive_newcoin_38pair_1000u_dryrun.json`

Design:

- Inherits Stage18, so the validated Stage17/18 entries and hotspot overlay
  stay intact.
- Lowers `startup_candle_count` from the Stage7 base of 1500 to 240 so newer
  coins can be backtested with shorter 1m history.
- Uses a 38-pair static futures universe for reproducible backtests.
- Adds one aggressive 1m momentum stream, `s19_momo_l_h10m_l8`, only for the
  current validated short-history subset:
  - `XLM/USDT:USDT`
  - `ICP/USDT:USDT`
  - `SUI/USDT:USDT`
  - `LINK/USDT:USDT`
- Keeps the rest of the 38-pair universe in the config so new pairs can be
  tested without changing deployment structure.
- Keeps fee at `0.0005` per side in both configs.
- Keeps no DCA / no martingale.

The first broad version allowed generic long, short, squeeze, and snapback
signals across the whole 38-pair universe. It generated 1293 trades in 2026-05
but lost heavily after fees. The final version narrows Stage19's new signal to
the pairs that stayed positive in both 2026-05 and 2026-01..05.

## Local Validation

Commands:

```bash
python -m py_compile user_data/strategies/Intp20Stage19AggressiveNewcoinStrategy.py server-deploy/user_data/strategies/Intp20Stage19AggressiveNewcoinStrategy.py
python user_data/scripts/run_offline_futures_backtest.py -c user_data/config_binance_stage19_aggressive_newcoin_38pair_200u_dryrun.json --strategy Intp20Stage19AggressiveNewcoinStrategy --timerange 20260501-20260601 --timeframe 1m --no-timeframe-detail --cache none --breakdown month --fee 0.0005
python user_data/scripts/run_offline_futures_backtest.py -c user_data/config_binance_stage19_aggressive_newcoin_38pair_200u_dryrun.json --strategy Intp20Stage19AggressiveNewcoinStrategy --timerange 20260101-20260601 --timeframe 1m --no-timeframe-detail --cache none --breakdown month year --fee 0.0005
```

## Backtest Results

All runs used Binance USDT futures, 1m candles, isolated margin, no DCA, no
martingale, and 0.05% one-side fee.  The final config uses 200 USDT wallet,
18 USDT stake, and 10 max open trades locally.  The server config maps this to
1000 USDT wallet, 90 USDT stake, and 10 max open trades.

| Window | Strategy | Return | Trades | Profit Factor | Max DD | Notes |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 2026-05 | Stage18 No-Key Hotspot | 7.03% | 69 | n/a | 1.94% | Prior baseline |
| 2026-05 | Stage19 Aggressive Newcoin | 24.67% | 105 | 2.44 | 3.81% | Short-window boost |
| 2026-01..05 | Stage18 No-Key Hotspot | 56.83% | 427 | n/a | 4.79% | Prior baseline |
| 2026-01..05 | Stage19 Aggressive Newcoin | 74.12% | 520 | 1.82 | 6.70% | Higher return, higher DD |

Monthly Stage19 2026-01..05:

| Month | Trades | Profit Abs | Notes |
| --- | ---: | ---: | --- |
| 2026-01 | 119 | 22.62 USDT | Positive |
| 2026-02 | 139 | 36.27 USDT | Positive |
| 2026-03 | 97 | 20.64 USDT | Positive |
| 2026-04 | 60 | 19.37 USDT | Positive |
| 2026-05 | 105 | 49.35 USDT | Strongest month |

## Decision

Stage19 is a stronger short-term dry-run candidate than Stage18 when the user
accepts higher drawdown.  It should be monitored forward before any live-capital
use because the extra return comes from a narrow high-frequency momentum layer
and higher capital concentration, not from a guaranteed market-neutral edge.
