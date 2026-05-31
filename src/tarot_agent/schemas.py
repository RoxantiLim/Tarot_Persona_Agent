from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    chunk_id: str
    source_file: str
    page: int
    chunk_index: int
    language: Literal["zh", "en", "mixed", "unknown"] = "unknown"
    content_type: str = "其他"
    extraction_method: Literal["pdf_text", "ocr"] = "pdf_text"
    text: str


class TarotCardInput(BaseModel):
    name: str
    orientation: Literal["正位", "逆位"] = "正位"


class TarotCase(BaseModel):
    case_id: str
    reader_id: str
    source_images: list[str] = Field(default_factory=list)
    case_type: str = "text_card_answer"
    question: str
    background: str = ""
    spread: str = "无牌阵三张牌"
    cards: list[TarotCardInput] = Field(default_factory=list)
    reader_answer: str
    followups: list[dict[str, str]] = Field(default_factory=list)
    privacy_status: str = "auto_redacted_pending_review"
    quality: str = "candidate"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PersonaProfile(BaseModel):
    reader_id: str
    display_name: str
    tone: str
    answer_structure: list[str]
    common_phrases: list[str] = Field(default_factory=list)
    reasoning_style: str
    avoid: list[str] = Field(default_factory=list)


class RAGResult(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
    context_docs: list[Any] = Field(default_factory=list)
    error: str = ""

    class Config:
        arbitrary_types_allowed = True


class AgentResult(BaseModel):
    answer: str
    debug: dict[str, Any] = Field(default_factory=dict)
    knowledge_docs: list[Any] = Field(default_factory=list)
    similar_cases: list[dict[str, Any]] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
