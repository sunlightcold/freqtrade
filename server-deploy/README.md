# Server Deploy

这个目录是服务器部署入口。后续部署、升级、迁移都优先在这里执行，不再使用仓库根目录的 compose。

## 首次启动

```bash
cd server-deploy
cp .env.example .env
nano .env
docker compose pull
docker compose up -d
```

至少替换 `.env` 里的密码和密钥：

```env
FREQTRADE_API_PASSWORD=replace-with-a-strong-password
FREQTRADE_API_JWT_SECRET_KEY=replace-with-a-long-random-jwt-secret
FREQTRADE_API_WS_TOKEN=replace-with-a-long-random-websocket-token
```

生成随机密钥：

```bash
openssl rand -hex 32
```

## 升级

```bash
cd server-deploy
git pull
docker compose pull
docker compose up -d
docker compose ps -a
```

## 切换到 Stage17 1000U 模拟盘

服务器只需要拉取仓库并用命令更新 `.env`，不需要手动上传文件：

```bash
cd /path/to/freqtrade/server-deploy
docker compose down
mkdir -p backups
cp user_data/tradesv3.sqlite backups/tradesv3-before-stage17-$(date +%Y%m%d-%H%M%S).sqlite 2>/dev/null || true
rm -f user_data/tradesv3.sqlite user_data/tradesv3.sqlite-shm user_data/tradesv3.sqlite-wal

cd /path/to/freqtrade
git pull --ff-only
cd server-deploy

set_env() {
  key="$1"
  value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

set_env FREQTRADE_CONFIG config_binance_stage17_turbo_adaptive_scalp_20pair_1000u_dryrun.json
set_env FREQTRADE_STRATEGY Intp20Stage17TurboAdaptiveScalpStrategy
docker compose pull
docker compose up -d --remove-orphans
docker compose logs --tail=100 -f freqtrade
```

Stage17 配置为 1000 USDT 模拟本金，单笔 90 USDT，最多 10 个同时持仓，手续费按单边 0.05% 写入配置。保持 `dry_run=true`，先看前向模拟盘表现。

## 切换到 Stage18 无 Key 热点模拟盘

Stage18 是独立策略，不覆盖 Stage17。热点采集器只使用公开接口，不需要 API key，且只写入本地 JSON 缓存；策略本身不会在下单流程里请求外部 API。

```bash
cd /path/to/freqtrade/server-deploy
docker compose --profile stage18 down
mkdir -p backups
cp user_data/tradesv3.sqlite backups/tradesv3-before-stage18-$(date +%Y%m%d-%H%M%S).sqlite 2>/dev/null || true
rm -f user_data/tradesv3.sqlite user_data/tradesv3.sqlite-shm user_data/tradesv3.sqlite-wal

cd /path/to/freqtrade
git pull --ff-only
cd server-deploy

set_env() {
  key="$1"
  value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

set_env FREQTRADE_CONFIG config_binance_stage18_no_key_hotspot_20pair_1000u_dryrun.json
set_env FREQTRADE_STRATEGY Intp20Stage18NoKeyHotspotStrategy
set_env STAGE18_HOTSPOT_INTERVAL_SECONDS 300
set_env STAGE18_HOTSPOT_TIMEOUT_SECONDS 8

docker compose --profile stage18 pull
docker compose --profile stage18 up -d
docker compose logs --tail=100 -f stage18-hotspot
docker compose logs --tail=100 -f freqtrade
```

如果只想先生成一次热点缓存做连通性测试：

```bash
docker compose --profile stage18 run --rm stage18-hotspot \
  python /freqtrade/user_data/scripts/fetch_stage18_hotspot_cache.py \
  --config /freqtrade/user_data/config_binance_stage18_no_key_hotspot_20pair_1000u_dryrun.json \
  --output /freqtrade/user_data/hotspot/stage18_hotspot_cache.json
```

## 切换到 Stage19 激进新币模拟盘

Stage19 是独立策略，不覆盖 Stage17/Stage18。它使用 38 对合约扩展池，`startup_candle_count=240`，适合对新币/短历史 1m K 线做近期回测和前向模拟；风险预算更高，先保持 `dry_run=true`。

