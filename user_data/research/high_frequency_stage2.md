# High-Frequency Stage 2 Research

Date: 2026-06-09

Goal: explore higher-frequency futures strategies after the retained 15m DCA
profile proved too low-frequency for a 0.5% daily-return target.

This note records real backtest outcomes. Results are not guarantees, and
short-window winners are rejected unless they survive walk-forward checks.

## Source Ideas Reused

- Freqtrade official futures examples: volatility expansion, supertrend-style
  state confirmation, leverage callbacks.
- SmoothScalp-style oscillator turns: fast stochastic, MFI, CCI, Bollinger
  location.
- NFI-style discipline: multi-timeframe regime filters, market guard concept,
  and strict rejection of short-window-only edge.

## New Strategy Experiments

| Candidate | Window | Pairs | Result | Decision |
| --- | --- | --- | ---: | --- |
| `Intp20CommunityFusionV2LongStrategy` | 2025-01-01..2025-03-01 | 20-pair universe | -58.27%, 1394 trades, 58.39% DD | Reject |
| `Intp20CommunityFusionV2ShortStrategy` | 2025-01-01..2025-03-01 | 20-pair universe | -70.49%, 1888 trades, 70.49% DD | Reject |
| `Intp20CommunityFusionV2ShortStrategy`, profit-only exits | 2025-01-01..2025-03-01 | 20-pair universe | -76.81%, 1771 trades, 76.97% DD | Reject |
| `Intp20CommunityMomentumShortStrategy` | 2025-01-01..2025-03-01 | AAVE, SUI, DOGE | +13.76%, 375 trades, 10.40% DD | Short-window only |
| `Intp20CommunityMomentumShortStrategy` | 2025-01-01..2025-03-01 | AAVE, SUI | +20.68%, 268 trades, 10.62% DD | Best short-window result |
| `Intp20CommunityMomentumShortStrategy` | 2025-01-01..2025-03-01 | AAVE | +20.44%, 134 trades, 14.93% DD | Less diversified |
| `Intp20CommunityRiskCutShortStrategy` | 2025-01-01..2025-03-01 | AAVE, SUI | +7.62%, 292 trades, 13.61% DD | Reject |
| `Intp20LongNextGenWeightedDcaStrategy` | 2025-01-01..2025-03-01 | retained long pool | +5.92%, 2 trades, 0.00% DD | Too low-frequency |

## Walk-Forward Rejection

The best short-window setup was:

```text
Intp20CommunityMomentumShortStrategy
pairs: AAVE/USDT:USDT, SUI/USDT:USDT
stake_amount: 5000
max_open_trades: 4
timerange: 20250101-20250301
```

It failed walk-forward:

| Window | Result | Notes |
| --- | ---: | --- |
| 2024-01-01..2024-12-31 | -50.48%, 402 trades, 57.35% DD | Bull-market shorting failure |
| 2025-01-01..2025-12-31 | -50.35%, 794 trades, 60.51% DD | January/February gains reversed after March |
| 2023-06-02..2026-05-31 | -50.38%, 508 trades, 52.31% DD | Early loss cluster invalidates deployment |

## Guard Variants

| Candidate | Window | Result | Decision |
| --- | --- | ---: | --- |
| `Intp20CommunityMacroShortStrategy` | 2024 | -52.26%, 278 trades, 55.62% DD | Reject |
| `Intp20CommunityBtcGuardShortStrategy` | 2024 | -51.95%, 299 trades, 55.19% DD | Reject |
| `Intp20CommunityBrakeShortStrategy` without protections | 2024 | -51.95%, 299 trades, 55.19% DD | Reject |
| `Intp20CommunityBrakeShortStrategy` with `--enable-protections` | 2024 | -50.03%, 285 trades, 52.12% DD | Reject |

## Tooling Finding

`user_data/scripts/run_offline_futures_backtest.py` did not expose
`--enable-protections`. The flag was added so future protection/circuit-breaker
research can be tested honestly.

