# Stage 18 No-Key Hotspot Research

Date: 2026-06-11

Goal: add a separate, non-destructive hotspot overlay strategy without paid
data sources or API keys.  Stage18 does not replace Stage17; it inherits the
Stage17 signal engine and adds market-hotness scoring for stake/leverage
adjustment and risk exits.

## Implementation

New files:

- `user_data/strategies/Intp20Stage18NoKeyHotspotStrategy.py`
- `user_data/scripts/fetch_stage18_hotspot_cache.py`
- `user_data/config_binance_stage18_no_key_hotspot_20pair_200u_dryrun.json`

Server deploy equivalents:

- `server-deploy/user_data/strategies/Intp20Stage18NoKeyHotspotStrategy.py`
- `server-deploy/user_data/scripts/fetch_stage18_hotspot_cache.py`
- `server-deploy/user_data/config_binance_stage18_no_key_hotspot_20pair_1000u_dryrun.json`

Design:

- Core entries and exits inherit Stage17 Turbo.
- Backtests use only local OHLCV-derived hotspot features:
  - 15m volume impulse versus 240m baseline
  - 15m/60m momentum
  - short-term volatility expansion
- Dry/live mode can additionally read
  `user_data/hotspot/stage18_hotspot_cache.json`.
- The strategy never calls external APIs from order-handling callbacks.
- If the cache is missing, stale, or degraded, the strategy falls back to the
  local OHLCV score.
- If Binance public futures endpoints return 451 or otherwise fail, the
  collector writes neutral pair scores and marks the cache as degraded.

## Local Validation

Commands:

```bash
python -m py_compile user_data/scripts/fetch_stage18_hotspot_cache.py user_data/strategies/Intp20Stage18NoKeyHotspotStrategy.py
python user_data/scripts/fetch_stage18_hotspot_cache.py --config user_data/config_binance_stage18_no_key_hotspot_20pair_200u_dryrun.json --output user_data/hotspot/stage18_hotspot_cache.json --timeout 8
python user_data/scripts/run_offline_futures_backtest.py -c user_data/config_binance_stage18_no_key_hotspot_20pair_200u_dryrun.json --strategy Intp20Stage18NoKeyHotspotStrategy --timerange 20260501-20260531 --timeframe 1m --no-timeframe-detail --cache none --breakdown month
python user_data/scripts/run_offline_futures_backtest.py -c user_data/config_binance_stage18_no_key_hotspot_20pair_200u_dryrun.json --strategy Intp20Stage18NoKeyHotspotStrategy --timerange 20260101-20260531 --timeframe 1m --no-timeframe-detail --cache none --breakdown month
```

Current local network note:

- Alternative.me Fear & Greed was reachable.
- Binance futures public endpoints returned HTTP 451 from this environment.
- The collector correctly marked `degraded=true` and emitted neutral pair
  scores instead of fake ranks.

## Backtest Results

All runs used 20 Binance USDT futures pairs, wallet 200 USDT, stake 18 USDT,
max open trades 10, isolated futures, no DCA/martingale, and 0.05% one-side
fee where configured.

| Window | Strategy | Return | Trades | Max DD | Notes |
| --- | --- | ---: | ---: | ---: | --- |
| 2026-05 | Stage17 Turbo | 7.47% | 69 | 2.09% | Prior baseline |
| 2026-05 | Stage18 No-Key Hotspot | 7.03% | 69 | 1.94% | Slightly lower return, lower DD |
| 2026-01..05 | Stage17 Turbo | 55.58% | 427 | 4.99% | Prior baseline |
| 2026-01..05 | Stage18 No-Key Hotspot | 56.83% | 427 | 4.79% | Slightly higher return, lower DD |

## Decision

Stage18 is a viable separate dry-run candidate.  It should be treated as a
hotspot/risk overlay rather than a full news-AI strategy until real news or
social data is added.

The first overly strict filter version reduced 2026-05 first-half trades from
37 to 10 and underperformed.  The final version keeps Stage17's trade count
and uses hot/risk scores mainly for stake, leverage, and adverse-risk exits.
