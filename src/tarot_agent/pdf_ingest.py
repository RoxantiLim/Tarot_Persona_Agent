from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .config import AppConfig
from .documents import Document
from .knowledge_filter import assess_chunk_quality, load_filter_overrides, quality_report
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

_PDF_OCR_ENGINE = None


def extract_pdf_text(config: AppConfig, pdf_path: Path) -> tuple[list[tuple[int, str, str]], list[int], dict]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("缺少 PyMuPDF，请先安装 requirements.txt。") from exc

    pages: list[tuple[int, str, str]] = []
    needs_ocr: list[int] = []
    stats = {"text_pages": 0, "ocr_pages": 0, "ocr_cache_hits": 0, "ocr_error_pages": []}
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            text = normalize_text(text)
            if len(text) >= config.pdf_ocr_min_chars:
                pages.append((page_index, text, "pdf_text"))
                stats["text_pages"] += 1
                continue

            if config.pdf_ocr_enabled:
                try:
                    ocr_text, cache_hit = extract_page_with_ocr(config, pdf_path, page_index, page)
                    if cache_hit:
                        stats["ocr_cache_hits"] += 1
                    if len(ocr_text) >= config.pdf_ocr_min_chars:
                        pages.append((page_index, ocr_text, "ocr"))
                        stats["ocr_pages"] += 1
                        continue
                except Exception as exc:
                    stats["ocr_error_pages"].append({"page": page_index, "error": str(exc)})
            needs_ocr.append(page_index)
    return pages, needs_ocr, stats


def extract_page_with_ocr(config: AppConfig, pdf_path: Path, page_index: int, page) -> tuple[str, bool]:
    cache_path = pdf_ocr_cache_path(config, pdf_path, page_index)
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8"), True

    engine = pdf_ocr_engine()
    png_bytes = page.get_pixmap(dpi=config.pdf_ocr_dpi, alpha=False).tobytes("png")
    result, _ = engine(png_bytes)
    lines = []
    for item in result or []:
        if len(item) < 3:
            continue
        box, text, score = item
        if not text or score < 0.35:
            continue
        y = min(point[1] for point in box)
        x = min(point[0] for point in box)
        lines.append((y, x, str(text).strip()))
    lines.sort(key=lambda row: (row[0], row[1]))
    text = normalize_text("\n".join(line for _, _, line in lines if line))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text, False


def pdf_ocr_engine():
    global _PDF_OCR_ENGINE
    if _PDF_OCR_ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise RuntimeError("Missing rapidocr-onnxruntime dependency. Install requirements.txt first.") from exc
        _PDF_OCR_ENGINE = RapidOCR()
    return _PDF_OCR_ENGINE


def pdf_ocr_cache_path(config: AppConfig, pdf_path: Path, page_index: int) -> Path:
    return (
        config.processed_dir
        / "pdf_ocr"
        / pdf_path.stem
        / f"dpi-{config.pdf_ocr_dpi}"
        / f"page-{page_index:04d}.txt"
    )


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


def split_page_into_chunks(
    source_file: str,
    page: int,
    text: str,
    max_chars: int = 900,
    extraction_method: str = "pdf_text",
    overrides: dict[tuple[str, int], str] | None = None,
) -> list[DocumentChunk]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    paragraphs = split_oversized_paragraphs(paragraphs, max_chars)
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
    chunks = merge_short_chunks(chunks)

    output = []
    for idx, chunk_text in enumerate(chunks):
        quality = assess_chunk_quality(chunk_text, source_file, page, overrides)
        output.append(
            DocumentChunk(
                chunk_id=f"{Path(source_file).stem}-p{page}-c{idx}",
                source_file=source_file,
                page=page,
                chunk_index=idx,
                language=detect_language(chunk_text),
                content_type=classify_content(chunk_text),
                extraction_method=extraction_method,
                quality_status=quality.status,
                quality_reasons=quality.reasons,
                retrieval_weight=quality.weight,
                text=chunk_text,
            )
        )
    return output


