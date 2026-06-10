# Ready Server Deploy Package

This folder is ready to copy to a Linux server and run with Docker Compose.

## Start

```bash
cd server-deploy
# Optional: copy user_data/config_server_api_override.example.json to
# user_data/config_server_api_override.json if you need a private override file.
docker compose pull
docker compose up -d
```

The bot image is `ghcr.io/sunlightcold/freqtrade:develop`, built by this fork's GitHub Actions.
If the server cannot pull from GHCR, make the package public or run `docker login ghcr.io`
with a GitHub token that has package read access.

## Access

- Built-in Freqtrade UI/API: http://YOUR_SERVER_IP_OR_DOMAIN:8080
- Standalone FreqUI: http://YOUR_SERVER_IP_OR_DOMAIN:8081
- Credentials are loaded from `.env`.

## Logs

```bash
docker compose ps
docker compose logs -f freqtrade
```

Keep `dry_run=true` until forward validation is stable.
