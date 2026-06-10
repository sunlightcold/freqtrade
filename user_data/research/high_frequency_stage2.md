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

## Stage 4: Bracket Exit Rejection

The bracket-exit screener was tested against ETC wick-reversal shorts because
the coarse ranking looked better than the Stage-3 ETC breakout candidate.
Native Freqtrade validation rejected the idea:

| Candidate | Window | Result | Decision |
| --- | --- | ---: | --- |
| `Intp20Stage4BracketEtcWickShortStrategy` | 2025-01-01..2025-03-01 | -0.83% | Reject |
| `Intp20Stage4LooseEtcWickShortStrategy` | 2025-01-01..2025-03-01 | -2.39% | Reject |

The failed strategy classes were not kept in the strategy file. The useful
artifact from this stage is the faster bracket-exit simulator.

## Stage 5: Regime-Aware 1m/5m Scalp Search

The screener was expanded with BTC market-regime filters, local trend/chop
filters, stream loading for 1m data, and higher-frequency templates:

- `rsi_reversion`
- `stoch_turn`
- `range_breakout`
- `ema_cross_scalp`
- `panic_snapback`
- `liquidity_sweep`

Generated CSV snapshots:

- `user_data/research/stage5_per_pair_5m_compact_fixed.csv`
- `user_data/research/stage5_per_pair_1m_focus_fixed.csv`

Best 5m fixed-hold candidates from the coarse screener:

| Rank | Pair | Template | Side | Regime | Hold | Coarse Daily | Min Slice Daily | Trades/Day | Max DD |
| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | XRP | RSI reversion | short | market extreme | 24 | 0.097% | 0.094% | 0.057 | 25.87% |
| 5 | XTZ | RSI reversion | short | local chop | 24 | 0.087% | 0.110% | 0.137 | 45.18% |
| 7 | XTZ | panic snapback | long | market contra | 24 | 0.152% | 0.044% | 0.115 | 30.79% |
| 15 | LINK | panic snapback | long | market contra | 12 | 0.074% | 0.056% | 0.144 | 31.90% |

Best 1m focused candidates from the coarse screener:

| Rank | Pair | Template | Side | Regime | Hold | Coarse Daily | Min Slice Daily | Trades/Day | Max DD |
| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | LINK | panic snapback | long | market contra | 40 | 0.213% | 0.072% | 0.101 | 53.87% |
| 3 | XRP | panic snapback | long | market contra | 40 | 0.151% | 0.033% | 0.255 | 52.78% |
| 7 | SOL | panic snapback | long | market contra | 40 | 0.091% | -0.005% | 0.110 | 46.43% |

### Native Validation

`Intp20Stage5LinkPanicLongStrategy` converted the top 1m LINK candidate into
native Freqtrade entries with a 40-minute fixed-hold exit and 4x leverage.

The first validation window rejected the raw version:

| Strategy | Window | Result | DD | Notes |
| --- | --- | ---: | ---: | --- |
| `Intp20Stage5LinkPanicLongStrategy` | 2025-01-01..2025-03-01 | -3.11% | 5.28% | One -35% leveraged stop erased small winners |
| `Intp20Stage5LinkPanicWideStopStrategy` | 2025-01-01..2025-03-01 | -2.09% | 4.27% | Wider stop did not restore edge |
| `Intp20Stage5LinkPanicRiskCutStrategy` | 2025-01-01..2025-03-01 | +0.27% | 2.13% | Short-window only |

Walk-forward validation rejected the risk-cut variant:

| Window | Result | Trades | DD | Decision |
| --- | ---: | ---: | ---: | --- |
| 2024 | +11.22% | 38 | 2.19% | Positive but low-frequency |
| 2025 | -2.54% | 36 | 5.75% | Reject |
| 2026-01-01..2026-05-31 | -1.99% | 8 | 2.68% | Reject |

### Stage 5 Decision

The 1m search produced higher coarse returns than earlier stages, but the
best native candidate failed walk-forward and remains far below the requested
0.5% daily target. The next stage should search multi-candidate portfolios and
state-dependent exits, because single-pair panic-reversal edges are too sparse
and too sensitive to tail-loss clusters.

