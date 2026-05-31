from __future__ import annotations

import json
import re

from .config import AppConfig
from .documents import Document
from .llm import deepseek_chat
from .prompts import KNOWLEDGE_SYSTEM_PROMPT, KNOWLEDGE_USER_TEMPLATE
from .schemas import RAGResult
from .vector_store import index_exists, load_vector_store


def retrieve_context(config: AppConfig, query: str, top_k: int = 5) -> list[Document]:
    if not index_exists(config):
        return []
    if config.retrieval_mode == "keyword":
        return keyword_search(config, query, top_k)
    store = load_vector_store(config)
    return store.similarity_search(query, k=top_k)


def keyword_search(config: AppConfig, query: str, top_k: int = 5) -> list[Document]:
    docs_file = config.data_dir / "indexes" / "local_vectors" / "documents.jsonl"
    if not docs_file.exists():
        return []

    terms = query_terms(query)
    scored: list[tuple[float, Document]] = []
    with docs_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            doc = Document(page_content=row["page_content"], metadata=row["metadata"])
            blob = doc.page_content.lower()
            metadata_blob = " ".join(str(value) for value in doc.metadata.values()).lower()
            score = sum(term_score(term, blob, metadata_blob) for term in terms)
            if score:
                scored.append((score, doc))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


def query_terms(query: str) -> set[str]:
    terms = set()
    for token in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9]+", query.lower()):
        if len(token) <= 1:
            continue
        terms.add(token)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token) and len(token) > 2:
            for size in (2, 3, 4):
                for start in range(0, max(0, len(token) - size + 1)):
                    terms.add(token[start : start + size])
    return terms


def term_score(term: str, text: str, metadata_text: str) -> float:
    score = 0.0
    if term in text:
        score += max(1.0, min(len(term), 6) / 2)
    if term in metadata_text:
        score += 0.5
    return score


def format_context(docs: list[Document]) -> str:
    if not docs:
        return "未检索到资料。"
    parts = []
    for idx, doc in enumerate(docs, start=1):
        meta = doc.metadata
        source = f"{meta.get('source_file', 'unknown')} 第 {meta.get('page', '?')} 页"
        parts.append(f"[{idx}] 来源：{source}\n{doc.page_content}")
    return "\n\n".join(parts)


def source_list(docs: list[Document]) -> list[str]:
    sources = []
    seen = set()
    for doc in docs:
        meta = doc.metadata
        source = f"{meta.get('source_file', 'unknown')}，第 {meta.get('page', '?')} 页"
        if source not in seen:
            seen.add(source)
            sources.append(source)
    return sources


def answer_knowledge_query(
    config: AppConfig,
    mode: str,
    query: str,
    card_name: str = "",
    orientation: str = "不限定",
    topic: str = "通用",
    top_k: int = 5,
) -> RAGResult:
    docs = retrieve_context(config, query, top_k=top_k)
    user_prompt = KNOWLEDGE_USER_TEMPLATE.format(
        mode=mode,
        query=query,
        card_name=card_name or "未指定",
        orientation=orientation,
        topic=topic,
        context=format_context(docs),
    )
    answer = deepseek_chat(
        config,
        [
            {"role": "system", "content": KNOWLEDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    error = "" if docs else "没有检索到知识库片段，回答依据有限。"
    return RAGResult(answer=answer, sources=source_list(docs), context_docs=docs, error=error)
