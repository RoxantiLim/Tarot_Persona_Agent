# Tarot Knowledge Companion + Tarot Persona Agent

一个本地塔罗知识库与多风格占卜 Agent 项目，分两层使用：

- **Streamlit 内部后台**：用于 PDF 入库、人工复核、案例审核、画像编辑和项目状态检查。
- **Next.js 用户前端**：用于展示型首页、知识库助手和三牌占卜 Agent。
- **FastAPI 本机后端**：把现有 Python RAG/Agent 能力包装给前端调用。

## 当前实现状态

- 已实现 Streamlit 单应用多页面后台入口。
- 已实现 FastAPI 本机 API 入口。
- 已实现 Next.js + TypeScript + Tailwind CSS 展示型用户前端。
- 已实现 PDF 文本抽取、页内段落切块、入库报告。
- 已实现 `BAAI/bge-m3` 本地 embedding。
- 默认使用本地 numpy 余弦向量索引，避免 Windows 上 ChromaDB Rust 查询层不稳定。
- ChromaDB 代码仍保留，可通过 `.env` 设置 `BUILD_CHROMA=1` 实验。
- 已实现 DeepSeek OpenAI-compatible 生成接口。
- 已实现 LangGraph persona agent 框架。
- 已实现截图案例视觉抽取脚本接口，但需要配置 vision model 后才会调用。

## 快速开始

1. 复制配置：

```powershell
Copy-Item .env.example .env
```

2. 在 `.env` 填入：

```text
DEEPSEEK_API_KEY=你的 DeepSeek API Key
```

3. 创建 AUXI 专用虚拟环境并安装依赖：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_env.ps1
```

4. 构建知识库：

```powershell
E:\for-LLM\AUXI\Tarot_Persona_Agent\.venv\Scripts\python.exe scripts\ingest_documents.py
```

5. 启动 Streamlit 内部后台：

```powershell
E:\for-LLM\AUXI\Tarot_Persona_Agent\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

浏览器打开：

```text
http://127.0.0.1:8501
```

## 本机展示型前端

第一阶段前端只面向本机使用，不做公网部署。

启动 FastAPI 后端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_api.ps1
```

默认地址：

```text
http://127.0.0.1:8787
http://127.0.0.1:8787/docs
```

启动 Next.js 用户前端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_web.ps1
```

默认地址：

```text
http://127.0.0.1:3000
```

页面：

```text
/           首页
/reading    三牌占卜 Agent
/knowledge  知识库助手
/status     本机状态
```

说明：

- Streamlit 后台仍然保留在 `http://127.0.0.1:8501`。
- DeepSeek API Key 只保留在 Python `.env` 中，不写入前端。
- 前端默认连接 `http://127.0.0.1:8787`；如需修改，可设置 `NEXT_PUBLIC_API_BASE_URL`。

## 第一版边界

- PDF 第一版只处理可直接提取文字的页面。
- 扫描页会标记为 `needs_ocr` 并跳过。
- 牌图案例第一版不自动识别，后续人工标注后再入库。
- 生成模型使用 DeepSeek。
- embedding 使用本地 `BAAI/bge-m3`。
- GPU 版 PyTorch 使用 `torch==2.6.0+cu124`。

## 目录

```text
app.py
api/
web/
src/tarot_agent/
scripts/
data/
Doc/
Tarotist-1/
```

`Doc/`、`Tarotist-*`、`.env`、向量索引和模型缓存都不会提交到 Git。