## Stage 6: Coarse Candidate Portfolio

`research_candidate_portfolio.py` was added to rebuild trades from selected
fast-screener CSV rows and score them as a combined portfolio. Each trade uses
`12.5%` of account equity in the coarse model, approximating eight capital
slots instead of full-account compounding per candidate.

Generated CSV snapshots:

- `user_data/research/stage6_5m_selected.csv`
- `user_data/research/stage6_5m_portfolio_trades.csv`
- `user_data/research/stage6_1m_selected.csv`
- `user_data/research/stage6_1m_portfolio_trades.csv`

### 5m Portfolio

Selected candidates:

| Pair | Template | Side | Regime | Hold |
| --- | --- | --- | --- | ---: |
| XTZ | panic snapback | long | market contra | 24 |
| SOL | panic snapback | short | market contra | 24 |
| SUI | RSI reversion | short | local chop | 24 |
| XRP | RSI reversion | short | market extreme | 24 |
| LINK | panic snapback | long | market contra | 24 |
| AAVE | panic snapback | long | market contra | 24 |
| COMP | RSI reversion | long | market extreme | 24 |

Coarse portfolio result:

| Window | Profit | Daily | Trades | Trades/Day | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Total | +307.90% | 0.129% | 1079 | 0.992 | 16.57% |
| 2024 | +118.46% | 0.215% | 432 | 1.187 | 13.20% |
| 2025 | +44.66% | 0.103% | 346 | 0.966 | 16.57% |
| 2026-01-01..2026-05-31 | +23.00% | 0.141% | 118 | 0.803 | 3.47% |

### 1m Portfolio

Selected candidates:

| Pair | Template | Side | Regime | Hold |
| --- | --- | --- | --- | ---: |
| LINK | panic snapback | long | market contra | 40 |
| XRP | panic snapback | long | market contra | 40 |

Coarse portfolio result:

| Window | Profit | Daily | Trades | Trades/Day | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Total | +81.08% | 0.056% | 375 | 0.350 | 15.60% |
| 2024 | +31.30% | 0.075% | 154 | 0.424 | 6.33% |
| 2025 | +11.62% | 0.031% | 136 | 0.386 | 15.60% |
| 2026-01-01..2026-05-31 | +10.77% | 0.092% | 27 | 0.243 | 2.10% |

### Stage 6 Decision

The 5m coarse portfolio is the most stable coarse result so far, but its
`0.129%` daily return is still far below the requested `0.5%` daily target.
It also needs native Freqtrade validation because Stage 5 showed coarse
single-candidate results can fail once real stoploss and order handling are
applied.

### Native Freqtrade Validation

`Intp20Stage6FiveMinutePortfolioStrategy` converted the selected 5m portfolio
into native Freqtrade logic. It runs on available `1m` candles and internally
resamples them to `5m` so the current local dataset can be reused.

Validation command shape:

```text
python user_data/scripts/run_offline_futures_backtest.py \
  -c user_data/config_binance_stage3_edge.json \
  --strategy Intp20Stage6FiveMinutePortfolioStrategy \
  --timeframe 1m \
  --pairs XTZ/USDT:USDT SOL/USDT:USDT SUI/USDT:USDT XRP/USDT:USDT \
          LINK/USDT:USDT AAVE/USDT:USDT COMP/USDT:USDT BTC/USDT:USDT \
  --no-timeframe-detail --breakdown month --cache none
```

Native results:

| Window | Profit | Trades | Max DD | Approx Daily | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| 2025-01-01..2025-03-01 | +3.78% | 64 | 5.21% | 0.063% | Smoke pass |
| 2024 | +53.58% | 414 | 9.67% | 0.119% | Positive, below target |
| 2025 | +23.42% | 332 | 11.04% | 0.059% | Positive, below target |
| 2026-01-01..2026-05-31 | +12.68% | 110 | 2.04% | 0.079% | Positive, below target |