```bash
cd /path/to/freqtrade/server-deploy
docker compose --profile stage19 down
mkdir -p backups
cp user_data/tradesv3.sqlite backups/tradesv3-before-stage19-$(date +%Y%m%d-%H%M%S).sqlite 2>/dev/null || true
rm -f user_data/tradesv3.sqlite user_data/tradesv3.sqlite-shm user_data/tradesv3.sqlite-wal

cd /path/to/freqtrade
git pull --ff-only
cd server-deploy

set_env() {
  key="$1"
  value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

set_env FREQTRADE_CONFIG config_binance_stage19_aggressive_newcoin_38pair_1000u_dryrun.json
set_env FREQTRADE_STRATEGY Intp20Stage19AggressiveNewcoinStrategy
set_env STAGE19_HOTSPOT_INTERVAL_SECONDS 240
set_env STAGE19_HOTSPOT_TIMEOUT_SECONDS 8

docker compose --profile stage19 pull
docker compose --profile stage19 up -d
docker compose logs --tail=100 -f stage19-hotspot
docker compose logs --tail=100 -f freqtrade
```

如果只想先跑一次热点缓存连通性测试：

```bash
docker compose --profile stage19 run --rm stage19-hotspot \
  python /freqtrade/user_data/scripts/fetch_stage18_hotspot_cache.py \
  --config /freqtrade/user_data/config_binance_stage19_aggressive_newcoin_38pair_1000u_dryrun.json \
  --output /freqtrade/user_data/hotspot/stage18_hotspot_cache.json
```

新增未在配置中的新币时，不需要长历史数据，但需要至少下载 240 根以上 1m K 线才能触发策略启动。回测示例：

```bash
freqtrade download-data \
  --config user_data/config_binance_stage19_aggressive_newcoin_38pair_200u_dryrun.json \
  --timeframes 1m \
  --pairs NEWCOIN/USDT:USDT \
  --timerange 20260601-

freqtrade backtesting \
  --config user_data/config_binance_stage19_aggressive_newcoin_38pair_200u_dryrun.json \
  --strategy Intp20Stage19AggressiveNewcoinStrategy \
  --pairs NEWCOIN/USDT:USDT \
  --timerange 20260601-
```

## 切换到 Stage20 自适应学习模拟盘

Stage20 是独立策略，不覆盖 Stage19。它仍然使用 38 对 Binance U 本位合约、1m 周期、1000 USDT 模拟本金、单笔 90 USDT、最多 10 个同时持仓，手续费按单边 0.05% 写入配置。Stage20 的新增学习层不按币种或月份拟合：短空和 pull 学习入口默认只观察不实盘，当前只允许通过快慢滚动记忆、胜率和 regime 过滤的动量多头学习入口参与。

### 并行部署 Stage20，不影响当前模拟盘

当前服务器仓库路径为 `/data/apps/freqtrade` 时，用独立 compose 项目和独立部署目录运行 Stage20。这样不会重建现有 `server-deploy` 里的模拟盘，Stage20 会使用自己的数据库和 Freqtrade API 端口。WebUI 使用现有 `server-deploy` 的 FreqUI，在里面添加 Stage20 这个 Bot。

```bash
cd /data/apps/freqtrade
git pull --ff-only

rsync -a --delete \
  --exclude '.env' \
  --exclude 'user_data/tradesv3.sqlite*' \
  --exclude 'user_data/logs/*' \
  server-deploy/ server-deploy-stage20/

cd /data/apps/freqtrade/server-deploy-stage20
cp -n /data/apps/freqtrade/server-deploy/.env .env 2>/dev/null || cp .env.example .env

set_env() {
  key="$1"
  value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

set_env FREQTRADE_IMAGE ghcr.io/sunlightcold/freqtrade:develop
set_env FREQTRADE_CONFIG config_binance_stage20_adaptive_regime_newcoin_38pair_1000u_dryrun.json
set_env FREQTRADE_STRATEGY Intp20Stage20AdaptiveRegimeNewcoinStrategy
set_env STAGE20_HOTSPOT_INTERVAL_SECONDS 240
set_env STAGE20_HOTSPOT_TIMEOUT_SECONDS 8
set_env FREQTRADE_API_BIND 0.0.0.0
set_env FREQTRADE_API_PORT 18080
set_env FREQTRADE_EXCHANGE_KEY ""
set_env FREQTRADE_EXCHANGE_SECRET ""
set_env FREQTRADE_EXTRA_CONFIG_ARGS "--config /freqtrade/user_data/config_server_api_override.json"

SERVER_ORIGIN="http://82.158.225.90:8081"
python3 - "$SERVER_ORIGIN" <<'PY'
import json
import sys
from pathlib import Path

origin = sys.argv[1]
path = Path("user_data/config_server_api_override.json")
example = Path("user_data/config_server_api_override.example.json")
data = json.loads(
    path.read_text(encoding="utf-8")
    if path.exists()
    else example.read_text(encoding="utf-8")
)
api_server = data.setdefault("api_server", {})
api_server["CORS_origins"] = [origin]
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

docker compose -p freqtrade-stage20 --profile stage20 pull
docker compose -p freqtrade-stage20 --profile stage20 up -d --no-deps freqtrade stage20-hotspot
docker compose -p freqtrade-stage20 --profile stage20 ps
```

