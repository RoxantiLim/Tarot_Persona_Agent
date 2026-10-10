from __future__ import annotations

from pathlib import Path
import os
import secrets
import threading
import time
from collections import deque
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.tarot_agent.agent_graph import run_persona_reading
from src.tarot_agent.cards import card_display_names, random_three_card_draw
from src.tarot_agent.config import AppConfig
from src.tarot_agent.documents import Document
from src.tarot_agent.persona import DEFAULT_PERSONAS, load_persona
from src.tarot_agent.rag_chain import answer_knowledge_query, retrieve_context
from src.tarot_agent.vector_store import index_exists, local_index_path, validate_local_index


_startup_config = AppConfig.load()
app = FastAPI(
    title="Tarot Persona API", version="0.2.0",
    docs_url="/docs" if os.getenv("PUBLIC_API_DOCS", "1") == "1" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if os.getenv("PUBLIC_API_DOCS", "1") == "1" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_startup_config.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_request_times: deque[float] = deque()
_rate_lock = threading.Lock()


@app.middleware("http")
async def protect_api(request: Request, call_next):
    config = get_config()
    if request.method != "OPTIONS" and request.url.path.startswith("/api/") and request.url.path != "/api/health":
        if config.api_access_token:
            supplied = request.headers.get("authorization", "")
            if not secrets.compare_digest(supplied.encode("utf-8"), f"Bearer {config.api_access_token}".encode("utf-8")):
                return JSONResponse({"detail": "访问凭据无效。"}, status_code=401)
        if config.api_access_token and request.method == "POST":
            limit = int(os.getenv("API_REQUESTS_PER_MINUTE", "10"))
            now = time.monotonic()
            with _rate_lock:
                while _request_times and now - _request_times[0] >= 60:
                    _request_times.popleft()
                if len(_request_times) >= limit:
                    return JSONResponse({"detail": "请求过于频繁，请稍后再试。"}, status_code=429, headers={"Retry-After": "60"})
                _request_times.append(now)
    return await call_next(request)


class CardInput(BaseModel):
    name: str
    orientation: Literal["正位", "逆位"] = "正位"


class KnowledgeQueryRequest(BaseModel):
    mode: Literal["牌意查询", "主题学习", "资料检索"] = "牌意查询"
    query: str = Field(min_length=1, max_length=3000)
    card_name: str = ""
    orientation: str = "不限定"
    topic: str = "通用"
    top_k: int = Field(default=5, ge=2, le=10)


class ReadingGenerateRequest(BaseModel):
    reader_id: str = "tarotist_1"
    question: str = Field(min_length=1, max_length=2000)
    cards: list[CardInput] = Field(min_length=3, max_length=3)
    include_check: bool = False


def get_config() -> AppConfig:
    return AppConfig.load()


def document_payload(doc: Document) -> dict[str, Any]:
    metadata = dict(doc.metadata)
    return {
        "content": doc.page_content,
        "source_file": metadata.get("source_file", "unknown"),
        "page": metadata.get("page"),
        "quality_status": metadata.get("quality_status", "keep"),
        "quality_reasons": metadata.get("quality_reasons", ""),
        "retrieval_score": metadata.get("retrieval_score"),
        "rerank_score": metadata.get("rerank_score"),
        "metadata": metadata,
    }


def public_error(exc: Exception) -> HTTPException:
    message = str(exc)
    if "No knowledge index found" in message:
        detail = "知识库索引还没有准备好。请先运行 scripts\\ingest_documents.py 构建索引。"
    elif "Embedding index mismatch" in message:
        detail = "当前 embedding 配置与索引不匹配，请先重建 API 索引。"
    elif "Embedding API" in message:
        detail = "向量服务暂时不可用，请检查 EMBEDDING_API_KEY、额度和网络。"
    elif "timed out" in message.lower() or "timeout" in message.lower():
        detail = "模型请求超时。请稍后重试，或降低本次请求复杂度。"
    elif "api" in message.lower() and "key" in message.lower():
        detail = "模型 API key 似乎没有配置好。请检查 .env 中的 DEEPSEEK_API_KEY。"
    else:
        detail = "暂时无法完成请求，请确认本地服务、资料库索引和 .env 配置已经准备好。"
    return HTTPException(
        status_code=500,
        detail=detail,
    )


def count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def count_files(path: Path, pattern: str = "*") -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob(pattern) if item.is_file())