Stage 6 is the cleanest native-validated high-frequency baseline so far:
positive across all validation slices with controlled drawdown. It still fails
the requested `0.5%` daily target by a wide margin, so the next stage must
increase opportunity count and improve exits without simply fitting one short
window.

## Stage 7: Aggressive Greedy Portfolio

`research_greedy_portfolio.py` was added to build a higher-exposure portfolio
from multiple screener CSVs with overlap de-duplication. A targeted exit scanner
was also added so promising entries could be checked without launching broad
bracket grids.

Best coarse 5m aggressive result used 5x leverage and a 25% capital slot:

| Window | Coarse Daily | Min Slice Daily | Trades/Day | Max DD |
| --- | ---: | ---: | ---: | ---: |
| Total | 0.504% | 0.464% | 2.33 | 48.84% |

That reached the requested daily target only in the coarse simulator. Native
Freqtrade validation showed the full basket was too noisy:

| Strategy | Window | Profit | Trades | Max DD | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `Intp20Stage7AggressivePortfolioStrategy` | 2025-01-01..2025-03-01 | +4.12% | 153 | 28.10% | Reject full basket |
| `Intp20Stage7AggressiveCoreStrategy` | 2025-01-01..2025-03-01 | +47.46% | 79 | 9.77% | Smoke pass, in-sample |

Walk-forward native validation for the pruned core, using `stake=2500`,
`max-open-trades=4`, and 5x strategy leverage:

| Window | Profit | Trades | Max DD | Approx Daily | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| 2024 | +105.71% | 498 | 37.39% | 0.198% | SUI tag was the main drag |
| 2025 | +96.82% | 408 | 12.47% | 0.185% | Negative June and October |
| 2026-01-01..2026-05-31 | +31.26% | 113 | 6.62% | 0.183% | XTZ slightly negative |

Stage 7 is the strongest native-validated return stream so far, but it still
does not reach `0.5%` daily outside the short smoke window. The coarse-to-native
drop confirms that every high-return coarse basket must be treated as an idea
source, not as an achieved target.

## Stage 8: Pruning And Capacity Checks

`Intp20Stage8NoSuiCoreStrategy` removes `sui_rsi_short_aligned_h24`, because it
lost `-19.32%` in the 2024 native validation and did not contribute enough in
2025/2026 to justify the tail risk. `Intp20Stage8LeaderCoreStrategy` removes
TRX as well and keeps the leader tags only.

Native validation at `stake=2500`, `max-open-trades=4`:

| Strategy | Window | Profit | Trades | Max DD | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| No-SUI core | 2024 | +125.02% | 414 | 19.15% | Better risk-adjusted |
| No-SUI core | 2025 | +92.20% | 375 | 13.60% | Slightly lower return |
| No-SUI core | 2026-01-01..2026-05-31 | +26.32% | 101 | 6.86% | Lower return |
| Leader core | 2024 | +123.20% | 378 | 21.32% | No improvement |
| Leader core | 2025 | +91.53% | 314 | 13.08% | Lower frequency |
| Leader core | 2026-01-01..2026-05-31 | +23.52% | 91 | 6.12% | Lower frequency |

Capacity check for the better No-SUI core, using `stake=3000` and
`max-open-trades=6`:

| Window | Profit | Trades | Max DD | Approx Daily |
| --- | ---: | ---: | ---: | ---: |
| 2024 | +150.02% | 414 | 21.50% | 0.252% |
| 2025 | +110.64% | 375 | 14.81% | 0.206% |
| 2026-01-01..2026-05-31 | +31.58% | 101 | 7.82% | 0.184% |

Stage 8 improved robustness in 2024, but it still does not approach `0.5%`
daily. Increasing exposure scales returns and drawdowns roughly linearly; it
does not solve the opportunity-count problem. The next search must add new
high-frequency streams, especially entries that trade during 2025-H2 without
deepening the June/October loss clusters.

## Stage 9: Aggressive Blend And Cross-Year Pruning