现有 WebUI:

```text
http://服务器IP:8081
```

在 FreqUI 里添加一个 Bot：

```text
Bot Name: stage20
API Url: http://服务器IP:18080
Username: .env 里的 FREQTRADE_API_USERNAME
Password: .env 里的 FREQTRADE_API_PASSWORD
```

`config_server_api_override.json` 里需要允许现有 WebUI 来源，例如 `http://82.158.225.90:8081`。如果服务器 IP 或域名变了，按下面更新：

```bash
cd /data/apps/freqtrade/server-deploy-stage20
SERVER_ORIGIN="http://82.158.225.90:8081"
python3 - "$SERVER_ORIGIN" <<'PY'
import json
import sys
from pathlib import Path

origin = sys.argv[1]
path = Path("user_data/config_server_api_override.json")
example = Path("user_data/config_server_api_override.example.json")
data = json.loads(
    path.read_text(encoding="utf-8")
    if path.exists()
    else example.read_text(encoding="utf-8")
)
api_server = data.setdefault("api_server", {})
api_server["CORS_origins"] = [origin]
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
docker compose -p freqtrade-stage20 --profile stage20 up -d --no-deps freqtrade
```

如果只重启 Stage20，不影响原策略：

```bash
cd /data/apps/freqtrade/server-deploy-stage20
docker compose -p freqtrade-stage20 --profile stage20 up -d --no-deps freqtrade stage20-hotspot
```

如果旧版本 `.env` 里固定过容器名，可能出现 `frequi-stage20` / `freqtrade-stage20` / `freqtrade-permissions-init-stage20` 已存在的冲突。升级到新版 compose 后先清理旧容器名，并移除第二个 WebUI：

```bash
cd /data/apps/freqtrade/server-deploy-stage20

docker rm -f frequi-stage20 freqtrade-stage20 freqtrade-permissions-init-stage20 stage20-hotspot-parallel 2>/dev/null || true

sed -i '/^FREQTRADE_CONTAINER_NAME=/d' .env
sed -i '/^FREQUI_CONTAINER_NAME=/d' .env
sed -i '/^PERMISSIONS_INIT_CONTAINER_NAME=/d' .env
sed -i '/^STAGE20_HOTSPOT_CONTAINER_NAME=/d' .env
sed -i '/^FREQUI_BIND=/d' .env
sed -i '/^FREQUI_PORT=/d' .env

docker compose -p freqtrade-stage20 --profile stage20 up -d --no-deps freqtrade stage20-hotspot
```

停掉 Stage20，也不影响原策略：

```bash
cd /data/apps/freqtrade/server-deploy-stage20
docker compose -p freqtrade-stage20 --profile stage20 down
```

```bash
cd /path/to/freqtrade/server-deploy
docker compose --profile stage20 down
mkdir -p backups
cp user_data/tradesv3.sqlite backups/tradesv3-before-stage20-$(date +%Y%m%d-%H%M%S).sqlite 2>/dev/null || true
rm -f user_data/tradesv3.sqlite user_data/tradesv3.sqlite-shm user_data/tradesv3.sqlite-wal

cd /path/to/freqtrade
git pull --ff-only
cd server-deploy

set_env() {
  key="$1"
  value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

set_env FREQTRADE_CONFIG config_binance_stage20_adaptive_regime_newcoin_38pair_1000u_dryrun.json
set_env FREQTRADE_STRATEGY Intp20Stage20AdaptiveRegimeNewcoinStrategy
set_env STAGE20_HOTSPOT_INTERVAL_SECONDS 240
set_env STAGE20_HOTSPOT_TIMEOUT_SECONDS 8

docker compose --profile stage20 pull
docker compose --profile stage20 up -d
docker compose logs --tail=100 -f stage20-hotspot
docker compose logs --tail=100 -f freqtrade
```

