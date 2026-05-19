from __future__ import annotations

import json
import re
from pathlib import Path

from .config import AppConfig
from .documents import Document
from .schemas import DocumentChunk


CONTENT_TYPES = {
    "牌意": ["正位", "逆位", "牌意", "含义", "meaning", "upright", "reversed"],
    "历史": ["历史", "起源", "文艺复兴", "history", "origin", "renaissance"],
    "象征学": ["象征", "符号", "symbol", "archetype", "原型"],
    "牌阵": ["牌阵", "spread", "阵型"],
    "占卜方法": ["占卜", "解牌", "抽牌", "divination", "reading"],
    "案例/解读": ["案例", "例子", "提问", "question", "example"],
    "入门教程": ["入门", "基础", "教程", "beginner", "guide"],
}


def extract_pdf_text(pdf_path: Path) -> tuple[list[tuple[int, str]], list[int]]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("缺少 PyMuPDF，请先安装 requirements.txt。") from exc

    pages: list[tuple[int, str]] = []
    needs_ocr: list[int] = []
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            text = normalize_text(text)
            if len(text) < 40:
                needs_ocr.append(page_index)
                continue
            pages.append((page_index, text))
    return pages, needs_ocr


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_language(text: str) -> str:
    zh_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    en_count = len(re.findall(r"[A-Za-z]", text))
    if zh_count and en_count and min(zh_count, en_count) > 20:
        return "mixed"
    if zh_count > en_count:
        return "zh"
    if en_count > 0:
        return "en"
    return "unknown"


def classify_content(text: str) -> str:
    lowered = text.lower()
    scores = {
        label: sum(1 for keyword in keywords if keyword.lower() in lowered)
        for label, keywords in CONTENT_TYPES.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "其他"


def split_page_into_chunks(source_file: str, page: int, text: str, max_chars: int = 900) -> list[DocumentChunk]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}".strip()
        else:
            if current:
                chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)

    output = []
    for idx, chunk_text in enumerate(chunks):
        output.append(
            DocumentChunk(
                chunk_id=f"{Path(source_file).stem}-p{page}-c{idx}",
                source_file=source_file,
                page=page,
                chunk_index=idx,
                language=detect_language(chunk_text),
                content_type=classify_content(chunk_text),
                text=chunk_text,
            )
        )
    return output


def ingest_pdfs_to_chunks(config: AppConfig) -> tuple[list[DocumentChunk], dict]:
    chunks: list[DocumentChunk] = []
    report = {"files": [], "total_chunks": 0, "needs_ocr": {}}
    pdfs = sorted(config.doc_dir.glob("*.pdf"))
    for pdf_path in pdfs:
        pages, needs_ocr = extract_pdf_text(pdf_path)
        file_chunks: list[DocumentChunk] = []
        for page, text in pages:
            file_chunks.extend(split_page_into_chunks(pdf_path.name, page, text))
        chunks.extend(file_chunks)
        report["files"].append(
            {
                "file": pdf_path.name,
                "text_pages": len(pages),
                "chunks": len(file_chunks),
                "needs_ocr_pages": needs_ocr,
            }
        )
        if needs_ocr:
            report["needs_ocr"][pdf_path.name] = needs_ocr
    report["total_chunks"] = len(chunks)
    return chunks, report


def write_processed_outputs(config: AppConfig, chunks: list[DocumentChunk], report: dict) -> None:
    config.ensure_dirs()
    chunks_path = config.processed_dir / "document_chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(chunk.model_dump_json(ensure_ascii=False) + "\n")
    report_path = config.reports_dir / "ingest_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def chunks_to_documents(chunks: list[DocumentChunk]) -> list[Document]:
    return [
        Document(
            page_content=chunk.text,
            metadata={
                "chunk_id": chunk.chunk_id,
                "source_file": chunk.source_file,
                "page": chunk.page,
                "chunk_index": chunk.chunk_index,
                "language": chunk.language,
                "content_type": chunk.content_type,
            },
        )
        for chunk in chunks
    ]
