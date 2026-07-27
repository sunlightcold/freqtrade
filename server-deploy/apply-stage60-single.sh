#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/data/app/freqtrade}"
DEPLOY="${ROOT}/server-deploy"
PROJECT="server-deploy"
RESET_DB="${RESET_DB:-0}"

CONFIG="config_binance_stage60_blended_shock_41pair_1000u_dryrun.json"
STRATEGY="Intp20Stage60BlendedShockStrategy"

set_env() {
  local key="$1"
  local value="$2"
  local env_file="${DEPLOY}/.env"

  if grep -q "^${key}=" "${env_file}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${env_file}"
  else
    printf '\n%s=%s\n' "${key}" "${value}" >> "${env_file}"
  fi
}

ensure_secret() {
  local key="$1"
  local placeholder="$2"
  local bytes="$3"
  local current

  current="$(sed -n "s/^${key}=//p" "${DEPLOY}/.env" | tail -1)"
  if [ -z "${current}" ] || [ "${current}" = "${placeholder}" ]; then
    set_env "${key}" "$(openssl rand -hex "${bytes}")"
  fi
}

if [ ! -d "${DEPLOY}" ]; then
  echo "Missing deploy directory: ${DEPLOY}" >&2
  exit 1
fi
if [ ! -f "${DEPLOY}/user_data/${CONFIG}" ]; then
  echo "Missing Stage60 config. Run git pull first: ${DEPLOY}/user_data/${CONFIG}" >&2
  exit 1
fi
if [ ! -f "${DEPLOY}/user_data/strategies/${STRATEGY}.py" ]; then
  echo "Missing Stage60 strategy. Run git pull first: ${STRATEGY}.py" >&2
  exit 1
fi
if [ ! -f "${DEPLOY}/user_data/strategies/Intp20Stage31RelativeShockStrategy.py" ]; then
  echo "Missing Stage60 base strategy: Intp20Stage31RelativeShockStrategy.py" >&2
  exit 1
fi

if [ ! -f "${DEPLOY}/.env" ]; then
  cp "${DEPLOY}/.env.example" "${DEPLOY}/.env"
fi

set_env FREQTRADE_CONFIG "${CONFIG}"
set_env FREQTRADE_STRATEGY "${STRATEGY}"
set_env FREQTRADE_API_BIND "127.0.0.1"
set_env FREQTRADE_API_PORT "8080"
set_env FREQTRADE_EXTRA_CONFIG_ARGS ""
ensure_secret FREQTRADE_API_PASSWORD replace-with-a-strong-password 24
ensure_secret FREQTRADE_API_JWT_SECRET_KEY replace-with-a-long-random-jwt-secret 32
ensure_secret FREQTRADE_API_WS_TOKEN replace-with-a-long-random-websocket-token 32

cd "${DEPLOY}"

if [ "${RESET_DB}" = "1" ]; then
  docker compose -p "${PROJECT}" stop freqtrade >/dev/null 2>&1 || true
  mkdir -p backups
  if [ -f user_data/tradesv3.sqlite ]; then
    cp user_data/tradesv3.sqlite \
      "backups/tradesv3-before-stage60-$(date +%Y%m%d-%H%M%S).sqlite"
  fi
  rm -f user_data/tradesv3.sqlite \
    user_data/tradesv3.sqlite-shm \
    user_data/tradesv3.sqlite-wal
fi

docker compose -p "${PROJECT}" pull freqtrade
docker compose -p "${PROJECT}" up -d --remove-orphans --no-deps freqtrade

for _ in $(seq 1 60); do
  if curl -fsS --max-time 3 http://127.0.0.1:8080/api/v1/ping >/dev/null; then
    docker compose -p "${PROJECT}" ps freqtrade
    echo "Stage60 API: pong"
    echo "Existing FreqUI remains unchanged; no second WebUI was started."
    exit 0
  fi
  sleep 2
done

echo "Stage60 did not expose its API within 120 seconds." >&2
docker compose -p "${PROJECT}" logs --tail=80 --no-color freqtrade >&2
exit 1
