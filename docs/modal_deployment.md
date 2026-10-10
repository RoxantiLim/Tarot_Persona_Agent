# Modal 后端部署

本方案保留 FastAPI 和 LangGraph，使用硅基流动 `BAAI/bge-m3` API 与 DeepSeek API。线上只读取 NumPy 向量索引，不运行 OCR、Streamlit 或本地模型。当前代码改造不等于已发布网站。

## 1. 本机环境

部署工具环境位于 `E:\for-LLM\AUXI\Tarot_Persona_Agent\.venv-modal`。从项目根目录运行：

```powershell
$ModalPython = 'E:\for-LLM\AUXI\Tarot_Persona_Agent\.venv-modal\Scripts\python.exe'
$env:MODAL_CONFIG_PATH = 'E:\for-LLM\AUXI\Tarot_Persona_Agent\modal.toml'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
& $ModalPython -m pip install --cache-dir 'E:\for-LLM\AUXI\Tarot_Persona_Agent\pip-cache' -r requirements-api.txt -r requirements-modal.txt
```

若该环境不存在，可用已有 Python 创建它：

```powershell
& 'E:\for-LLM\AUXI\Tarot_Persona_Agent\.venv-clean\Scripts\python.exe' -m venv 'E:\for-LLM\AUXI\Tarot_Persona_Agent\.venv-modal'
```

## 2. 修改现有 .env

保留已有 `DEEPSEEK_API_KEY` 和其他本地配置，新增或替换以下同名条目，每个变量只保留一行：

```dotenv
EMBEDDING_PROVIDER=api
EMBEDDING_API_KEY=在这里填写硅基流动密钥
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_TIMEOUT_SECONDS=20
EMBEDDING_BATCH_SIZE=16
VECTOR_STORE_BACKEND=numpy
LOCAL_INDEX_DIR=data/indexes/api_vectors
BUILD_CHROMA=0
```

`EMBEDDING_BASE_URL` 是 `/v1` 基地址，不要填写 `/v1/embeddings`。`EMBEDDING_DEVICE`、`MODEL_CACHE_DIR`、`CHROMA_DIR` 在 API + NumPy 模式下不参与向量检索，原值可以保留。免费模型名称为 `BAAI/bge-m3`；不要无意替换为 `Pro/BAAI/bge-m3`。

编辑配置后重启正在运行的后端。在独立 API 索引完成前，API 模式不会自动加载旧本地模型或旧向量。

## 3. 重建独立索引并验证

```powershell
& $ModalPython scripts/rebuild_api_index.py
& $ModalPython scripts/rebuild_api_index.py --validate-only
```

默认读取 `data/indexes/local_vectors/documents.jsonl`，仅将已处理文档发送给 embedding API，写入 `data/indexes/api_vectors`。不重新解析 PDF、不删除原来的 `local_vectors` 或 Chroma 索引。再次重建 API 索引时，旧 API 目录会保留为同级 `api_vectors.backup-*`；发布失败会尝试恢复旧目录。重建前先停掉读取该索引的本地服务，避免 Windows 文件锁影响目录切换。

可用 `--source 路径` 指定另一个 documents.jsonl，用 `--output 路径` 指定新的索引目录。输入索引和输出目录不能相同。API 请求失败、响应不完整、维度不同或包含无效向量时，重建失败，旧索引保留。

验证通过后先进行本地检索评估：

```powershell
& $ModalPython scripts/run_eval.py --skip-generation
```

该命令仍会调用 embedding API，只跳过 DeepSeek 生成；它会更新评估报告。需要检查完整生成时移除 `--skip-generation`，这会产生 DeepSeek 调用费用。模拟单元测试不能证明真实密钥或真实模型可用。

## 4. 准备部署数据

```powershell
& $ModalPython scripts/prepare_modal_data.py
```

生成 `data/deploy/modal`，仅包含验证过的索引、Persona JSON、审核后的案例 JSONL。使用 `--without-cases` 可以排除案例，但部署后案例召回为空。这个包和索引受 `.gitignore` 保护，不会提交到 GitHub；执行 Modal 部署时会上传到你自己的 Modal 工作区。包中含知识文本和审核案例，不要当作公开静态资源发布。

原始 PDF、截图、牌图、OCR 缓存、日志、`.env` 和候选案例不会打包。牌图用于前端，后端 Modal 不需要它们。

## 5. Modal 账号、Secrets 和预算

注册 Starter 账号，在 Usage & Billing 检查支付方式、免费计算额度、usage limit 与扣除额度后的 spend limit。试用阶段可将净支出上限设为 0；额度和费用以账户页面为准。

在 Modal Secrets 新建 `tarot-api-secrets`，填写：

| 变量 | 值 |
| --- | --- |
| `DEEPSEEK_API_KEY` | 已有 DeepSeek 密钥 |
| `EMBEDDING_API_KEY` | 硅基流动密钥 |
| `API_ACCESS_TOKEN` | 独立生成的随机访问令牌，不是模型 API Key |

在本机生成访问令牌，然后仅复制到自己控制的 Secrets 与前端服务端配置中：

