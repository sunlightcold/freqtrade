#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/data/app/freqtrade}"
TARGET="${ROOT}/server-deploy"
RESET_DB="${RESET_DB:-1}"
STOP_LEGACY_BOTS="${STOP_LEGACY_BOTS:-1}"

CONFIG="config_binance_stage31_relative_shock_20pair_1000u_dryrun.json"
STRATEGY="Intp20Stage31RelativeShockStrategy"
RUNTIME_API_CONFIG="config_stage31_runtime_api.json"

if [ ! -f "${TARGET}/docker-compose.yml" ]; then
  echo "Missing deployment directory: ${TARGET}" >&2
  exit 1
fi

if [ ! -f "${TARGET}/.env" ]; then
  cp "${TARGET}/.env.example" "${TARGET}/.env"
fi

set_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "${TARGET}/.env"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${TARGET}/.env"
  else
    printf '\n%s=%s\n' "${key}" "${value}" >> "${TARGET}/.env"
  fi
}

stop_project() {
  local directory="$1"
  local project="$2"
  if [ -f "${directory}/docker-compose.yml" ]; then
    (cd "${directory}" && docker compose -p "${project}" down --remove-orphans)
  fi
}

set_env FREQTRADE_CONFIG "${CONFIG}"
set_env FREQTRADE_STRATEGY "${STRATEGY}"
set_env FREQTRADE_API_BIND "0.0.0.0"

if [ -z "${WEBUI_ORIGIN:-}" ]; then
  PUBLIC_IP="$(curl -4fsS --max-time 10 https://api.ipify.org || true)"
  if [ -n "${PUBLIC_IP}" ]; then
    WEBUI_ORIGIN="http://${PUBLIC_IP}:8081"
  else
    WEBUI_ORIGIN="*"
  fi
fi

python3 - "${TARGET}/user_data/${RUNTIME_API_CONFIG}" "${WEBUI_ORIGIN}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
origin = sys.argv[2]
path.write_text(
    json.dumps({"api_server": {"CORS_origins": [origin]}}, indent=2) + "\n",
    encoding="utf-8",
)
PY

set_env FREQTRADE_EXTRA_CONFIG_ARGS \
  "--config /freqtrade/user_data/${RUNTIME_API_CONFIG}"

if [ "${RESET_DB}" = "1" ] && [ -f "${TARGET}/user_data/tradesv3.sqlite" ]; then
  mkdir -p "${TARGET}/backups"
  cp "${TARGET}/user_data/tradesv3.sqlite" \
    "${TARGET}/backups/tradesv3-before-stage31-$(date +%Y%m%d-%H%M%S).sqlite"
  rm -f "${TARGET}/user_data/tradesv3.sqlite" \
    "${TARGET}/user_data/tradesv3.sqlite-shm" \
    "${TARGET}/user_data/tradesv3.sqlite-wal"
fi

if [ "${STOP_LEGACY_BOTS}" = "1" ]; then
  stop_project "${ROOT}/server-deploy-stage20" "freqtrade-stage20"
  stop_project "${ROOT}/server-deploy-stage24" "freqtrade-stage24"
fi

(
  cd "${TARGET}"
  docker compose -p server-deploy pull freqtrade
  docker compose -p server-deploy up -d --remove-orphans freqtrade
  docker compose -p server-deploy ps freqtrade
)

API_PORT="$(sed -n 's/^FREQTRADE_API_PORT=//p' "${TARGET}/.env" | tail -1)"
API_PORT="${API_PORT:-8080}"
for _ in $(seq 1 24); do
  if curl -fsS --max-time 5 "http://127.0.0.1:${API_PORT}/api/v1/ping"; then
    break
  fi
  sleep 5
done
curl -fsS --max-time 5 "http://127.0.0.1:${API_PORT}/api/v1/ping" >/dev/null
printf '\nStage31 dry-run is online on API port %s.\n' "${API_PORT}"
printf 'Allowed WebUI origin: %s\n' "${WEBUI_ORIGIN}"
