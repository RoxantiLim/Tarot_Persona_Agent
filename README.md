# Tarot Knowledge Companion + Tarot Persona Agent

本项目是一个本地 Streamlit 多页面应用，分两阶段：

- **塔罗学习知识库助手**：基于 PDF 文档构建 RAG 知识库，用于牌意查询、主题学习和资料检索。
- **多风格塔罗占卜 Agent**：复用知识库，结合占卜师案例库和 persona profile，生成不同风格的三牌无牌阵解读。

## 快速开始

1. 复制配置：

```powershell
Copy-Item .env.example .env
```

2. 在 `.env` 填入 `DEEPSEEK_API_KEY`。

3. 安装依赖。推荐把虚拟环境和缓存放到 `E:\for-LLM\AUXI`：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_env.ps1
```

也可以直接使用当前 Python 环境：

```powershell
pip install -r requirements.txt
```

4. 构建知识库：

```powershell
python scripts\ingest_documents.py
```

5. 启动应用：

```powershell
python -m streamlit run app.py
```

## 当前第一版边界

- PDF 只处理可直接提取文字的页面；扫描页会标记为 `needs_ocr` 并跳过。
- embedding 使用本地 `BAAI/bge-m3`。
- 生成模型使用 DeepSeek 的 OpenAI 兼容接口。
- 案例抽取脚本已预留视觉模型接口；没有配置视觉模型时不会调用 API。
- 牌图案例第一版不自动识别，作为待人工标注数据处理。

## 目录

```text
app.py
src/tarot_agent/
scripts/
data/
Doc/
Tarotist-1/
```
