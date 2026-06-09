# Open Strategy Source Notes

This note tracks open-source strategy communities and the parts worth mining for
the INTP20 futures research workflow. Public strategies are treated as idea
sources only. Every adapted idea must be reimplemented in the local style,
backtested on our downloaded Binance futures data, and walk-forward checked
before it becomes a preset.

## Source Map

| Source | URL | Use |
| --- | --- | --- |
| Freqtrade official strategy examples | https://github.com/freqtrade/freqtrade-strategies | Baseline examples, futures samples, callback patterns |
| Official futures examples | https://github.com/freqtrade/freqtrade-strategies/tree/main/user_data/strategies/futures | Short/leverage examples, volatility systems, supertrend, ADX/SMA |
| Freqtrade strategy docs | https://www.freqtrade.io/en/stable/strategy-customization/ | Correct strategy API, informative pairs, lookahead warnings |
| Freqtrade callbacks docs | https://www.freqtrade.io/en/stable/strategy-callbacks/ | `custom_exit`, `custom_stake_amount`, `adjust_trade_position`, `leverage` |
| NostalgiaForInfinity | https://github.com/iterativv/NostalgiaForInfinity | Multi-timeframe filters, market-mode exits, pump/dump protections, pairlist discipline |
| NFI documentation | https://iterativv.github.io/NostalgiaForInfinity/ | Operational notes, update workflow, community process |
| Freqtrade Discord / GitHub issues | https://github.com/freqtrade/freqtrade/issues | Bug reports, migration notes, strategy API edge cases |
| TradingView public scripts | https://www.tradingview.com/scripts/ | Idea source only; reimplement and verify independently |

## Patterns Worth Testing

- Multi-timeframe confirmation: keep the current 15m signal engine, but test
  additional 1h/4h state such as higher-timeframe EMA slope, RSI regime, and
  range expansion.
- Futures volatility system: test ATR/range-expansion entries separately from
  pullback entries. This should be a new isolated strategy, not mixed into the
  current moonshot model until proven.
- Chandelier-style regime exits: NFI uses a chandelier direction concept in
  higher timeframes. A local version may be useful as a faster loss exit before
  a full stoploss.
- OBV/volume confirmation: official trend-following examples use volume/OBV to
  confirm direction. This may help avoid thin continuation entries.
- Pairlist discipline: NFI favors larger dynamic universes and blacklist rules.
  Our offline research should reproduce this mechanically with a local volume
  and volatility ranking before adding pairs.
- Strict DCA logic: Freqtrade warns that loose `adjust_trade_position` logic can
  re-enter too often. Our DCA code already checks open orders, entry count,
  trend break, stabilization, and ATR; keep that discipline.

## Rejected First Adaptation

I tested a community-inspired guard variant after reading the official futures
examples and NFI-style pump/dump protections. The experiment added 1h range,
wick, and clustered counter-candle filters on top of the moonshot strategy.

Result:

| Slice | Strategy under test | Full return | CAGR | Max drawdown | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| Long | `Intp20LongCommunityGuardDcaStrategy` | 205.58% | 45.36% | 24.27% | Reject: same as moonshot, no risk improvement |
| Short | `Intp20ShortCommunityGuardDcaStrategy` | 81.60% | 22.11% | 16.59% | Reject: same as moonshot, no risk improvement |

The filters did not catch the stoploss clusters that matter in this dataset.
The likely next useful adaptation is not more entry filtering, but a separate
exit/risk module: chandelier/ATR loss exit, pair-specific stop caps, or a
volatility breakout system tested as its own strategy.

## Rejected Next-Stage Adaptations

- Standalone volatility breakout: `Intp20VolatilityBreakoutStrategy` tested the
  official futures volatility-system idea as a separate trend breakout stream.
  It lost 24.14% with 44.51% max drawdown over 2023-06-05 to 2026-05-31. The
  high win rate was not useful because a small number of full stoplosses erased
  the winners. The class was removed.
- Chandelier/ATR early loss exits reduced some drawdown on shorts, but killed
  long-side expectancy and did not improve the retained long engine.
- Pair-weighted short sizing did not improve the short hedge engine enough to
  justify extra complexity.

## Next Research Queue

1. Test an explicit loss-avoidance module for the retained long top6: use
   trade-context features around the six retained stoplosses, not broad entry
   filters that leave results unchanged.
2. Re-rank pairs monthly by local volume, ATR, and trend strength, then compare
   static top6 versus rolling pair selection.
3. Test OBV/volume confirmation only on losing long pairs first: `APT`, `ETC`,
   `XLM`, `XTZ`.
4. Only after rule-based variants plateau, test FreqAI-style regime
   classification. Do not use model output directly for entries until leakage
   and walk-forward stability are checked.