def split_oversized_paragraphs(paragraphs: list[str], max_chars: int) -> list[str]:
    output = []
    for paragraph in paragraphs:
        output.extend(split_text_at_boundaries(paragraph, max_chars))
    return output


def split_text_at_boundaries(text: str, max_chars: int) -> list[str]:
    parts = []
    remaining = text.strip()
    while len(remaining) > max_chars:
        window = remaining[: max_chars + 1]
        sentence_breaks = [
            match.end()
            for match in re.finditer(r"[.!?。！？；;](?:\s+|$)|\n+", window)
            if match.end() >= max_chars // 2
        ]
        boundary = sentence_breaks[-1] if sentence_breaks else window.rfind(" ")
        if boundary < max_chars // 2:
            boundary = max_chars
        parts.append(remaining[:boundary].strip())
        remaining = remaining[boundary:].strip()
    if remaining:
        parts.append(remaining)
    return merge_short_chunks(parts)


def merge_short_chunks(chunks: list[str], min_chars: int = 80) -> list[str]:
    merged = []
    pending = ""
    for chunk in (item.strip() for item in chunks if item.strip()):
        if pending:
            chunk = f"{pending}\n\n{chunk}"
            pending = ""
        if len(chunk) < min_chars and not merged:
            pending = chunk
        elif len(chunk) < min_chars:
            merged[-1] = f"{merged[-1]}\n\n{chunk}"
        else:
            merged.append(chunk)
    if pending:
        if merged:
            merged[-1] = f"{merged[-1]}\n\n{pending}"
        else:
            merged.append(pending)
    return merged


def ingest_pdfs_to_chunks(config: AppConfig) -> tuple[list[DocumentChunk], dict]:
    chunks: list[DocumentChunk] = []
    report = {"files": [], "total_chunks": 0, "needs_ocr": {}}
    overrides = load_filter_overrides(config)
    pdfs = sorted(config.doc_dir.glob("*.pdf"))
    for pdf_path in pdfs:
        print(f"[ingest] processing {pdf_path.name}", flush=True)
        pages, needs_ocr, stats = extract_pdf_text(config, pdf_path)
        file_chunks: list[DocumentChunk] = []
        for page, text, extraction_method in pages:
            file_chunks.extend(
                split_page_into_chunks(
                    pdf_path.name,
                    page,
                    text,
                    extraction_method=extraction_method,
                    overrides=overrides,
                )
            )
        chunks.extend(file_chunks)
        status_counts = Counter(chunk.quality_status for chunk in file_chunks)
        report["files"].append(
            {
                "file": pdf_path.name,
                "text_pages": stats["text_pages"],
                "ocr_pages": stats["ocr_pages"],
                "ocr_cache_hits": stats["ocr_cache_hits"],
                "ocr_error_pages": stats["ocr_error_pages"],
                "chunks": status_counts["keep"] + status_counts["downrank"],
                "extracted_chunks": len(file_chunks),
                "excluded_chunks": status_counts["exclude"],
                "downranked_chunks": status_counts["downrank"],
                "needs_ocr_pages": needs_ocr,
            }
        )
        if needs_ocr:
            report["needs_ocr"][pdf_path.name] = needs_ocr
        print(
            f"[ingest] {pdf_path.name}: text={stats['text_pages']} "
            f"ocr={stats['ocr_pages']} remaining={len(needs_ocr)} "
            f"indexed={status_counts['keep'] + status_counts['downrank']} "
            f"excluded={status_counts['exclude']}",
            flush=True,
        )
    report.update(quality_report(chunks))
    report["filter_override_count"] = len(overrides)
    report["total_text_pages"] = sum(item["text_pages"] for item in report["files"])
    report["total_ocr_pages"] = sum(item["ocr_pages"] for item in report["files"])
    report["total_needs_ocr_pages"] = sum(len(item["needs_ocr_pages"]) for item in report["files"])
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
                "extraction_method": chunk.extraction_method,
                "quality_status": chunk.quality_status,
                "quality_reasons": ",".join(chunk.quality_reasons),
                "retrieval_weight": chunk.retrieval_weight,
            },
        )
        for chunk in chunks
        if chunk.quality_status != "exclude"
    ]
