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

## Stage60 单策略模拟盘

Stage60 是当前通过门禁的单策略候选：41 个 Binance USDT 永续币对、1 分钟周期、
多空交易、1000U 模拟本金、单仓 100U、最多 9 仓。三段独立年度原生回测的组合
年化分别为 271.82%、118.32%、164.36%，胜率为 83.68%、81.27%、81.28%，
日均 11.65 至 16.60 单。完整成本、回撤和局限见
[`STAGE60_BACKTEST_REPORT.md`](STAGE60_BACKTEST_REPORT.md)。这些是历史模拟结果，
不是未来收益保证；Stage60 目前只允许模拟盘。

服务器仓库路径为 `/data/app/freqtrade` 时，只通过 Git 更新并替换主 Bot。脚本会
保留 `.env` 中现有的 API 密码和交易所凭证，并确保同一 Compose 项目中只有一个
FreqUI。Freqtrade API 和 FreqUI 分别绑定 `127.0.0.1:8080`、`127.0.0.1:8081`，
公网访问必须经过宿主机 Nginx 反向代理：

```bash
cd /data/app/freqtrade
git pull --ff-only
bash server-deploy/apply-stage60-single.sh /data/app/freqtrade
```

宿主机 Nginx 的 `proxy_pass` 指向：

```nginx
proxy_pass http://127.0.0.1:8081;
```

修改 Nginx 配置后执行 `nginx -t && systemctl reload nginx`。服务器安全组和防火墙
不需要放行 `8080` 或 `8081`。

第一次切换策略并希望从 1000U 空白模拟账户开始时，显式重置数据库。旧数据库会先
备份到 `server-deploy/backups/`：

```bash
cd /data/app/freqtrade
git pull --ff-only
RESET_DB=1 bash server-deploy/apply-stage60-single.sh /data/app/freqtrade
```

查看唯一 WebUI 的登录账号和脚本自动生成或保留的密码，不需要手工重新输入配置：

```bash
cd /data/app/freqtrade/server-deploy
grep -E '^FREQTRADE_API_(USERNAME|PASSWORD)=' .env
```

部署后快速检查：

```bash
cd /data/app/freqtrade/server-deploy
docker compose -p server-deploy ps
curl -sS http://127.0.0.1:8080/api/v1/ping
docker compose -p server-deploy logs --since=10m --no-color freqtrade \
  | grep -Ei 'ERROR|CRITICAL|Traceback|not found|ExchangeNotAvailable' \
  | tail -40
```

## 覆盖当前三路为 Stage28 / Stage29 / Stage30

服务器当前三路模拟盘按下面映射覆盖：

- `/data/apps/freqtrade/server-deploy` -> `Intp20Stage28HighWinCompositeScalpStrategy`
- `/data/apps/freqtrade/server-deploy-stage20` -> `Intp20Stage29HighWinReversionScalpStrategy`
- `/data/apps/freqtrade/server-deploy-stage24` -> `Intp20Stage30HighWinMomentumScalpStrategy`

Stage28/29/30 是 2026-06-12..2026-07-05 线上失效窗口后的修复版，使用 BTC 状态过滤和热点新币白名单，手续费按单边 `0.05%`、本金 `1000U` 配置。最新窗口回测：

- Stage28: 15 单，胜率 73.3%，收益 +4.98%，CAGR 109.27%，最大回撤约 0.7%
- Stage29: 22 单，胜率 77.3%，收益 +7.37%，CAGR 195.03%，移除近期拖累的 MEW
- Stage30: 约 19 单，胜率约 73.7%，收益约 +7.41%，CAGR 196.52%，加入 EIGEN 领涨回踩确认

2026-01-01..2026-07-05 长窗复核为正但年化不高，说明这三套是针对当前热点新币行情的高胜率修复策略，不应理解为长期收益承诺。

只需要拉代码并执行脚本，不需要手动上传文件。默认保留各目录 `.env` 里的 API 密码和交易所 key，只改策略配置并重启 `freqtrade` 服务：

```bash
cd /data/apps/freqtrade
git pull --ff-only
bash server-deploy/apply-stage28-30-overrides.sh /data/apps/freqtrade
cd /data/apps/freqtrade/server-deploy && docker compose -p server-deploy ps
cd /data/apps/freqtrade/server-deploy-stage20 && docker compose -p freqtrade-stage20 ps
cd /data/apps/freqtrade/server-deploy-stage24 && docker compose -p freqtrade-stage24 ps
```

如果要清空旧模拟盘订单记录、用 1000U 重新开始，执行脚本前加 `RESET_DB=1`。脚本会先备份 `tradesv3.sqlite` 再删除旧库：

```bash
cd /data/apps/freqtrade
git pull --ff-only
RESET_DB=1 bash server-deploy/apply-stage28-30-overrides.sh /data/apps/freqtrade
```

## Stage17 1000U 实验候选

Stage17 当前不满足“稳定年化 100% + 高频交易”的采用要求。最新 1000U/0.05% 单边手续费抽测中，2026-06-01..2026-06-12 只有 11 单、约 1.1 单/天、总收益 +0.14%。保留下面命令只用于复现实验或回滚排查，不作为推荐部署。

服务器只需要拉取仓库并用命令更新 `.env`，不需要手动上传文件：

