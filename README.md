# Tarot Knowledge Companion + Tarot Persona Agent

一个本地 Streamlit 多页面应用，分两阶段建设：

- **塔罗学习知识库助手**：从 PDF 资料构建 RAG 知识库，用于牌意查询、主题学习和资料检索。
- **多风格塔罗占卜 Agent**：复用知识库，结合占卜师案例库和 persona profile，生成不同风格的三牌无牌阵解读。

## 当前实现状态

- 已实现 Streamlit 单应用多页面入口。
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

5. 启动应用：

```powershell
E:\for-LLM\AUXI\Tarot_Persona_Agent\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

浏览器打开：

```text
http://127.0.0.1:8501
```

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
src/tarot_agent/
scripts/
data/
Doc/
Tarotist-1/
```

`Doc/`、`Tarotist-*`、`.env`、向量索引和模型缓存都不会提交到 Git。
