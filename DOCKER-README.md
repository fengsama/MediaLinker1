# MediaLinker NAS / Docker 部署

Docker 版运行在 NAS 本机，浏览器访问 `http://NAS的IP:8787`。它直接读取已映射的 NAS 目录，不需要在电脑上挂载 SMB。

## 快速部署

1. 下载本仓库中的 `docker-compose.yml` 和 `.env.example`，放入 NAS 上同一个新目录。
2. 将 `.env.example` 复制为 `.env`。
3. 编辑 `.env`：
   - `NAS_ROOT` 填写同时包含下载目录和媒体库目录的共同上级目录，例如群晖的 `/volume1`。
   - `MEDIALINKER_ACCESS_TOKEN` 改成自己的强密码。
4. 在该目录运行：

```bash
docker compose up -d
```

5. 浏览器访问 `http://NAS的IP:8787`，输入上一步设置的密码。

进入网页后看到的路径以 `/nas` 开头。例如 NAS 实际目录 `/volume1/downloads` 在网页里显示为 `/nas/downloads`。

## 更新

```bash
docker compose pull
docker compose up -d
```

Docker 版通过更新容器镜像升级，网页内不会替换正在运行的容器。

## 硬链接注意事项

- 来源文件和输出文件必须位于同一个文件系统，否则系统无法创建硬链接。
- 建议把共同上级目录一次性映射到 `/nas`。不要把下载目录和媒体库目录分别映射为两个 Docker 卷，否则即使它们在 NAS 上属于同一存储池，也可能被容器识别成不同文件系统。
- 容器需要对来源目录拥有读取权限，对输出目录拥有写入权限。
- 硬链接不会重复占用影片容量；删除其中一个文件名不会删除仍由另一个硬链接引用的数据。

## 安全建议

- 必须修改默认访问密码，并使用至少 16 位的独立密码。
- 建议只在家庭局域网开放端口。若需要从公网访问，请通过可信的反向代理启用 HTTPS，不要直接暴露 8787 端口。
- 网页只能浏览 `MEDIALINKER_ALLOWED_ROOTS` 配置的目录，默认仅允许 `/nas`。

## 自行构建

```bash
docker compose build
```

也可以直接构建：

```bash
docker build -t medialinker .
```
