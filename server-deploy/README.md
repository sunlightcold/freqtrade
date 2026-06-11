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
set_env FREQTRADE_CONTAINER_NAME freqtrade-stage17
set_env FREQUI_CONTAINER_NAME frequi-stage17

docker compose pull
docker compose up -d
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
set_env FREQTRADE_CONTAINER_NAME freqtrade-stage18
set_env FREQUI_CONTAINER_NAME frequi-stage18
set_env STAGE18_HOTSPOT_CONTAINER_NAME stage18-hotspot
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
set_env FREQTRADE_CONTAINER_NAME freqtrade-stage19
set_env FREQUI_CONTAINER_NAME frequi-stage19
set_env STAGE19_HOTSPOT_CONTAINER_NAME stage19-hotspot
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

当前服务器仓库路径为 `/data/apps/freqtrade` 时，用独立 compose 项目和独立部署目录运行 Stage20。这样不会重建现有 `server-deploy` 里的模拟盘，Stage20 会使用自己的数据库、容器名和 WebUI 端口。

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
set_env FREQUI_IMAGE ghcr.io/sunlightcold/freqtrade-frequi-zh:develop
set_env FREQTRADE_CONFIG config_binance_stage20_adaptive_regime_newcoin_38pair_1000u_dryrun.json
set_env FREQTRADE_STRATEGY Intp20Stage20AdaptiveRegimeNewcoinStrategy
set_env FREQTRADE_CONTAINER_NAME freqtrade-stage20
set_env FREQUI_CONTAINER_NAME frequi-stage20
set_env STAGE20_HOTSPOT_CONTAINER_NAME stage20-hotspot-parallel
set_env STAGE20_HOTSPOT_INTERVAL_SECONDS 240
set_env STAGE20_HOTSPOT_TIMEOUT_SECONDS 8
set_env FREQTRADE_API_BIND 127.0.0.1
set_env FREQTRADE_API_PORT 18080
set_env FREQUI_BIND 0.0.0.0
set_env FREQUI_PORT 18081
set_env FREQTRADE_EXCHANGE_KEY ""
set_env FREQTRADE_EXCHANGE_SECRET ""

docker compose -p freqtrade-stage20 --profile stage20 pull
docker compose -p freqtrade-stage20 --profile stage20 up -d --remove-orphans
docker compose -p freqtrade-stage20 --profile stage20 ps
```

Stage20 WebUI:

```text
http://服务器IP:18081
```

登录页填写：

```text
Bot Name: freqtrade
API Url: http://服务器IP:18081
Username: .env 里的 FREQTRADE_API_USERNAME
Password: .env 里的 FREQTRADE_API_PASSWORD
```

如果只重启 Stage20，不影响原策略：

```bash
cd /data/apps/freqtrade/server-deploy-stage20
docker compose -p freqtrade-stage20 --profile stage20 up -d
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
set_env FREQTRADE_CONTAINER_NAME freqtrade-stage20
set_env FREQUI_CONTAINER_NAME frequi-stage20
set_env STAGE20_HOTSPOT_CONTAINER_NAME stage20-hotspot
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
