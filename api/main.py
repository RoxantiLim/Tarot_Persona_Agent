from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.tarot_agent.agent_graph import run_persona_reading
from src.tarot_agent.cards import card_display_names, random_three_card_draw
from src.tarot_agent.config import AppConfig
from src.tarot_agent.documents import Document
from src.tarot_agent.persona import DEFAULT_PERSONAS, load_persona
from src.tarot_agent.rag_chain import answer_knowledge_query, retrieve_context
from src.tarot_agent.vector_store import index_exists


app = FastAPI(title="Tarot Persona Local API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CardInput(BaseModel):
    name: str
    orientation: Literal["正位", "逆位"] = "正位"


class KnowledgeQueryRequest(BaseModel):
    mode: Literal["牌意查询", "主题学习", "资料检索"] = "牌意查询"
    query: str = Field(min_length=1)
    card_name: str = ""
    orientation: str = "不限定"
    topic: str = "通用"
    top_k: int = Field(default=5, ge=2, le=10)


class ReadingGenerateRequest(BaseModel):
    reader_id: str = "tarotist_1"
    question: str = Field(min_length=1)
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
    return HTTPException(
        status_code=500,
        detail="暂时无法完成请求，请确认本地服务和资料库已经准备好。",
    )


@app.get("/api/health")
def health() -> dict[str, Any]:
    config = get_config()
    return {
        "ok": True,
        "index_exists": index_exists(config),
        "retrieval_mode": config.retrieval_mode,
        "vector_store_backend": config.vector_store_backend,
        "embedding_model": config.embedding_model,
        "llm_model": config.deepseek_model,
        "cards_count": len(card_display_names()),
        "readers_count": len(DEFAULT_PERSONAS),
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