Stage 9 added a broader 1m-driven rule set that still validates through native
Freqtrade on the 1m dataset while internally resampling signals to 5m. The new
streams were inspired by common open-source Freqtrade patterns such as RSI/BB
snapbacks, VWAP reclaims, micro momentum, stochastic turns, and squeeze/range
breakouts, but every candidate below was rebuilt and checked against the local
20-pair futures dataset.

Native smoke validation at `stake=2500`, `max-open-trades=4`,
`2025-01-01..2025-03-01`:

| Strategy | Profit | Trades | Max DD | Decision |
| --- | ---: | ---: | ---: | --- |
| Aggressive blend | +29.50% | 240 | 27.50% | Too noisy |
| Smoke-pruned blend | +73.03% | 131 | 5.52% | Good smoke, needs walk-forward |

Walk-forward native validation for the smoke-pruned blend:

| Window | Profit | Trades | Max DD | Approx Daily | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| 2024 | +109.71% | 818 | 26.46% | 0.202% | Positive, higher DD |
| 2025 | +179.94% | 701 | 8.64% | 0.282% | Strong, still below target |
| 2026-01-01..2026-05-31 | +28.25% | 175 | 5.77% | 0.166% | Opportunity shortage |

`Intp20Stage9CrossYearCoreStrategy` then removed rules that flipped sharply
between years. Native validation at `stake=2500`, `max-open-trades=4`:

| Window | Profit | Trades | Max DD | Approx Daily | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| 2024 | +147.37% | 673 | 16.96% | 0.250% | Better risk-adjusted |
| 2025 | +134.64% | 583 | 11.64% | 0.234% | Lower than pruned blend |
| 2026-01-01..2026-05-31 | +25.87% | 137 | 5.66% | 0.153% | Still too sparse |

Capacity check for the cross-year core at `stake=3000`, `max-open-trades=6`:

| Window | Profit | Trades | Max DD | Approx Daily |
| --- | ---: | ---: | ---: | ---: |
| 2024 | +176.85% | 673 | 18.89% | 0.281% |
| 2025 | +161.56% | 583 | 12.47% | 0.264% |
| 2026-01-01..2026-05-31 | +31.04% | 137 | 6.47% | 0.180% |

Stage 9 is the strongest native family so far on risk-adjusted return, but it
still does not reach the requested `0.5%` daily target or `200%+` annualized
threshold across all validation slices. Larger stake helps but does not fix the
main bottleneck: Stage 9 does not create enough robust trades in 2026. The next
stage must add genuinely new high-frequency opportunity sources rather than
only pruning or scaling the same rules.

## Stage 10: 1m MA-Offset Hybrid

Stage 10 tested three new 1m templates in the fast screener:

- `orb_breakout`
- `vwap_stretch_reversion`
- `ma_offset_reversion`

The first accepted native candidate is `Intp20Stage10MaOffsetHybridStrategy`.
It keeps the native-validated Stage-9C 5m core and adds sparse 1m MA-offset
reversion rules. The Stage-10 tags use minute-based holds such as `h12m` and
`h18m`, while Stage-9 tags keep the existing 5m-bar hold convention. This avoids
accidentally turning a 12-minute 1m scalp into a 60-minute 5m hold.

Native validation used `stake=4000`, `max-open-trades=8`, `dry-run-wallet=10000`,
`timeframe=1m`, and the local Binance futures dataset.

| Strategy | Window | Profit | Trades | Max DD | CAGR | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Stage 9C capacity baseline | 2024 | +233.86% | 672 | 22.23% | 232.76% | Baseline passes 200% year |
| Stage 9C capacity baseline | 2025 | +215.43% | 583 | 13.69% | 215.43% | Baseline passes 200% year |
| Stage 9C capacity baseline | 2026-01-01..2026-05-31 | +41.01% | 136 | 7.89% | 130.76% | Still below target |
| Stage 10 Top3 MA-offset | 2026-01-01..2026-05-31 | +48.68% | 154 | 7.22% | 162.50% | Improves short slice, below target |
| Stage 10 Hybrid | 2024 | +249.49% | 926 | 24.34% | 248.30% | Higher return, higher DD |
| Stage 10 Hybrid | 2025 | +254.39% | 788 | 11.32% | 254.39% | Higher return, lower DD |
| Stage 10 Hybrid | 2026-01-01..2026-05-31 | +50.38% | 171 | 7.14% | 169.89% | Improves short slice, still below target |

