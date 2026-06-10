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
FREQTRADE_IMAGE=ghcr.io/sunlightcold/freqtrade:develop
```

This image is produced by the fork workflow `.github/workflows/fork-ghcr-image.yml`.
Every push to `develop` publishes:

- `ghcr.io/sunlightcold/freqtrade:develop`
- `ghcr.io/sunlightcold/freqtrade:sha-<commit>`
- `ghcr.io/sunlightcold/freqtrade:latest` when the Docker tag is `develop`

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

## Server Docker Deployment With Web UI

On the server, install Docker and the Docker Compose plugin first. Then clone or upload this repository to the server.

Copy the server env template:

```bash
cp .env.server.example .env
```

Edit `.env`:

```text
FREQTRADE_IMAGE=ghcr.io/sunlightcold/freqtrade:develop
FREQTRADE_API_BIND=0.0.0.0
FREQTRADE_API_PORT=8080
FREQUI_BIND=0.0.0.0
FREQUI_PORT=8081
FREQTRADE_API_PASSWORD=replace-with-a-strong-password
FREQTRADE_API_JWT_SECRET_KEY=replace-with-a-long-random-jwt-secret
FREQTRADE_API_WS_TOKEN=replace-with-a-long-random-websocket-token
```

Copy the server API override template:

```bash
cp user_data/config_server_api_override.example.json user_data/config_server_api_override.json
```

Edit `user_data/config_server_api_override.json`:

```json
{
  "api_server": {
    "CORS_origins": [
      "http://YOUR_SERVER_IP:8081",
      "https://YOUR_DOMAIN"
    ],
    "username": "freqtrader",
    "password": "replace-with-a-strong-password",
    "jwt_secret_key": "replace-with-a-long-random-jwt-secret",
    "ws_token": "replace-with-a-long-random-websocket-token"
  }
}
```

Use the same password/JWT/WebSocket values in `.env` and `config_server_api_override.json`.

Start the bot and Web UI:

```bash
docker compose pull
docker compose up -d
```

If the server cannot pull from GHCR, either make the GitHub package public or run
`docker login ghcr.io` on the server with a GitHub token that has package read access.

Open:

- Built-in Freqtrade UI/API: `http://YOUR_SERVER_IP:8080`
- Standalone FreqUI static site: `http://YOUR_SERVER_IP:8081`

Check status and logs:

```bash
docker compose ps
docker compose logs -f freqtrade
```

Install or refresh UI files:

```bash
docker compose run --rm frequi-init
docker compose restart freqtrade frequi
```

Update later:

```bash
docker compose pull
docker compose up -d
```

For a public server, prefer a reverse proxy with HTTPS and firewall allowlisting. If exposing raw ports, open only `8080` and `8081` to your own IP.

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
