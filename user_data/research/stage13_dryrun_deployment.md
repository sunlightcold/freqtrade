# Stage 13 Dry-Run Deployment

This deployment profile runs the validated 20-pair Stage-13 strategy in dry-run mode.

## Recommended 200U Local Run

```powershell
.\.venv\Scripts\freqtrade.exe trade -c user_data\config_binance_stage13_validated_20pair_200u_dryrun.json --strategy Intp20Stage13Validated20Strategy
```

UI/API:

- API server: `http://127.0.0.1:8080`
- Username: `freqtrader`
- Password: `SuperSecurePassword`

If the UI page says it is not installed, install it once:

```powershell
.\.venv\Scripts\freqtrade.exe install-ui
```

Then restart the bot and refresh the page.

## Docker Compose Run

Copy the example env file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set your image:

```text
FREQTRADE_IMAGE=your-registry/your-freqtrade:latest
```

The default compose profile uses:

```text
FREQTRADE_CONFIG=config_binance_stage13_validated_20pair_200u_dryrun.json
FREQTRADE_STRATEGY=Intp20Stage13Validated20Strategy
FREQTRADE_API_PORT=8080
FREQUI_PORT=8081
```

Start:

```powershell
docker compose up -d
```

Install/update UI files only:

```powershell
docker compose run --rm frequi-init
```

View logs:

```powershell
docker compose logs -f freqtrade
```

Stop:

```powershell
docker compose down
```

## 10,000U Research Profile

To replay the research-sized dry-run profile instead of the 200U profile, set this in `.env`:

```text
FREQTRADE_CONFIG=config_binance_stage13_validated_20pair_dryrun.json
```

## Preflight Checklist

- Confirm the exchange account is in Binance futures one-way mode.
- Keep `dry_run = true` until the dry-run has enough forward evidence.
- Keep isolated futures margin.
- Do not raise `stake_amount` or `max_open_trades` on a 200U account without a new backtest.
- Expect the UI to be English-first; FreqUI is not fully localized to Chinese.