如果只想先跑一次热点缓存连通性测试：

```bash
docker compose --profile stage20 run --rm stage20-hotspot \
  python /freqtrade/user_data/scripts/fetch_stage18_hotspot_cache.py \
  --config /freqtrade/user_data/config_binance_stage20_adaptive_regime_newcoin_38pair_1000u_dryrun.json \
  --output /freqtrade/user_data/hotspot/stage18_hotspot_cache.json
```

新增未在配置中的新币时，仍然只需要足够短历史启动策略；至少下载 240 根以上 1m K 线。回测示例：

```bash
freqtrade download-data \
  --config user_data/config_binance_stage20_adaptive_regime_newcoin_38pair_200u_dryrun.json \
  --timeframes 1m \
  --pairs NEWCOIN/USDT:USDT \
  --timerange 20260601-

freqtrade backtesting \
  --config user_data/config_binance_stage20_adaptive_regime_newcoin_38pair_200u_dryrun.json \
  --strategy Intp20Stage20AdaptiveRegimeNewcoinStrategy \
  --pairs NEWCOIN/USDT:USDT \
  --timerange 20260601-
```

## 部署 Stage21 双向高频新币模拟盘

Stage21 是独立策略，不覆盖 Stage20。它使用 93 对 Binance U 本位合约、1m 周期、1000 USDT 模拟本金、单笔 70 USDT、最多 14 个同时持仓，手续费仍按单边 taker 0.05% 写入配置。币池扩展到多空高频和热点新币，包含 `PUMP/USDT:USDT`、`MERL/USDT:USDT`、`WIF/USDT:USDT`、`1000BONK/USDT:USDT`、`1000FLOKI/USDT:USDT`、`POPCAT/USDT:USDT`、`PNUT/USDT:USDT`、`FARTCOIN/USDT:USDT`、`KAITO/USDT:USDT`、`AIXBT/USDT:USDT`、`VIRTUAL/USDT:USDT`、`BERA/USDT:USDT`、`SHELL/USDT:USDT` 等。

当前服务器仓库路径为 `/data/apps/freqtrade` 时，建议用独立目录和独立 compose 项目运行：

```bash
cd /data/apps/freqtrade
git pull --ff-only

rsync -a --delete \
  --exclude '.env' \
  --exclude 'user_data/tradesv3.sqlite*' \
  --exclude 'user_data/logs/*' \
  server-deploy/ server-deploy-stage21/

cd /data/apps/freqtrade/server-deploy-stage21
cp -n /data/apps/freqtrade/server-deploy/.env .env 2>/dev/null || cp .env.example .env

set_env() {
  key="$1"
  value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

set_env FREQTRADE_IMAGE ghcr.io/sunlightcold/freqtrade:develop
set_env FREQTRADE_CONFIG config_binance_stage21_dual_hf_newcoin_93pair_1000u_dryrun.json
set_env FREQTRADE_STRATEGY Intp20Stage21DualHfNewcoinStrategy
set_env STAGE21_HOTSPOT_INTERVAL_SECONDS 180
set_env STAGE21_HOTSPOT_TIMEOUT_SECONDS 8
set_env FREQTRADE_API_BIND 0.0.0.0
set_env FREQTRADE_API_PORT 18082
set_env FREQTRADE_EXCHANGE_KEY ""
set_env FREQTRADE_EXCHANGE_SECRET ""
set_env FREQTRADE_EXTRA_CONFIG_ARGS "--config /freqtrade/user_data/config_server_api_override.json"

SERVER_ORIGIN="http://82.158.225.90:8081"
python3 - "$SERVER_ORIGIN" <<'PY'
import json
import sys
from pathlib import Path

origin = sys.argv[1]
path = Path("user_data/config_server_api_override.json")
example = Path("user_data/config_server_api_override.example.json")
data = json.loads(
    path.read_text(encoding="utf-8")
    if path.exists()
    else example.read_text(encoding="utf-8")
)
api_server = data.setdefault("api_server", {})
api_server["CORS_origins"] = [origin]
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

docker compose -p freqtrade-stage21 --profile stage21 pull
docker compose -p freqtrade-stage21 --profile stage21 up -d --no-deps freqtrade stage21-hotspot
docker compose -p freqtrade-stage21 --profile stage21 ps
```

