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

## 私有覆盖配置

默认不需要 `config_server_api_override.json`。如确实需要叠加私有配置：

```bash
cp user_data/config_server_api_override.example.json user_data/config_server_api_override.json
```

然后在 `.env` 设置：

```env
FREQTRADE_EXTRA_CONFIG_ARGS=--config /freqtrade/user_data/config_server_api_override.json
```
