# Tarot Persona Agent - Next Chat Handoff

Updated: 2026-05-31

## Read First

This repository is a personal learning and internship-demo project. Read:

1. `AGENTS.md`
2. `docs/NEXT_CHAT_HANDOFF.md`
3. `docs/PROJECT_PLAN_AND_PROGRESS.md`

Do not upload or commit local private materials, API keys, OCR cache, indexes, screenshots, or case JSONL files.

## Project Goal

Build one Streamlit application with two related projects:

1. A tarot learning knowledge-base assistant for study, lookup, and review.
2. A multi-persona tarot reading Agent that reuses the knowledge base and imitates the natural styles of real tarot readers from reviewed historical cases.

The app has:

- Knowledge-base assistant
- Tarot reading Agent
- Data and persona management
- Project status page
- Normal user view and developer view

## Main Technology Stack

- Python + Streamlit
- DeepSeek OpenAI-compatible API
- LangChain-compatible document structures
- LangGraph Agent workflow
- `BAAI/bge-m3` local embeddings
- ChromaDB primary vector store
- NumPy vector-store fallback
- PyMuPDF PDF parsing
- RapidOCR ONNX Runtime for local screenshot and scanned-PDF OCR

## Local Environment

Use the clean non-Anaconda environment:

```text
Official Python: E:\for-LLM\AUXI\Python311
Virtual environment: E:\for-LLM\AUXI\Tarot_Persona_Agent\.venv-clean
```

Start the app:

```powershell
cd E:\for-LLM\Tarot_Persona_Agent
powershell -ExecutionPolicy Bypass -File scripts\start_app.ps1
```

Open:

```text
http://127.0.0.1:8501
```

Stop:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop_app.ps1
```

Logs:

```text
logs/streamlit.err.log
logs/streamlit.out.log
logs/ingest.err.log
logs/ingest.out.log
```

## Current Local Configuration

The local `.env` is ignored by Git and contains secrets. Do not print or commit the API key.

Relevant non-secret values:

```text
DEEPSEEK_MODEL=deepseek-v4-pro
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DEVICE=cuda
RETRIEVAL_MODE=vector
VECTOR_STORE_BACKEND=chroma
BUILD_CHROMA=1
PDF_OCR_ENABLED=1
PDF_OCR_DPI=180
PDF_OCR_MIN_CHARS=40
```

## Knowledge Base Status

The complete scanned-PDF OCR and ChromaDB pipeline has been implemented and locally rebuilt:

```text
PDF text extraction
-> OCR fallback for scanned pages
-> page-level OCR cache
-> paragraph chunks with metadata
-> bge-m3 embeddings
-> ChromaDB primary index
-> NumPy fallback index
```

Latest ingest report:

| Metric | Value |
|---|---:|
| Total chunks | 1811 |
| Native PDF text pages | 806 |
| OCR pages | 310 |
| Remaining needs_ocr pages | 11 |
| Primary vector backend | chroma |

Scanned books:

| File | OCR result |
|---|---:|
| `《经典塔罗攻略秘籍》1.pdf` | 89 / 89 pages |
| `《经典塔罗攻略秘籍》2.pdf` | 99 / 99 pages |
| `《经典塔罗攻略秘籍》3.pdf` | 119 / 120 pages |

Validated queries:

- Normal query: `圣杯六 正位 感情 复合`
- OCR query: `维斯康提 米兰 公爵 塔罗 历史`

The OCR query correctly returns `《经典塔罗攻略秘籍》1.pdf`, page 25, with:

```text
extraction_method=ocr
```

## Persona Agent Status

The Agent supports:

- Random three-card draws from all 78 cards with random upright/reversed orientation
- User-specified three-card input
- Reader selection
- Side-by-side same-question comparison
- Session history
- Developer debug view
- Knowledge retrieval
- Similar-case retrieval
- Persona profile loading
- Response generation
- Optional style and grounding self-check

Reviewed case counts:

| Reader | Reviewed | Needs review |
|---|---:|---:|
| `tarotist_1` | 140 | 13 |
| `tarotist_2` | 120 | 2 |

Persona profiles:

```text
data/personas/tarotist_1.json
data/personas/tarotist_2.json
```

## Important Stability History

The original venv was created from:

```text
E:\Anaconda\python.exe
```

Repeated Streamlit crashes occurred as Windows-level `python.exe` APPCRASH events involving `combase.dll`, without Python traceback. A low virtual-memory event was also observed.

The project has since moved to official Python 3.11 and `.venv-clean`.

During GPU index rebuild, the default embedding batch size used nearly all 6 GB VRAM and stalled. `BgeM3Embeddings.embed_documents()` now explicitly uses:

```python
batch_size=8
```

This kept GPU usage around 3.8-4.3 GB during the successful rebuild.

## Current Uncommitted Work

The latest ChromaDB + scanned-PDF OCR work is implemented locally but has not yet been committed or pushed.

Expected modified files:

```text
.env.example
app.py
docs/PROJECT_PLAN_AND_PROGRESS.md
docs/NEXT_CHAT_HANDOFF.md
scripts/ingest_documents.py
src/tarot_agent/config.py
src/tarot_agent/embeddings.py
src/tarot_agent/pdf_ingest.py
src/tarot_agent/schemas.py
src/tarot_agent/vector_store.py
```

Latest pushed commit:

```text
1011c4e Improve runtime stability and clean Python setup
```

## Git Privacy Rules

These local paths must remain ignored and must not be committed:

```text
.env
Doc/
Tarotist-*/
data/indexes/
data/processed/
data/reports/
data/cases/*_candidates.jsonl
data/cases/*_reviewed.jsonl
data/cases/*_needs_review.jsonl
logs/
```

## Recommended Next Steps

1. Manually test the running Streamlit app:
   - Knowledge query
   - OCR-backed knowledge query
   - Single-reader tarot Agent
   - Same-question side-by-side comparison
2. Inspect logs after tests and confirm no crash.
3. Commit and push the ChromaDB + scanned-PDF OCR version.
4. Review the remaining 11 `needs_ocr` pages and classify likely cover, blank, or low-value pages.
5. Improve the progress/status UI:
   - Display active backend: ChromaDB or NumPy fallback
   - Display OCR status per PDF
   - Display native-text versus OCR chunk counts
6. Build a small evaluation dataset for internship presentation:
   - Fixed knowledge queries
   - Fixed tarot questions and cards
   - Retrieval source checks
   - Persona style comparison
   - Latency and failure-rate notes

## Suggested First Prompt for the Next Chat

```text
请先阅读 AGENTS.md、docs/NEXT_CHAT_HANDOFF.md 和 docs/PROJECT_PLAN_AND_PROGRESS.md。
这是同一个 Tarot_Persona_Agent 项目的新对话。请先检查 git status 和当前 Streamlit 运行状态，不要修改或提交 .env、Doc、Tarotist 截图、案例 JSONL、OCR 缓存和向量索引。
ChromaDB + 扫描 PDF OCR 已经实现并完成本地重建，但还没有提交。请先帮我验证网页中的知识库查询、OCR 资料命中、单占卜师和同题并列功能，再根据结果决定是否提交 GitHub。
```
