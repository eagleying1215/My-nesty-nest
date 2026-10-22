# 线上部署（准备完成，尚未发布）

本目录适用于一台有公网 IP 的 Linux 服务器和一个由你控制的域名。无需连接 Ozon 或付费 API；服务器和域名可能收费，具体费用需你在服务商确认。当前聊天未连接托管账号，没有可直接使用的公网网址。

## 你需要准备

1. 一个服务器/云主机账号，以及 Linux 服务器（建议至少1GB内存）和 SSH 访问权限。
2. 一个域名，把其 DNS A 记录指向该服务器公网 IPv4。仅在服务器确实配置 IPv6 时设置 AAAA。
3. 服务器安装 Docker Engine 和 Docker Compose 插件，放行 TCP 80、443；不要对公网开放 8000。
4. 将项目代码上传至服务器。不要把你自己的 data/、数据库、备份、密码文件上传到公开 Git 仓库。

如果你已有 Render、Railway 等托管账号，应先根据该平台的持久化磁盘、HTTPS 与费用限制适配，不能直接用临时文件系统存正式商品数据。

## 在服务器启动

在项目根目录运行（交互输入密码，不要在聊天中发送密码）：

```bash
python3 配置线上密码.py
docker compose --env-file deploy/private.env -f deploy/compose.yaml config --quiet
docker compose --env-file deploy/private.env -f deploy/compose.yaml up -d --build
```

配置脚本将域名、用户名与 PBKDF2 加盐摘要保存在被 Git 忽略的 `deploy/private.env`，不存储明文密码。密码至少16位，建议使用密码管理器随机生成。该文件仍应保密。不要直接输出 `docker compose config` 或整个进程环境，以免泄露摘要或其他配置。

Caddy 自动申请和续期 HTTPS 证书（需真实域名及80/443连通），浏览器输入 `https://你的实际域名`。浏览器会弹出用户名和密码框，登录后进入中文工作台。密码保护覆盖页面、图片脚本、全部数据接口和备份，只有不含商品信息的 `/healthz` 健康接口无需登录。浏览器可能缓存登录凭据，退出使用请关闭浏览器会话；无需复杂账号系统。

确认：

```bash
docker compose --env-file deploy/private.env -f deploy/compose.yaml ps
```

检查未登录访问请用以下 GET 命令，以预期的401为准：

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://你的实际域名/api/products
```

返回401说明数据入口需登录；随后在浏览器登录，创建一款明确标记“演示”的商品，保存刷新，再下载备份验证。HTTPS、真实域名访问、磁盘恢复验证完成前，不能认为部署成功。

## 数据、更新与恢复

- SQLite 与实拍存放在 Docker 命名数据卷 `workbench_data`（实际名称含项目名前缀），不会随容器重建删除。
- **不要执行 `docker compose down -v`**，它会删除数据卷。日常备份使用页面“完整备份”，另存到私密存储。
- 新服务器上先部署，再在页面“恢复备份”导入 JSON；已有数据会被覆盖，先备份。
- 从本地迁移也使用完整备份/恢复，不会自动迁移当前云机器的数据。
- 更新前先备份，再执行上述 `up -d --build`。重启策略仅覆盖同一服务器 Docker 服务恢复，不是跨机器备份。
- 域名证书存储于独立的 Caddy 数据卷。不要在应用前另接未知的公共临时隧道。
- 查看启动错误：`docker compose --env-file deploy/private.env -f deploy/compose.yaml logs --tail=80`。不要分享含私人资料的日志。

## 验证范围

Python 应用、认证与原业务测试在开发环境验证。容器构建、Caddy 证书签发、DNS 和公网访问必须在有 Docker daemon 与实际域名的目标服务器上验证；本目录的存在不代表已经发布。