在现有 FreqUI 里添加一个 Bot：

```text
Bot Name: stage21
API Url: http://服务器IP:18082
Username: .env 里的 FREQTRADE_API_USERNAME
Password: .env 里的 FREQTRADE_API_PASSWORD
```

只看 Stage21 日志：

```bash
cd /data/apps/freqtrade/server-deploy-stage21
docker compose -p freqtrade-stage21 logs --tail=200 --no-color freqtrade
docker compose -p freqtrade-stage21 logs --tail=100 --no-color stage21-hotspot
```

停掉 Stage21，不影响 Stage20 或原模拟盘：

```bash
cd /data/apps/freqtrade/server-deploy-stage21
docker compose -p freqtrade-stage21 down
```

## 部署 Stage22 高确定性新币脉冲模拟盘

Stage22 是独立策略，不覆盖 Stage20/Stage21。它不是宽松刷单版：实测宽松 1m 高频在单边 0.05% taker 手续费下会被噪声和手续费磨损打穿。Stage22 改为只做高确定性新币脉冲，主要是带滚动 edge/胜率过滤的短线空头，少量强趋势多头观察入口。配置仍为 93 对 Binance U 本位合约、1m 周期、1000 USDT 模拟本金、单笔 60 USDT、最多 14 个同时持仓、单边手续费 0.05%。

### 新币 K 线下载

如果 `freqtrade download-data` 因为 Binance `exchangeInfo` 超时失败，可以用仓库内脚本从 Binance Vision 公共归档下载 futures 1m K 线，不需要 API key：

```bash
cd /data/apps/freqtrade/server-deploy-stage22

docker compose -p freqtrade-stage22 run --rm --no-deps freqtrade \
  python /freqtrade/user_data/scripts/download_binance_vision_futures_ohlcv.py \
  --userdir /freqtrade/user_data \
  --pairs BTC PUMP MERL KAITO AIXBT VIRTUAL BERA SHELL WIF 1000BONK 1000FLOKI POPCAT PNUT FARTCOIN \
  --timeframes 1m \
  --timerange 20260101- \
  --max-concurrency 8
```

公共归档通常会延迟一天左右，所以最近一天缺失属于正常现象。

### 独立部署

当前服务器仓库路径为 `/data/apps/freqtrade` 时：

```bash
cd /data/apps/freqtrade
git pull --ff-only

rsync -a --delete \
  --exclude '.env' \
  --exclude 'user_data/tradesv3.sqlite*' \
  --exclude 'user_data/logs/*' \
  server-deploy/ server-deploy-stage22/

cd /data/apps/freqtrade/server-deploy-stage22
cp -n /data/apps/freqtrade/server-deploy/.env .env 2>/dev/null || cp .env.example .env

set_env() {
  key="$1"
  value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

set_env FREQTRADE_IMAGE ghcr.io/sunlightcold/freqtrade:develop
set_env FREQTRADE_CONFIG config_binance_stage22_hot_newcoin_pulse_93pair_1000u_dryrun.json
set_env FREQTRADE_STRATEGY Intp20Stage22HotNewcoinPulseStrategy
set_env STAGE22_HOTSPOT_INTERVAL_SECONDS 180
set_env STAGE22_HOTSPOT_TIMEOUT_SECONDS 8
set_env FREQTRADE_API_BIND 0.0.0.0
set_env FREQTRADE_API_PORT 18083
set_env FREQTRADE_EXCHANGE_KEY ""
set_env FREQTRADE_EXCHANGE_SECRET ""
set_env FREQTRADE_EXTRA_CONFIG_ARGS "--config /freqtrade/user_data/config_server_api_override.json"

SERVER_ORIGIN="http://82.158.225.90:8081"
python3 - "$SERVER_ORIGIN" <<'PY'
import json
import sys
from pathlib import Path

origin = sys.argv[1]
path = Path("user_data/config_server_api_override.json")
example = Path("user_data/config_server_api_override.example.json")
data = json.loads(
    path.read_text(encoding="utf-8")
    if path.exists()
    else example.read_text(encoding="utf-8")
)
api_server = data.setdefault("api_server", {})
api_server["CORS_origins"] = [origin]
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

docker compose -p freqtrade-stage22 --profile stage22 pull
docker compose -p freqtrade-stage22 --profile stage22 up -d --no-deps freqtrade stage22-hotspot
docker compose -p freqtrade-stage22 --profile stage22 ps
```