```powershell
& $ModalPython -c "import secrets; print(secrets.token_urlsafe(32))"
```

不要将上述令牌放入 `NEXT_PUBLIC_*`、前端代码或 Git。若需要调整 CORS，可在 Secret 中增加 `CORS_ORIGINS`，用逗号分隔允许的站点；CORS 不等同于访问认证。

如果本机已有准备好的 `.env.modal`，其中包含上述三个变量，可以在登录后直接创建 Secret，无需把密钥粘贴进终端命令：

```powershell
& $ModalPython -m modal secret create tarot-api-secrets --from-dotenv .env.modal
```

`.env.modal` 受 Git 忽略，只作为你本机向 Modal 配置 Secret 的输入。若 Secret 已存在，先核对是否属于本项目，更新时再使用 `--force`。

## 6. 登录和发布后端

```powershell
& $ModalPython -m modal setup
& $ModalPython -m modal deploy modal_app.py
```

`setup` 需要在浏览器中完成本人授权。部署会创建 `tarot-persona-api` 的 HTTPS 接口，随后电脑可关闭；`modal serve` 是依赖本机进程的开发模式。没有准备包或没有 Secrets 时，先完成对应步骤，不要跳过验证。

若浏览器通过本机代理访问 Modal，而 CLI 无法连接，需要安装 `requirements-modal.txt` 中的官方代理支持依赖。此电脑当前本机代理端口为7890，CLI 可在当前 PowerShell 会话中使用：

```powershell
$env:HTTPS_PROXY = 'http://127.0.0.1:7890'
$env:HTTP_PROXY = 'http://127.0.0.1:7890'
```

端口应以自己的代理设置为准。这两行只影响当前会话，不修改系统代理。如果需要单独发起浏览器授权，也可以运行 `& $ModalPython -m modal token new`。

Windows 中若发布输出出现 `gbk` 编码错误，确认本节顶部的 `PYTHONUTF8` 和 `PYTHONIOENCODING` 已设置，再重试发布；镜像构建结果会复用。

配置为 CPU 0.5 物理核请求、1024 MiB 内存、最多一个容器、零常驻容器、每容器最多两个并行请求。容器闲置后会缩到零，首次访问可能冷启动。启动、请求处理及缩容等待都可能消耗计算额度；最大容器数不是账单上限。

有访问令牌时，单个 Python 进程对 POST 请求限制为每分钟10次，超限返回429。这是演示级限流，重启后计数会重置，需要配合预算限制。请求模型超时不会重新执行整个 Agent；线上 DeepSeek 超时为90秒，Modal 执行超时140秒，Web Functions 还有150秒的 HTTP 超时机制。模型超时不是整个请求的预算，牌面补充生成与风格检查会增加总耗时，长任务仍需单独设计。

先访问部署地址的 `/api/health`，检查 `embedding_configured`、`index_compatible`、知识数量。健康接口只验证配置是否存在和索引文件，不证明外部服务实际可达。随后通过前端测试一次检索与一次完整解读，并观察日志、延迟和计算额度。

## 7. 本地前端连接 Modal

在 `web/.env.local` 配置，并重启 Next.js：

```dotenv
BACKEND_API_BASE_URL=https://实际的Modal地址.modal.run
BACKEND_API_ACCESS_TOKEN=与Modal中API_ACCESS_TOKEN一致的值
BACKEND_API_TIMEOUT_MS=145000
NEXT_PUBLIC_API_BASE_URL=
```

此时浏览器仍请求同源 `/api/*`，Next.js 服务端添加后端访问令牌。它不会将令牌打包到浏览器。若本地 Python 后端也开启 `API_ACCESS_TOKEN`，本地代理需要同样配置 `BACKEND_API_ACCESS_TOKEN`；仅本地测试时可以暂不启用该访问令牌。

Cloudflare 上线使用静态页面 + Pages Function 代理，避免把 Agent 放进 Workers。完整步骤见 [Cloudflare 前端部署](cloudflare_deployment.md)。现有 Next.js 服务端路由不能直接导出为静态站，新增构建脚本会在独立目录中排除该路由，源码和本地运行方式保留。

## 回退

代码回退点是 Git 标签 `pre-modal-deploy-2026-10-09`。若只需回到旧本地检索，将 `.env` 改回：

```dotenv
EMBEDDING_PROVIDER=local
VECTOR_STORE_BACKEND=chroma
LOCAL_INDEX_DIR=data/indexes/local_vectors
BUILD_CHROMA=1
```

然后重启原 `.venv-clean` 的后端，使用原有本地模型与索引。以上假定原配置为 Chroma，若原来使用 NumPy，恢复原值即可。保留完整本地环境以便回退；`.venv-modal` 没有安装本地模型依赖。

## 官方参考

- [硅基流动 embedding API](https://siliconflow.readme.io/reference/createembedding)
- [Modal FastAPI / ASGI](https://modal.com/docs/guide/webhooks)
- [Modal Secrets](https://modal.com/docs/guide/secrets)
- [Modal 预算](https://modal.com/docs/guide/budgets)
- [Modal Web 请求超时](https://modal.com/docs/guide/webhook-timeouts)