@app.get("/api/health")
def health() -> dict[str, Any]:
    config = get_config()
    local_index_file = local_index_path(config) / "vectors.npy"
    chroma_index_file = config.chroma_dir / "chroma.sqlite3"
    processed_chunks_file = config.processed_dir / "document_chunks.jsonl"
    reviewed_case_files = list(config.cases_dir.glob("*_reviewed.jsonl")) if config.cases_dir.exists() else []
    reviewed_cases_count = sum(count_jsonl_lines(path) for path in reviewed_case_files)
    has_index = index_exists(config)
    has_key = bool(config.deepseek_api_key.strip())
    status_messages = []
    index_compatible = False
    index_info = {}
    if local_index_file.exists():
        try:
            index_info = validate_local_index(config)
            index_compatible = True
        except (RuntimeError, ValueError, OSError, KeyError):
            status_messages.append("向量索引与配置不匹配或文件不完整，请重新构建索引。")
    if config.embedding_provider == "api" and not config.embedding_api_key.strip():
        status_messages.append("EMBEDDING_API_KEY 未配置，向量检索暂不可用。")
    if not has_key:
        status_messages.append("DEEPSEEK_API_KEY 未配置，生成类功能会返回配置提示。")
    if not has_index:
        status_messages.append("知识库索引未找到，请运行 scripts\\ingest_documents.py。")
    return {
        "ok": True,
        "deepseek_configured": has_key,
        "index_exists": has_index,
        "local_index_exists": local_index_file.exists(),
        "chroma_index_exists": chroma_index_file.exists(),
        "retrieval_mode": config.retrieval_mode,
        "vector_store_backend": config.vector_store_backend,
        "embedding_model": config.embedding_model,
        "embedding_provider": config.embedding_provider,
        "embedding_configured": config.embedding_provider == "local" or bool(config.embedding_api_key.strip()),
        "index_compatible": index_compatible,
        "embedding_device": config.embedding_device,
        "llm_model": config.deepseek_model,
        "knowledge_chunks_count": index_info.get("count", count_jsonl_lines(processed_chunks_file)),
        "reviewed_cases_count": reviewed_cases_count,
        "persona_files_count": count_files(config.personas_dir, "*.json"),
        "cards_count": len(card_display_names()),
        "readers_count": len(DEFAULT_PERSONAS),
        "status_messages": status_messages,
    }


@app.get("/api/cards")
def cards() -> dict[str, Any]:
    return {
        "cards": card_display_names(),
        "orientations": ["正位", "逆位"],
        "sample_draw": random_three_card_draw(),
    }


@app.get("/api/readers")
def readers() -> dict[str, Any]:
    config = get_config()
    rows = []
    for reader_id in sorted(DEFAULT_PERSONAS):
        persona = load_persona(config, reader_id)
        rows.append(
            {
                "reader_id": persona.reader_id,
                "display_name": persona.display_name,
                "tone": persona.tone,
                "reasoning_style": persona.reasoning_style,
            }
        )
    return {"readers": rows}


@app.post("/api/knowledge/query")
def knowledge_query(request: KnowledgeQueryRequest) -> dict[str, Any]:
    config = get_config()
    try:
        if request.mode == "资料检索":
            docs = retrieve_context(config, request.query, top_k=request.top_k)
            return {
                "answer": "",
                "error": "" if docs else "没有找到相关内容。换个说法试试。",
                "sources": [
                    f"{doc.metadata.get('source_file', 'unknown')}，第 {doc.metadata.get('page', '?')} 页"
                    for doc in docs
                ],
                "documents": [document_payload(doc) for doc in docs],
            }
        result = answer_knowledge_query(
            config=config,
            mode=request.mode,
            query=request.query,
            card_name=request.card_name,
            orientation=request.orientation,
            topic=request.topic,
            top_k=request.top_k,
        )
        return {
            "answer": result.answer,
            "error": result.error,
            "sources": result.sources,
            "documents": [document_payload(doc) for doc in result.context_docs],
        }
    except Exception as exc:
        raise public_error(exc) from exc


@app.post("/api/reading/generate")
def reading_generate(request: ReadingGenerateRequest) -> dict[str, Any]:
    config = get_config()
    try:
        result = run_persona_reading(
            config=config,
            reader_id=request.reader_id,
            question=request.question,
            cards=[card.model_dump() for card in request.cards],
            include_check=request.include_check,
        )
        return {
            "answer": result.answer,
            "debug": result.debug,
            "knowledge_docs": [document_payload(doc) for doc in result.knowledge_docs],
            "similar_cases": result.similar_cases,
        }
    except Exception as exc:
        raise public_error(exc) from exc