在现有 FreqUI 里添加一个 Bot：

```text
Bot Name: stage22
API Url: http://服务器IP:18083
Username: .env 里的 FREQTRADE_API_USERNAME
Password: .env 里的 FREQTRADE_API_PASSWORD
```

只看 Stage22 日志：

```bash
cd /data/apps/freqtrade/server-deploy-stage22
docker compose -p freqtrade-stage22 logs --tail=200 --no-color freqtrade
docker compose -p freqtrade-stage22 logs --tail=100 --no-color stage22-hotspot
```

停掉 Stage22，不影响 Stage20/Stage21 或原模拟盘：

```bash
cd /data/apps/freqtrade/server-deploy-stage22
docker compose -p freqtrade-stage22 down
```

## 部署 Stage23 激进通用脉冲模拟盘

Stage23 是 Stage21 的激进防守版，不覆盖 Stage20/Stage21/Stage22。它保留 93 对 Binance U 本位合约、1m 周期、1000 USDT 模拟本金、最多 14 个同时持仓、单边手续费 0.05%，同时屏蔽 Stage21 里回测拖累最大的通用追多和松散回调入口，只保留更有短线胜率的组合入口和通用短动量。这个版本目标是提高短期交易密度和收益弹性，但仍然需要先 dry-run 前向观察。

已做的离线验证使用 2026-01-01 到 2026-06-12 的本地 1m futures K 线，手续费按单边 `0.0005` 计算。完整样本约 `+54.14%`，前半段约 `+27.89%`，后半段约 `+26.21%`。这些不是收益承诺，只用于说明它没有靠单一月份或单一币种拟合。

### 独立部署

当前服务器仓库路径为 `/data/apps/freqtrade` 时：

```bash
cd /data/apps/freqtrade
git pull --ff-only

rsync -a --delete \
  --exclude '.env' \
  --exclude 'user_data/tradesv3.sqlite*' \
  --exclude 'user_data/logs/*' \
  server-deploy/ server-deploy-stage23/

cd /data/apps/freqtrade/server-deploy-stage23
cp -n /data/apps/freqtrade/server-deploy/.env .env 2>/dev/null || cp .env.example .env

set_env() {
  key="$1"
  value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

set_env FREQTRADE_IMAGE ghcr.io/sunlightcold/freqtrade:develop
set_env FREQTRADE_CONFIG config_binance_stage23_aggressive_generic_pulse_93pair_1000u_dryrun.json
set_env FREQTRADE_STRATEGY Intp20Stage23AggressiveGenericPulseStrategy
set_env STAGE23_HOTSPOT_INTERVAL_SECONDS 180
set_env STAGE23_HOTSPOT_TIMEOUT_SECONDS 8
set_env FREQTRADE_API_BIND 0.0.0.0
set_env FREQTRADE_API_PORT 18084
set_env FREQTRADE_EXCHANGE_KEY ""
set_env FREQTRADE_EXCHANGE_SECRET ""
set_env FREQTRADE_EXTRA_CONFIG_ARGS "--config /freqtrade/user_data/config_server_api_override.json"

SERVER_ORIGIN="http://82.158.225.90:8081"
python3 - "$SERVER_ORIGIN" <<'PY'
import json
import sys
from pathlib import Path

origin = sys.argv[1]
path = Path("user_data/config_server_api_override.json")
example = Path("user_data/config_server_api_override.example.json")
data = json.loads(
    path.read_text(encoding="utf-8")
    if path.exists()
    else example.read_text(encoding="utf-8")
)
api_server = data.setdefault("api_server", {})
api_server["CORS_origins"] = [origin]
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

docker compose -p freqtrade-stage23 --profile stage23 pull
docker compose -p freqtrade-stage23 --profile stage23 up -d --no-deps freqtrade stage23-hotspot
docker compose -p freqtrade-stage23 --profile stage23 ps
```