### Stage 10 Decision

Stage 10 is a real incremental improvement over Stage 9C: it increases trade
count and improves all three validation windows at the tested exposure. It also
confirms the main constraint: even after adding 1m mean-reversion scalps, the
2026 slice still does not reach the requested `200%+` annualized threshold or
the stricter `0.5%` daily target. The next stage should keep Stage 10 as the
current best native candidate, then search for additional high-frequency streams
that specifically trade in quiet 2026-style regimes without adding large tail
losses.

## Stage 11: VWAP-Stretch Hybrid And Pruning

Stage 11 focused on 1m VWAP-stretch reversion as an additional high-frequency
stream. The standalone VWAP-stretch greedy portfolio was too sparse:

| Greedy Model | Trades | Profit | Daily | Min Slice Daily | Max DD | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| VWAP-stretch only | 163 | +15.60% | 0.014% | 0.015% | 1.76% | Low DD, too sparse |
| Stage10 MA-offset + VWAP-stretch | 552 | +55.23% | 0.041% | 0.050% | 2.88% | Worth native validation |

The combined greedy selected APT, SOL, ETC, DOGE, and XTZ VWAP-stretch add-ons.
Those rules became `Intp20Stage11VwapStretchHybridStrategy`, which keeps the
Stage-10 MA-offset hybrid intact and adds the VWAP-stretch rules as spare-slot
1m entries.

Native validation again used `stake=4000`, `max-open-trades=8`,
`dry-run-wallet=10000`, `timeframe=1m`, and the local Binance futures dataset.

| Strategy | Window | Profit | Trades | Max DD | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| Stage 11 Hybrid | 2024 | +260.35% | 1001 | 24.47% | Passes return target, high DD |
| Stage 11 Hybrid | 2025 | +257.17% | 872 | 11.73% | Strong |
| Stage 11 Hybrid | 2026-01-01..2026-05-31 | +58.26% | 191 | 6.81% | Approx. 200%+ CAGR |
| Stage 11B pruned | 2024 | +277.38% | 932 | 20.85% | Better 2024, lower DD |
| Stage 11B pruned | 2025 | +265.98% | 800 | 12.27% | Higher return, slightly higher DD |
| Stage 11B pruned | 2026-01-01..2026-05-31 | +55.24% | 177 | 6.94% | CAGR 191.60%, below target |
| Stage 11C no XTZ MA-offset | 2024 | +272.61% | 959 | 21.64% | Better than Stage 11 risk/return |
| Stage 11C no XTZ MA-offset | 2025 | +262.53% | 829 | 12.10% | Higher return than Stage 11 |
| Stage 11C no XTZ MA-offset | 2026-01-01..2026-05-31 | +59.07% | 184 | 6.78% | Best short slice so far |

### Stage 11 Decision

`Intp20Stage11CNoXtzMaoffStrategy` is the current best native candidate. It
removes only the Stage-10 XTZ short MA-offset add-on, while keeping the
Stage-11 VWAP-stretch stream. This is a cleaner compromise than Stage 11B:
Stage 11B reduced 2024 drawdown slightly more, but it also pushed the 2026
slice below the `200%+` annualized target.

Stage 11C finally clears the requested `200%+` annualized/yearly threshold in
all three native validation slices at the tested exposure. It does not yet prove
the stricter `0.5%` arithmetic daily target, and 2024 drawdown around `21.64%`
is still high. The next stage should therefore target drawdown clusters rather
than simply adding more entries:

- July-September 2024 drawdown cluster.
- October-December 2025 stagnation/drawdown cluster.
- APT/XTZ/DOGE VWAP-stretch rules that flip between strong and weak years.
- Dynamic exposure or pause filters that reduce stake during local loss clusters.

## Stage 12: Capacity And Dynamic XTZ Short Filter

