# Stage 12 Dry-Run Universe

This note defines which pairs are allowed into the current dry-run bot.

Admission rule:

- The pair must have native Freqtrade Stage-12 backtest evidence.
- It must have at least one real Stage-12 trade in the main validation windows.
- Its aggregate contribution across `2024`, `2025`, and `2026-01..05` must be
  positive.

This deliberately excludes pairs that only passed the template scanner. The
expanded liquid universe is useful research input, but those pairs need Stage-13
native backtests before they can be promoted into the live dry-run config.

## Max Validated Dry-Run Pool

Default config:

- `user_data/config_binance_stage12_validated_14pair_dryrun.json`

| Rank | Pair | Main Profit USDT | Main Trades | Note |
| ---: | --- | ---: | ---: | --- |
| 1 | `MKR/USDT:USDT` | +15408.95 | 419 | Strongest aggregate, no 2026 trades in tested slice |
| 2 | `SOL/USDT:USDT` | +9097.44 | 220 | Strong across all main windows |
| 3 | `XLM/USDT:USDT` | +7691.38 | 135 | Strong 2024, positive later |
| 4 | `AAVE/USDT:USDT` | +7363.42 | 118 | Strong 2024 and 2026 |
| 5 | `XTZ/USDT:USDT` | +6450.27 | 142 | Improved by Stage-12 BTC/XTZ ROC filter |
| 6 | `XRP/USDT:USDT` | +5440.73 | 108 | Strong 2025 and 2026 |
| 7 | `ETH/USDT:USDT` | +4096.81 | 49 | Low trade count but positive |
| 8 | `SUI/USDT:USDT` | +3490.48 | 146 | Good main-window aggregate, weak 2023H2 OOS |
| 9 | `ETC/USDT:USDT` | +3338.06 | 62 | Positive but lower frequency |
| 10 | `LTC/USDT:USDT` | +3059.13 | 227 | Active, steady aggregate |
| 11 | `COMP/USDT:USDT` | +3017.74 | 44 | Watchlist: negative in 2026 slice |
| 12 | `OP/USDT:USDT` | +2637.01 | 115 | Watchlist: negative in 2024 |
| 13 | `APT/USDT:USDT` | +1499.30 | 62 | Watchlist: negative in 2025 |
| 14 | `DOGE/USDT:USDT` | +1056.91 | 61 | Positive but smaller contribution |

Operational settings:

- Strategy: `Intp20Stage12XtzCoreRocFilterStrategy`
- Timeframe: `1m`
- Starting dry-run wallet: `10000 USDT`
- Stake amount: `5000 USDT`
- Max open trades: `8`
- Dry-run API port: `8080`

## Core 10-Pair Alternative

Secondary config:

- `user_data/config_binance_stage12_core_10pair_dryrun.json`

This keeps only the top 10 validated contributors and removes `COMP`, `OP`,
`APT`, and `DOGE`. Use it when drawdown stability is more important than maximum
pair coverage.

## Excluded For Now

Zero-trade Stage-12 pairs:

- `AVAX/USDT:USDT`
- `BCH/USDT:USDT`
- `BNB/USDT:USDT`
- `BTC/USDT:USDT`
- `LINK/USDT:USDT`
- `TRX/USDT:USDT`

They had complete data and were in the whitelist, but the current Stage-12 class
had no active entry path for them in the native validation.

Expanded liquid research candidates:

- `ADA`, `DOT`, `ATOM`, `ARB`, `NEAR`, `UNI`, `FIL`, `INJ`, `ALGO`, `HBAR`,
  `FET`, `GALA`, `RUNE`, `ICP`, `SAND`, `MANA`, `1000SHIB`, `1000PEPE`

These have newly downloaded 3-year `1m` data and template-scan evidence, but
they are not admitted to the dry-run bot until a Stage-13 native backtest passes.