在现有 FreqUI 里添加一个 Bot：

```text
Bot Name: stage23
API Url: http://服务器IP:18084
Username: .env 里的 FREQTRADE_API_USERNAME
Password: .env 里的 FREQTRADE_API_PASSWORD
```

只看 Stage23 日志：

```bash
cd /data/apps/freqtrade/server-deploy-stage23
docker compose -p freqtrade-stage23 logs --tail=200 --no-color freqtrade
docker compose -p freqtrade-stage23 logs --tail=100 --no-color stage23-hotspot
```

停掉 Stage23，不影响其它模拟盘：

```bash
cd /data/apps/freqtrade/server-deploy-stage23
docker compose -p freqtrade-stage23 down
```

### 回测内存注意

不要直接跑 `93 个币种 + 1m + 全年`，32GB 内存很容易被 Pandas 指标列和 Freqtrade 回测缓存打满。2025 验证建议按月或两个月切片跑，或者先缩小到核心币种池：

```bash
.\.venv\Scripts\python.exe user_data\scripts\run_offline_futures_backtest.py -c user_data\config_binance_stage23_aggressive_generic_pulse_93pair_1000u_dryrun.json --strategy Intp20Stage23AggressiveGenericPulseStrategy --timerange 20250101-20250201 --fee 0.0005 --no-timeframe-detail --cache none
```

## 部署 Stage24 稳健脉冲模拟盘

Stage24 是 Stage23 的稳健改进版，不覆盖已有模拟盘。2023-06 到 2026-06 的月度分段回测显示，Stage23 最大结构性拖累来自通用 `s21_momo_s_*` 短动量入口；Stage24 保留 93 币组合和多空交易，但屏蔽长期不稳的通用学习入口，减少弱市场阶段的手续费和噪声磨损。

长样本月度分段结果，手续费按单边 `0.0005` 计算：

```text
2023-06~2024-01: +8.02%, 709 trades, max monthly DD 7.92%
2024:            +88.72%, 1716 trades, max monthly DD 9.40%
2025:           +150.26%, 1380 trades, max monthly DD 9.09%
2026-01~06-12:  +61.92%, 472 trades, max monthly DD 4.59%
```

这些是历史回测结果，不是实盘收益承诺。Stage24 的优先级高于 Stage23：它牺牲了一点 2026 强势期收益，但明显改善 2024/2025 的弱窗口表现。

### 独立部署

当前服务器仓库路径为 `/data/apps/freqtrade` 时：

```bash
cd /data/apps/freqtrade
git pull --ff-only

rsync -a --delete \
  --exclude '.env' \
  --exclude 'user_data/tradesv3.sqlite*' \
  --exclude 'user_data/logs/*' \
  server-deploy/ server-deploy-stage24/

cd /data/apps/freqtrade/server-deploy-stage24
cp -n /data/apps/freqtrade/server-deploy/.env .env 2>/dev/null || cp .env.example .env

set_env() {
  key="$1"
  value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

set_env FREQTRADE_IMAGE ghcr.io/sunlightcold/freqtrade:develop
set_env FREQTRADE_CONFIG config_binance_stage24_robust_pulse_93pair_1000u_dryrun.json
set_env FREQTRADE_STRATEGY Intp20Stage24RobustPulseStrategy
set_env STAGE24_HOTSPOT_INTERVAL_SECONDS 180
set_env STAGE24_HOTSPOT_TIMEOUT_SECONDS 8
set_env FREQTRADE_API_BIND 0.0.0.0
set_env FREQTRADE_API_PORT 18085
set_env FREQTRADE_EXCHANGE_KEY ""
set_env FREQTRADE_EXCHANGE_SECRET ""
set_env FREQTRADE_EXTRA_CONFIG_ARGS "--config /freqtrade/user_data/config_server_api_override.json"

SERVER_ORIGIN="http://82.158.225.90:8081"
python3 - "$SERVER_ORIGIN" <<'PY'
import json
import sys
from pathlib import Path

origin = sys.argv[1]
path = Path("user_data/config_server_api_override.json")
example = Path("user_data/config_server_api_override.example.json")
data = json.loads(
    path.read_text(encoding="utf-8")
    if path.exists()
    else example.read_text(encoding="utf-8")
)
api_server = data.setdefault("api_server", {})
api_server["CORS_origins"] = [origin]
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

docker compose -p freqtrade-stage24 --profile stage24 pull
docker compose -p freqtrade-stage24 --profile stage24 up -d --no-deps freqtrade stage24-hotspot
docker compose -p freqtrade-stage24 --profile stage24 ps
```