```bash
cd /data/apps/freqtrade/server-deploy
docker compose down
mkdir -p backups
cp user_data/tradesv3.sqlite backups/tradesv3-before-stage17-$(date +%Y%m%d-%H%M%S).sqlite 2>/dev/null || true
rm -f user_data/tradesv3.sqlite user_data/tradesv3.sqlite-shm user_data/tradesv3.sqlite-wal

cd /data/apps/freqtrade
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
sed -i '/^FREQTRADE_EXTRA_CONFIG_ARGS=/d' .env
docker compose pull
docker compose up -d --remove-orphans
docker compose logs --tail=100 -f freqtrade
```

Stage17 配置为 1000 USDT 模拟本金，单笔 90 USDT，最多 10 个同时持仓，手续费按单边 0.05% 写入配置。该策略仅作为实验候选保留。

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

## Stage20 自适应学习实验候选

Stage20 是独立策略，不覆盖 Stage17/Stage24。它使用扩展后的新币和高 beta 币池、1m 周期、1000 USDT 模拟本金、单笔 90 USDT、最多 10 个同时持仓，手续费按单边 0.05% 写入配置。当前实盘入口只保留快扫动量多空，偏向捕捉短时间流动性冲击；更宽的 pulse / vwap 入口保留在代码里做研究，但在 Stage23/24 中会被屏蔽。

Stage20 当前不满足“稳定年化 100% + 高频交易”的采用要求。最新 1000U/0.05% 单边手续费抽测中，2026-06-01..2026-06-12 只有 9 单、约 0.9 单/天、总收益 +0.33%。保留部署命令只用于实验复现，不作为推荐运行方案。

### 并行运行 Stage20 实验，不影响当前模拟盘

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
sed -i '/^FREQTRADE_EXTRA_CONFIG_ARGS=/d' .env

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

Stage20 的服务端配置已内置现有 WebUI 来源 `http://82.158.225.90:8081`。如果服务器 IP 或域名变了，直接更新 `user_data/config_binance_stage20_adaptive_regime_newcoin_38pair_1000u_dryrun.json` 里的 `api_server.CORS_origins`，不要再给 `.env` 增加不存在的 `config_server_api_override.json`。

```bash
cd /data/apps/freqtrade/server-deploy-stage20
sed -i '/^FREQTRADE_EXTRA_CONFIG_ARGS=/d' .env
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
sed -i '/^FREQTRADE_EXTRA_CONFIG_ARGS=/d' .env

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

## Stage24 稳健脉冲实验候选

Stage24 是 Stage23 的稳健改进版，不覆盖已有模拟盘。最新复核显示，长期拖累来自通用 `s21_momo_l_*` 长动量和松散 pull 入口；Stage24 当前只放行 `s21_momo_s_*` 短动量，屏蔽长期不稳的通用学习入口，减少弱市场阶段的手续费和噪声磨损。

Stage24 也不满足“稳定年化 100% + 高频交易”的采用要求。2026-06-01..2026-06-12 窗口为 14 单、约 1.4 单/天、总收益 +2.02%、短窗口 CAGR 107.54%；但 2026-04-01..2026-05-01 只有 4 单、约 0.13 单/天、总收益 +0.28%、CAGR 3.49%。因此不能采用为目标策略。

长样本月度分段结果，手续费按单边 `0.0005` 计算：

```text
2023-06~2024-01: +8.02%, 709 trades, max monthly DD 7.92%
2024:            +88.72%, 1716 trades, max monthly DD 9.40%
2025:           +150.26%, 1380 trades, max monthly DD 9.09%
2026-01~06-12:  +61.92%, 472 trades, max monthly DD 4.59%
```

这些是历史回测结果，不是实盘收益承诺，且不能替代最新 1000U 复核结论。Stage24 只作为实验候选保留。

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
sed -i '/^FREQTRADE_EXTRA_CONFIG_ARGS=/d' .env

docker compose -p freqtrade-stage24 --profile stage24 pull
docker compose -p freqtrade-stage24 --profile stage24 up -d --force-recreate --no-deps freqtrade stage24-hotspot
docker compose -p freqtrade-stage24 --profile stage24 ps
```

在现有 FreqUI 里添加一个 Bot：

```text
Bot Name: stage24
API Url: http://服务器IP:18085
Username: .env 里的 FREQTRADE_API_USERNAME
Password: .env 里的 FREQTRADE_API_PASSWORD
```

Stage24 的服务端配置已内置现有 WebUI 来源 `http://82.158.225.90:8081`。如果服务器 IP 或域名变了，直接更新 `user_data/config_binance_stage24_robust_pulse_93pair_1000u_dryrun.json` 里的 `api_server.CORS_origins`。

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

只有确认 `user_data/config_server_api_override.json` 已经存在时才设置这一项。否则 Freqtrade 启动时会报 `Config file ... not found` 并循环重启。恢复方式：

```bash
sed -i '/^FREQTRADE_EXTRA_CONFIG_ARGS=/d' .env
docker compose up -d
```
# Stage31 Deployment Blocked

Stage31 and its follow-up research did not pass the current acceptance gates.
`apply-stage31-single.sh` intentionally exits without changing containers,
configuration, or databases. See `STAGE33_34_RESEARCH_REPORT.md` for the
cross-year results. There is no approved replacement strategy to deploy yet.
