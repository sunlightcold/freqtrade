#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/data/apps/freqtrade}"
RESET_DB="${RESET_DB:-0}"
RESTART="${RESTART:-1}"

SOURCE="${ROOT}/server-deploy"

copy_runtime_files() {
  local target="$1"
  mkdir -p "${target}/user_data/strategies"

  cp -f "${SOURCE}/user_data/strategies/Intp20Stage7AggressivePortfolioStrategy.py" \
    "${target}/user_data/strategies/"
  cp -f "${SOURCE}/user_data/strategies/Intp20Stage14CommunityBoostStrategy.py" \
    "${target}/user_data/strategies/"
  cp -f "${SOURCE}/user_data/strategies/Intp20Stage15HighTurnoverScalpStrategy.py" \
    "${target}/user_data/strategies/"
  cp -f "${SOURCE}/user_data/strategies/Intp20Stage16StressPrunedScalpStrategy.py" \
    "${target}/user_data/strategies/"
  cp -f "${SOURCE}/user_data/strategies/Intp20Stage25HfCandidateStrategies.py" \
    "${target}/user_data/strategies/"

  cp -f "${SOURCE}/user_data/config_binance_stage25_composite_scalp_20pair_1000u_dryrun.json" \
    "${target}/user_data/"
  cp -f "${SOURCE}/user_data/config_binance_stage26_reversion_shock_20pair_1000u_dryrun.json" \
    "${target}/user_data/"
  cp -f "${SOURCE}/user_data/config_binance_stage27_quality_rotation_20pair_1000u_dryrun.json" \
    "${target}/user_data/"
}

set_env() {
  local env_file="$1"
  local key="$2"
  local value="$3"
  if grep -q "^${key}=" "${env_file}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${env_file}"
  else
    printf '\n%s=%s\n' "${key}" "${value}" >> "${env_file}"
  fi
}

clear_extra_config() {
  local env_file="$1"
  if grep -q '^FREQTRADE_EXTRA_CONFIG_ARGS=' "${env_file}"; then
    sed -i 's|^FREQTRADE_EXTRA_CONFIG_ARGS=.*|FREQTRADE_EXTRA_CONFIG_ARGS=|' "${env_file}"
  else
    printf '\nFREQTRADE_EXTRA_CONFIG_ARGS=\n' >> "${env_file}"
  fi
}

backup_and_reset_db() {
  local target="$1"
  if [ "${RESET_DB}" != "1" ]; then
    return
  fi
  mkdir -p "${target}/backups"
  if [ -f "${target}/user_data/tradesv3.sqlite" ]; then
    cp "${target}/user_data/tradesv3.sqlite" \
      "${target}/backups/tradesv3-before-stage25-27-$(date +%Y%m%d-%H%M%S).sqlite"
  fi
  rm -f "${target}/user_data/tradesv3.sqlite" \
    "${target}/user_data/tradesv3.sqlite-shm" \
    "${target}/user_data/tradesv3.sqlite-wal"
}

configure_bot() {
  local target="$1"
  local project="$2"
  local config="$3"
  local strategy="$4"
  local bind="$5"
  local port="$6"

  if [ ! -d "${target}" ]; then
    echo "Missing deploy directory: ${target}" >&2
    exit 1
  fi
  if [ ! -f "${target}/.env" ]; then
    cp "${target}/.env.example" "${target}/.env"
  fi

  copy_runtime_files "${target}"
  set_env "${target}/.env" FREQTRADE_CONFIG "${config}"
  set_env "${target}/.env" FREQTRADE_STRATEGY "${strategy}"
  set_env "${target}/.env" FREQTRADE_API_BIND "${bind}"
  set_env "${target}/.env" FREQTRADE_API_PORT "${port}"
  clear_extra_config "${target}/.env"
  backup_and_reset_db "${target}"

  if [ "${RESTART}" = "1" ]; then
    (
      cd "${target}"
      docker compose -p "${project}" pull freqtrade
      docker compose -p "${project}" up -d --remove-orphans --no-deps freqtrade
    )
  fi
}

configure_bot \
  "${ROOT}/server-deploy" \
  "server-deploy" \
  "config_binance_stage25_composite_scalp_20pair_1000u_dryrun.json" \
  "Intp20Stage25CompositeScalpStrategy" \
  "127.0.0.1" \
  "8080"

configure_bot \
  "${ROOT}/server-deploy-stage20" \
  "freqtrade-stage20" \
  "config_binance_stage26_reversion_shock_20pair_1000u_dryrun.json" \
  "Intp20Stage26ReversionShockStrategy" \
  "0.0.0.0" \
  "18080"

configure_bot \
  "${ROOT}/server-deploy-stage24" \
  "freqtrade-stage24" \
  "config_binance_stage27_quality_rotation_20pair_1000u_dryrun.json" \
  "Intp20Stage27QualityRotationScalpStrategy" \
  "0.0.0.0" \
  "18085"

echo "Applied Stage25/26/27 overrides."
echo "Stage25: ${ROOT}/server-deploy -> 127.0.0.1:8080"
echo "Stage26: ${ROOT}/server-deploy-stage20 -> 0.0.0.0:18080"
echo "Stage27: ${ROOT}/server-deploy-stage24 -> 0.0.0.0:18085"