在现有 FreqUI 里添加一个 Bot：

```text
Bot Name: stage24
API Url: http://服务器IP:18085
Username: .env 里的 FREQTRADE_API_USERNAME
Password: .env 里的 FREQTRADE_API_PASSWORD
```

只看 Stage24 日志：

```bash
cd /data/apps/freqtrade/server-deploy-stage24
docker compose -p freqtrade-stage24 logs --tail=200 --no-color freqtrade
docker compose -p freqtrade-stage24 logs --tail=100 --no-color stage24-hotspot
```

停掉 Stage24，不影响其它模拟盘：

```bash
cd /data/apps/freqtrade/server-deploy-stage24
docker compose -p freqtrade-stage24 down
```

### 长时间分段回测

本地或服务器都不要直接跑 `93 币 + 1m + 全年`。使用分段脚本逐月跑，结果会写入 `user_data/backtest_results/split/`：

```bash
python user_data/scripts/run_split_futures_backtests.py \
  -c user_data/config_binance_stage24_robust_pulse_93pair_1000u_dryrun.json \
  --strategy Intp20Stage24RobustPulseStrategy \
  --start 20250101 \
  --end 20260101 \
  --months-per-window 1 \
  --fee 0.0005 \
  --no-timeframe-detail
```

## 镜像

- Freqtrade 后端：`ghcr.io/sunlightcold/freqtrade:develop`
- 简体中文 FreqUI：`ghcr.io/sunlightcold/freqtrade-frequi-zh:develop`

如果服务器无法拉取 GHCR 镜像，把 GitHub Package 设为 public，或者在服务器执行 `docker login ghcr.io`。

## 访问

浏览器打开：

```text
http://YOUR_SERVER_IP_OR_DOMAIN:8081
```

登录页：

```text
Bot Name: freqtrade
API Url: http://YOUR_SERVER_IP_OR_DOMAIN:8081
Username: .env 里的 FREQTRADE_API_USERNAME
Password: .env 里的 FREQTRADE_API_PASSWORD
```

外网只需要访问 `8081`。`8081` 内部会通过 nginx 反向代理访问 Freqtrade API，不需要把 `8080` 暴露到公网。

## 日志

```bash
docker compose ps
docker compose logs -f freqtrade
docker compose logs -f frequi
```

保持 `dry_run=true`，直到模拟盘前向验证稳定。

## Telegram 通知

通知按 Freqtrade 官方标准写到 JSON 配置里，不把 token/chat_id 直接塞进 compose 配置。

复制通知配置模板：

```bash
cp user_data/config_notifications.example.json user_data/config_notifications.json
```

编辑 `user_data/config_notifications.json`：

```json
{
  "telegram": {
    "enabled": true,
    "token": "你的TelegramBotToken",
    "chat_id": "你的ChatID",
    "allow_custom_messages": true
  }
}
```

然后在 `.env` 里叠加这个配置文件：

```env
FREQTRADE_EXTRA_CONFIG_ARGS=--config /freqtrade/user_data/config_notifications.json
```

重启：

```bash
docker compose up -d
docker compose logs --tail=100 freqtrade
```

`config_notifications.json` 是私有配置，不要提交到 GitHub。

## 私有覆盖配置

默认不需要 `config_server_api_override.json`。如确实需要叠加私有配置：

```bash
cp user_data/config_server_api_override.example.json user_data/config_server_api_override.json
```

然后在 `.env` 设置：

```env
FREQTRADE_EXTRA_CONFIG_ARGS=--config /freqtrade/user_data/config_server_api_override.json
```
