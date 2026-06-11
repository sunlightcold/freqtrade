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
set_env PERMISSIONS_INIT_CONTAINER_NAME freqtrade-permissions-init-stage17
set_env FREQTRADE_CONTAINER_NAME freqtrade-stage17
set_env FREQUI_CONTAINER_NAME frequi-stage17

docker compose pull
docker compose up -d
docker compose logs --tail=100 -f freqtrade
```

Stage17 配置为 1000 USDT 模拟本金，单笔 90 USDT，最多 10 个同时持仓，手续费按单边 0.05% 写入配置。保持 `dry_run=true`，先看前向模拟盘表现。

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