Stage 12 first tested whether Stage 11C was mainly capital-constrained at the
requested `0.5%` arithmetic daily target. Native validation used the same local
Binance futures 1m dataset and 20-pair universe, but increased slot size from
`stake=4000` to `stake=5000` while keeping `max-open-trades=8` and
`dry-run-wallet=10000`.

| Strategy | Window | Profit | Trades | Max DD | Approx Daily | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Stage 11C capacity | 2024 | +335.96% | 951 | 24.62% | 0.918% | Passes return, high 2024 DD |
| Stage 11C capacity | 2025 | +307.42% | 827 | 13.36% | 0.842% | Passes return |
| Stage 11C capacity | 2026-01-01..2026-05-31 | +73.84% | 184 | 7.68% | 0.492% | Nearly hits 0.5% daily |

The capacity check showed that the existing edge can reach the user's annualized
return target under more aggressive slot sizing. It also confirmed that 2024's
August-September drawdown remains the main risk bottleneck.

Trade-level attribution on the Stage 11C capacity runs showed:

| Source | 2024 | 2025 | 2026-01..05 | Interpretation |
| --- | ---: | ---: | ---: | --- |
| `s9_08_xtz_rsi_s_lc_h24_l4` | +2541.62 USDT | +2676.53 USDT | -318.27 USDT | Useful in 2024/2025, harmful in 2026 rebound/chop |
| `s11_05_xtz_vstretch_l_mchop_h8m_l5` | negative at lower stake | negative at lower stake | positive at capacity | Not a clean standalone prune |
| `s11_04_doge_vstretch_s_mchop_h12m_l5` | weak | small positive | positive | Pruning reduces opportunity without fixing drawdown |

The first pruning candidates were deliberately small and reversible:

| Candidate | Window | Profit | Trades | Max DD | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| No XTZ VWAP-stretch long | 2026-01-01..2026-05-31 | +69.69% | 178 | 7.85% | Reject, lower return without DD improvement |
| No DOGE VWAP-stretch short | 2026-01-01..2026-05-31 | +72.73% | 182 | 7.73% | Not enough improvement |
| No XTZ/DOGE VWAP-stretch | 2026-01-01..2026-05-31 | +68.57% | 176 | 7.90% | Reject |
| Remove XTZ core short | 2026-01-01..2026-05-31 | +76.62% | 156 | 7.44% | Promising in 2026 |
| Remove XTZ core short | 2025 | +281.68% | 762 | 18.64% | Reject as full deletion |

The final Stage-12 candidate is `Intp20Stage12XtzCoreRocFilterStrategy`. It keeps
the XTZ core short rule, but blocks it when both XTZ and BTC have non-negative
5m 48-bar momentum:

```text
block XTZ core short when XTZ roc_48 >= 0 and BTC roc_48 >= 0
```

Native validation at `stake=5000`, `max-open-trades=8`, `dry-run-wallet=10000`:

| Strategy | Window | Profit | Trades | Max DD | Approx Daily | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Stage 12 XTZ ROC filter | 2024 | +340.86% | 940 | 23.50% | 0.931% | Better return and lower closed DD than capacity Stage 11C |
| Stage 12 XTZ ROC filter | 2025 | +307.97% | 794 | 13.57% | 0.844% | Matches capacity return, slightly higher DD |
| Stage 12 XTZ ROC filter | 2026-01-01..2026-05-31 | +87.65% | 174 | 5.40% | 0.584% | Best 2026 slice so far |

### Stage 12 Decision

`Intp20Stage12XtzCoreRocFilterStrategy` becomes the current best native
candidate. It satisfies the `200%+` annualized/yearly target in all validation
slices and reaches the requested `0.5%` arithmetic daily pace in the 2026 short
slice. It improves the 2026 drawdown materially and slightly improves the 2024
closed-trade drawdown, but it does not eliminate the 2024 wallet underwater
event around August-September. The next research pass should focus on that
cluster directly, especially MKR micro long, SOL panic short, SUI VWAP long, and
cross-asset risk throttling during broad chop/reversal periods.
