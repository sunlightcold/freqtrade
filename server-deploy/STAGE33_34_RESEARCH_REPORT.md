# Stage33-34 Acceptance-Gate Research

## Verdict

No candidate passed all hard gates. No strategy in this report is approved for
deployment.

| Gate | Requirement |
| --- | ---: |
| Universe | 20 Binance USDT perpetual pairs |
| Direction | Both long and short |
| Validation | At least one full year per pair, with locked sample-out parameters |
| Cost | 0.07% per side (0.05% fee plus 0.02% slippage) |
| Win rate | At least 70% |
| Activity | At least 2 trades/day |
| Return | At least 100%/year or 0.5% average/day |

Funding was not included because historical funding/mark data is unavailable
locally. This omission makes the tests more favorable, not more conservative.

## Windows

- Development: 2023-07-01 through 2024-07-01.
- Validation: 2024-07-01 through 2025-07-01.
- Sample out: 2025-07-01 through 2026-07-01.
- Walk-forward ML: prior 365 days train each quarterly model; 2024-07-01
  through 2025-07-01 selects thresholds; 2025-07-01 through 2026-07-01 is
  untouched sample out.

## Results

| Experiment | Development | Validation | Sample out | Failure |
| --- | --- | --- | --- | --- |
| Stage31 TP/horizon, 1% TP, 120m | 78.52% WR, 10.28/day, +122.23% | 78.15% WR, 10.07/day, -37.55% | 79.21% WR, 4.94/day, +42.39% | Negative validation expectancy |
| Adaptive relative shock | 80.56% WR, 6.03/day, +68.61% | 77.71% WR, 5.48/day, -32.51% | 79.54% WR, 3.07/day, +8.06% | Online filter did not restore PF above 1 |
| 5m traditional fixed exits | No three-window positive candidate | No three-window positive candidate | No three-window positive candidate | Maximum portfolio WR 50.49% |
| 15m traditional fixed exits | No three-window positive candidate | No three-window positive candidate | No three-window positive candidate | Maximum portfolio WR below 50% |
| 15m reversal bracket | 77.27% WR, 2.54/day, PF 0.697 | Negative | Negative | High win rate but negative expectancy |
| Cross-sectional 1.2%/3% bracket | 73.07% WR, 1.98/day, -22.55% | 75.00% WR, 1.98/day, +0.61% | 72.06% WR, 1.98/day, -34.56% | Frequency below gate and two losing years |
| Walk-forward ML 1.2%/3% | 71.37% WR, 4.19/day, PF 0.879 | Threshold-selection year | 69.50% WR, 3.35/day, PF 0.841 | Negative expectancy and sample-out WR below 70% |
| Walk-forward ML 2%/3% | 59.69% WR, 6.52/day, PF 0.907 | Threshold-selection year | 57.36% WR, 5.19/day, PF 0.898 | Win-rate and return gates fail |

The TP/horizon and generic-template rows are fast screens with equal-slot
capital approximations. They are rejection evidence only. The walk-forward ML
rows use fixed 90 USDT margin, 5x leverage, no more than 10 concurrent trades,
one open trade per pair, and exits ordered by their simulated timestamps.

## Overfitting Check

A separate development-only per-pair selection chose 36 pair/side rules from
18,760 candidates. Only 10 remained profitable in validation, 7 in sample out,
and 2 in both. No candidate had at least 70% win rate, PF above 1, and meaningful
activity in all three windows. Pair-specific optimization was therefore
rejected instead of being promoted into a strategy.

## Decision

- Stage31 deployment is blocked.
- No Stage32/33/34 runtime strategy or dry-run configuration is published.
- Current running bots are not changed by this research.
- A future candidate must pass every gate in native Freqtrade backtesting before
  any deployment script is enabled.
