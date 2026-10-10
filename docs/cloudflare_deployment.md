# Cloudflare Pages 前端部署

前端页面导出为静态文件，`web/functions/api/[[path]].ts` 只代理五个已知 API 路由。Python、LangGraph、向量检索和模型调用运行在 Modal。请求等待后端返回时不执行模型计算；实际 Workers CPU 用量仍需在部署后观察。

网站已发布到 [tarot-persona-web.pages.dev](https://tarot-persona-web.pages.dev)，上线记录见 [部署状态](deployment_status.md)。重新部署其他环境时，先按 [Modal 部署说明](modal_deployment.md) 配置密钥、重建索引并部署后端，拿到真实 HTTPS 地址。

## 构建

在项目根目录运行：

```powershell
Set-Location web
npm run typecheck
npm run test:proxy
npm run build:cloudflare
```

脚本复用已有 `web/node_modules`，不重新安装包。Windows 构建临时目录和缓存放在 `E:\for-LLM\AUXI\Tarot_Persona_Agent\web-builds`，Linux 默认为 `/tmp/tarot-persona-web-builds`，可通过 `TAROT_BUILD_DIR` 自定义。临时目录保留便于检查，需要时可自行清理。

脚本只复制前端所需目录和配置，不复制 `.env*`，排除本地 Next.js `/api` 路由，强制浏览器使用同源 `/api/*`。构建输出为 `web/out`；如果原来已有导出目录，保留为 `web/out.backup-*`。

`out/_routes.json` 仅允许 `/api/*` 进入 Functions，其余页面和牌图走静态资源。现有牌图目录受 Git 忽略，本机导出会包含它；若改用 Git 自动构建，需要单独提供这些资源，并确认其公开展示授权。

## Cloudflare 配置

项目名称为 `tarot-persona-web`，生产分支为 `main`。`web/wrangler.toml` 管理运行时普通变量；访问令牌单独存于 Cloudflare Secret：

| 变量 | 类型 | 值 |
| --- | --- | --- |
| `BACKEND_API_BASE_URL` | 配置文件变量 | Modal 部署生成的 HTTPS 基地址，无 `/api` 后缀 |
| `BACKEND_API_ACCESS_TOKEN` | Secret | 与 Modal `API_ACCESS_TOKEN` 相同的随机令牌 |

当前生产环境已配置令牌。预览环境若需要调用 API，需单独配置相同名称的 Secret。普通变量以 `wrangler.toml` 为准，修改后重新发布。令牌留在 Function 的 `context.env` 中，不填写任何 `NEXT_PUBLIC_*`。浏览器和 Cloudflare 同源访问，因此一般无需把网站域名加到 Modal CORS 中。

本地代理验证可以创建受 Git 忽略的 `web/.dev.vars`，填写这两个变量，然后用 Wrangler Pages dev 预览。不要把 `.dev.vars` 上传到静态目录。

## 上传

使用 Wrangler 上传静态资源与 Functions。本机已安装 Wrangler 4.149.0，工具、登录配置、日志和缓存均在 AUXI。后续发布直接复用：

```powershell
# 当前目录必须是 web，Wrangler 才能找到同级 functions。
$env:XDG_CONFIG_HOME = 'E:\for-LLM\AUXI\Tarot_Persona_Agent\cloudflare-config'
$env:WRANGLER_LOG_PATH = 'E:\for-LLM\AUXI\Tarot_Persona_Agent\cloudflare-logs\wrangler.log'
$env:WRANGLER_CACHE_DIR = 'E:\for-LLM\AUXI\Tarot_Persona_Agent\cloudflare-cache'
$env:WRANGLER_SEND_METRICS = 'false'
$taskWrangler = 'E:\for-LLM\AUXI\Tarot_Persona_Agent\cloudflare-tools\node_modules\wrangler\bin\wrangler.js'
# 需要当前本机代理时设置；代理需已启动。
$env:HTTPS_PROXY = 'http://127.0.0.1:7890'
$env:HTTP_PROXY = 'http://127.0.0.1:7890'
# 当前已登录，仅登录失效或切换账号时执行：
# node $taskWrangler login --scopes account:read user:read pages:write
node $taskWrangler pages deploy out --project-name tarot-persona-web --branch main --commit-dirty=true
```

显式指定 `--branch main`，防止从当前开发分支发布成预览版本。该项目使用 Direct Upload；普通控制台拖拽上传不会编译 Pages Functions。修改 Cloudflare 变量或 Secret 后重新部署，使配置生效。Wrangler 需要的项目临时目录 `web/.wrangler/` 已被 Git 忽略。

静态目录中不能出现 `.env`、向量索引或知识文本。Pages Function 只转发 JSON 请求，限制请求体为16 KiB，后端错误消息不包含代理访问令牌。它不替代用户登录：知道网站地址的人仍可调用公开页面的功能。展示初期可使用 Cloudflare Access 限制访问对象，并保留 Modal 预算与后端限流。

## 上线验证

1. 打开 Pages 地址的首页、知识库、占卜页和运行状态页。
2. 确认 `/api/health` 能返回 API embedding 和兼容索引状态。
3. 测试一次资料检索和一次完整解读；确认牌图正常显示。
4. 检查浏览器 Network 面板，请求应发往网站同源 `/api/*`，不携带模型密钥或后端令牌。
5. 从主要访客所在地测试冷启动和模型延迟，再决定是否开启常驻容器或调整区域。

官方参考：[Pages Functions 路由](https://developers.cloudflare.com/pages/functions/routing/)、[运行时变量与 Secrets](https://developers.cloudflare.com/pages/functions/bindings/)、[Next.js 静态导出](https://nextjs.org/docs/app/guides/static-exports)、[Direct Upload 与 Functions](https://developers.cloudflare.com/pages/get-started/direct-upload/)。
