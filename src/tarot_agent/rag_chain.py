from __future__ import annotations

from .config import AppConfig
from .documents import Document
from .llm import deepseek_chat
from .prompts import KNOWLEDGE_SYSTEM_PROMPT, KNOWLEDGE_USER_TEMPLATE
from .schemas import RAGResult
from .vector_store import index_exists, load_vector_store


def retrieve_context(config: AppConfig, query: str, top_k: int = 5) -> list[Document]:
    if not index_exists(config):
        return []
    store = load_vector_store(config)
    return store.similarity_search(query, k=top_k)


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
    error = "" if docs else "没有检索到知识库片段，回答可能只包含配置提示或依据有限。"
    return RAGResult(answer=answer, sources=source_list(docs), context_docs=docs, error=error)
