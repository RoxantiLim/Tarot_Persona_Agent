# 部署状态

更新日期：2026-10-09（Asia/Shanghai）。

## Modal 后端已发布

- 工作区：`roxantilim`
- 应用：`tarot-persona-api`
- 后端基地址：https://roxantilim--tarot-persona-api-api.modal.run
- [健康状态](https://roxantilim--tarot-persona-api-api.modal.run/api/health)
- [Modal 部署管理页](https://modal.com/apps/roxantilim/main/deployed/tarot-persona-api)
- CPU 请求：0.5，内存：1024 MiB，最少0个容器、最多1个容器，每容器最多2个并行请求。
- 模型：硅基流动 `BAAI/bge-m3` 与 DeepSeek `deepseek-v4-pro`。
- 云端 Secret：`tarot-api-secrets`；凭据存于本机 AUXI 配置和 Modal Secret，不记录在本文中。

## 已完成的线上验证

| 检查 | 结果 |
| --- | --- |
| `/api/health` | HTTP 200，1653个知识片段，API embedding 已配置，索引兼容 |
| 未提供令牌访问 `/api/cards` | HTTP 401 |
| 携带令牌访问 `/api/cards` | HTTP 200，78张牌 |
| 携带令牌访问 `/api/readers` | HTTP 200，2个 Persona |
| 真实向量检索 | HTTP 200，返回3个片段，约3.14秒 |
| 完整三牌解读 | HTTP 200，返回5个知识片段、3个相似案例，三张指定牌均出现，约36.61秒 |

耗时来自本机当前代理网络的一次验证，不代表其他地区、冷启动或后续请求的固定耗时。风格检查本次未启用。

## Cloudflare 前端已发布

- [正式网站](https://tarot-persona-web.pages.dev)
- [本次部署快照](https://b91ed7b2.tarot-persona-web.pages.dev)
- Pages 项目：`tarot-persona-web`，生产分支：`main`，采用 Wrangler Direct Upload。
- 前端静态页面与牌图由 Pages 提供，`/api/*` 由 Pages Function 转发到 Modal。
- `BACKEND_API_BASE_URL` 存于 `web/wrangler.toml`；后端访问令牌仅存于 Cloudflare 生产环境 Secret，模型密钥仅在 Modal。

通过正式网站的线上验证：

| 检查 | 结果 |
| --- | --- |
| 首页、知识库、占卜页、运行状态页 | HTTP 200，页面引用的 JS/CSS 资源均可加载 |
| 牌图样本 | HTTP 200，返回有效 PNG |
| 同源 `/api/health` | HTTP 200，1653个知识片段，API embedding 与索引兼容 |
| 同源 `/api/cards` 与 `/api/readers` | HTTP 200，78张牌、2个 Persona；客户端无需持有后端令牌 |
| 真实向量检索 | HTTP 200，返回3个片段，约2.50秒 |
| 完整三牌解读 | HTTP 200，826字，5个知识片段、3个相似案例，五个图节点完成，约34.97秒 |
| 静态构建凭据检查 | 未发现当前模型密钥或后端令牌 |

本次浏览器检查工具因启动错误不可用，尚未完成视觉和点击交互验收。上述结果来自真实 HTTP 请求及资源检查，耗时不代表后续请求的固定延迟；本次解读未开启风格检查。

本地 `web/.env.local` 已配置为通过 Next.js 服务端代理连接 Modal。重启本地 Next.js 后生效。后续更新前端按照 [Cloudflare 部署说明](cloudflare_deployment.md) 构建并重新发布。

后续更新后端按照 [Modal 部署说明](modal_deployment.md) 重新发布。Windows CLI 使用 UTF-8 输出，网络需要时使用本机代理。