## Conclusion

The 1m high-frequency families can easily generate enough trades, but the loss
tail is still larger than the win stream. A 0.5% daily target was not achieved
in a walk-forward-stable way in this stage.

Next useful stage:

1. Build a walk-forward optimizer that rejects a parameter set unless it is
   positive in 2024, 2025, and 2026 slices.
2. Add a true market-regime classifier before entries, not only per-trade
   protections after losses.
3. Search exits first: the recurring failure is stoploss clustering, not lack
   of entry frequency.

## Stage 3: Fast Screener Expansion

The local screener was expanded with additional templates and stricter ranking:

- `micro_momentum`
- `vwap_reclaim`
- `squeeze_breakout`
- `wick_reversal`
- compact/wide grid modes
- per-pair ranking
- leverage-adjusted scoring
- trade-frequency and walk-forward slice metrics

Generated CSV snapshots:

- `user_data/research/stage3_fast_5m_compact.csv`
- `user_data/research/stage3_fast_15m_compact.csv`
- `user_data/research/stage3_per_pair_5m_compact.csv`
- `user_data/research/stage3_per_pair_15m_compact.csv`

### Fast Screener Findings

The 5m portfolio search failed hard when traded as a 20-pair basket. The best
rows were still effectively account-ruin candidates after leverage adjustment.

The 15m per-pair screen produced a few candidates that were positive in 2024,
2025, and 2026 slices, but none reached the requested 0.5% daily target.

Best coarse candidates:

| Scope | Template | Side | Hold | Coarse Daily | Notes |
| --- | --- | --- | ---: | ---: | --- |
| DOGE | mean reversion | long | 24 candles | 0.227% | Too low-frequency |
| ETH | squeeze breakout | short | 24 candles | 0.112% | Large drawdown in coarse model |
| ETC | breakout | short | 24 candles | 0.101% | Candidate for native validation |
| OP | vwap reclaim | short | 12 candles | 0.060% | Candidate, but weak |
| COMP | mean reversion | short | 12 candles | 0.037% | Stable but too small |
| TRX | wick reversal | short | 24 candles | 0.036% | Stable but too small |

### Native Freqtrade Validation

`Intp20Stage3EdgeStrategy` converted the best 15m per-pair coarse rules into
native Freqtrade entries with fixed-hold `custom_exit` exits and 4x leverage.

First short-window validation, `2025-01-01..2025-03-01`, all selected rules:

| Candidate | Result |
| --- | ---: |
| Full Stage 3 rule basket | -4.07%, 95 trades, 9.41% DD |

The basket was rejected. Positive short-window contributors were isolated into
`Intp20Stage3EdgeShortCoreStrategy`:

| Window | Pairs | Result | DD | Decision |
| --- | --- | ---: | ---: | --- |
| 2025-01-01..2025-03-01 | ETC, TRX | +6.99%, 38 trades | 2.85% | Short-window only |
| 2024 | ETC, TRX | -2.71%, 135 trades | 14.47% | Reject combined |
| 2025 | ETC, TRX | +2.59%, 185 trades | 14.41% | Too weak |
| 2026-01-01..2026-05-31 | ETC, TRX | +8.31%, 45 trades | 1.53% | Too weak |

Single-rule validation showed ETC short breakout is better than TRX, but still
far from target:

| Window | Pair/Rule | Result | DD |
| --- | --- | ---: | ---: |
| 2024 | ETC short breakout | +3.55% | 8.47% |
| 2025 | ETC short breakout | -4.56% | 15.43% |
| 2026-01-01..2026-05-31 | ETC short breakout | +8.21% | 1.64% |

### Stage 3 Decision

Stage 3 did not reach or approach 0.5% daily. The main improvement was tooling:
we can now reject coarse overfit faster and translate candidates into native
Freqtrade validation. Next search should add regime-conditioned exits and
portfolio construction, because naive fixed-hold exits erase many coarse edges.
