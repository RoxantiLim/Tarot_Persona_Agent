from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .schemas import DocumentChunk


OVERRIDES_FILE = "knowledge_filter_overrides.json"
QUALITY_WEIGHTS = {"keep": 1.0, "downrank": 0.45, "exclude": 0.0}
VALID_OVERRIDE_ACTIONS = {"force_keep", "force_downrank", "force_exclude"}

_COPYRIGHT_MARKERS = (
    "copyright",
    "all rights reserved",
    "library of congress",
    "isbn",
    "版权所有",
    "版權所有",
)
_PUBLICATION_MARKERS = (
    "published by",
    "penguin group",
    "registered office",
    "出版发行",
    "责任编辑",
)
_EXPLANATION_MARKERS = (
    "meaning",
    "means",
    "represents",
    "symbol",
    "indicate",
    "牌意",
    "含义",
    "意味着",
    "代表",
    "象征",
    "表示",
    "说明",
)


@dataclass(frozen=True)
class QualityAssessment:
    status: str
    reasons: list[str]
    weight: float


def overrides_path(config) -> Path:
    return config.data_dir / OVERRIDES_FILE


def load_filter_overrides(config) -> dict[tuple[str, int], str]:
    path = overrides_path(config)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    overrides = {}
    for row in payload.get("overrides", []):
        try:
            source_file = str(row["source_file"]).strip()
            page = int(row["page"])
            action = str(row["action"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if source_file and page > 0 and action in VALID_OVERRIDE_ACTIONS:
            overrides[(source_file, page)] = action
    return overrides


def list_filter_overrides(config) -> list[dict[str, object]]:
    return [
        {"source_file": source_file, "page": page, "action": action}
        for (source_file, page), action in sorted(load_filter_overrides(config).items())
    ]


def set_filter_override(config, source_file: str, page: int, action: str) -> None:
    overrides = load_filter_overrides(config)
    key = (source_file.strip(), int(page))
    if action == "clear":
        overrides.pop(key, None)
    elif action in VALID_OVERRIDE_ACTIONS:
        overrides[key] = action
    else:
        raise ValueError(f"Unsupported knowledge-filter override: {action}")
    save_filter_overrides(config, overrides)


def save_filter_overrides(config, overrides: dict[tuple[str, int], str]) -> None:
    path = overrides_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"source_file": source_file, "page": page, "action": action}
        for (source_file, page), action in sorted(overrides.items())
        if source_file and page > 0 and action in VALID_OVERRIDE_ACTIONS
    ]
    path.write_text(
        json.dumps({"overrides": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def assess_chunk_quality(
    text: str,
    source_file: str = "",
    page: int = 0,
    overrides: dict[tuple[str, int], str] | None = None,
) -> QualityAssessment:
    automatic = _assess_chunk_quality(text)
    action = (overrides or {}).get((source_file, page))
    if action == "force_keep":
        return QualityAssessment("keep", [*automatic.reasons, "override:force_keep"], 1.0)
    if action == "force_downrank":
        return QualityAssessment(
            "downrank",
            [*automatic.reasons, "override:force_downrank"],
            QUALITY_WEIGHTS["downrank"],
        )
    if action == "force_exclude":
        return QualityAssessment("exclude", [*automatic.reasons, "override:force_exclude"], 0.0)
    return automatic


def _assess_chunk_quality(text: str) -> QualityAssessment:
    stripped = text.strip()
    lowered = stripped.lower()
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]

    if _starts_with_any(lowered, ("table of contents", "contents\n", "目录", "目錄")):
        return _assessment("exclude", "table_of_contents")
    if _looks_like_dotted_contents(stripped):
        return _assessment("exclude", "table_of_contents")
    if _starts_with_any(lowered, ("index\n", "index ", "索引", "索 引")):
        return _assessment("exclude", "index_page")
    if _starts_with_any(lowered, ("bibliography", "references\n", "参考书目", "参考文献")):
        return _assessment("exclude", "reference_list")
    if _looks_like_citation_list(stripped, lines):
        return _assessment("exclude", "reference_list")
    if any(marker in lowered for marker in _COPYRIGHT_MARKERS):
        return _assessment("exclude", "copyright_page")
    if _looks_like_publication_info(stripped):
        return _assessment("exclude", "publication_info")
    if _starts_with_any(
        lowered,
        ("acknowledgements", "acknowledgments", "dedication", "about the author", "致谢", "献给"),
    ):
        return _assessment("exclude", "front_matter")
    if len(stripped) < 80:
        return _assessment("exclude", "short_fragment")

    if _looks_like_pure_list(stripped, lines):
        return _assessment("exclude", "pure_list")
    if _looks_like_title_page(stripped, lines):
        return _assessment("exclude", "title_page")

    reasons = []
    if _looks_list_heavy(stripped, lines):
        reasons.append("list_heavy")
    if len(stripped) < 160:
        reasons.append("short_text")
    if reasons:
        return QualityAssessment("downrank", reasons, QUALITY_WEIGHTS["downrank"])
    return QualityAssessment("keep", [], QUALITY_WEIGHTS["keep"])


def quality_report(chunks: Iterable[DocumentChunk]) -> dict[str, object]:
    rows = list(chunks)
    status_counts = Counter(chunk.quality_status for chunk in rows)
    reason_counts = Counter(reason for chunk in rows for reason in chunk.quality_reasons)
    review_pages: dict[tuple[str, int], dict[str, object]] = {}

    for chunk in rows:
        if chunk.quality_status == "keep":
            continue
        key = (chunk.source_file, chunk.page)
        page_row = review_pages.setdefault(
            key,
            {
                "source_file": chunk.source_file,
                "page": chunk.page,
                "quality_status": chunk.quality_status,
                "quality_reasons": [],
                "preview": chunk.text[:220].replace("\n", " | "),
            },
        )
        if chunk.quality_status == "exclude":
            page_row["quality_status"] = "exclude"
        page_row["quality_reasons"] = sorted(
            set(page_row["quality_reasons"]) | set(chunk.quality_reasons)
        )

    return {
        "total_extracted_chunks": len(rows),
        "total_chunks": status_counts["keep"] + status_counts["downrank"],
        "total_excluded_chunks": status_counts["exclude"],
        "total_downranked_chunks": status_counts["downrank"],
        "quality_reason_counts": dict(sorted(reason_counts.items())),
        "review_pages": sorted(review_pages.values(), key=lambda row: (row["source_file"], row["page"])),
    }


def _assessment(status: str, reason: str) -> QualityAssessment:
    return QualityAssessment(status, [reason], QUALITY_WEIGHTS[status])


def _starts_with_any(text: str, prefixes: tuple[str, ...]) -> bool:
    return any(text.startswith(prefix) for prefix in prefixes)


def _short_line_ratio(lines: list[str]) -> float:
    if not lines:
        return 0.0
    short_lines = sum(len(line) <= 48 for line in lines)
    return short_lines / len(lines)


def _has_explanation(text: str) -> bool:
    lowered = text.lower()
    marker_count = sum(marker in lowered for marker in _EXPLANATION_MARKERS)
    sentence_count = _sentence_count(text)
    return marker_count > 0 or sentence_count >= 3


def _looks_like_pure_list(text: str, lines: list[str]) -> bool:
    return (
        len(lines) >= 8
        and _short_line_ratio(lines) >= 0.75
        and _sentence_count(text) <= 2
        and not _contains_explanation_marker(text)
    )


def _looks_list_heavy(text: str, lines: list[str]) -> bool:
    if len(lines) < 8 or _short_line_ratio(lines) < 0.75:
        return False
    sentence_count = _sentence_count(text)
    return 2 < sentence_count <= max(4, len(lines) // 4)


def _contains_explanation_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _EXPLANATION_MARKERS)


def _looks_like_publication_info(text: str) -> bool:
    lowered = text.lower()
    marker_count = sum(marker in lowered for marker in _PUBLICATION_MARKERS)
    return marker_count >= 2 or (
        marker_count == 1
        and len(text) < 240
        and _sentence_count(text) <= 1
    )


def _looks_like_dotted_contents(text: str) -> bool:
    dotted_entries = len(re.findall(r"\.{5,}\s*\d+", text))
    dot_runs = len(re.findall(r"\.{8,}", text))
    return dotted_entries >= 2 or dot_runs >= 3


def _looks_like_citation_list(text: str, lines: list[str]) -> bool:
    numbered_lines = sum(bool(re.match(r"^\d+\s", line)) for line in lines)
    lowered = text.lower()
    citation_signals = sum(
        marker in lowered
        for marker in ("ibid", "page ", "vol.", "press", "library", "journal", "http://", "https://")
    )
    year_signals = len(re.findall(r"\b(?:1[4-9]\d{2}|20\d{2})\b", text))
    return len(lines) >= 5 and numbered_lines >= 3 and citation_signals + year_signals >= 3


def _sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?。！？；;]", text))


def _looks_like_title_page(text: str, lines: list[str]) -> bool:
    if not 2 <= len(lines) <= 12 or len(text) >= 240:
        return False
    short_line_ratio = _short_line_ratio(lines)
    if _sentence_count(text) <= 1:
        return short_line_ratio >= 0.8
    return short_line_ratio >= 0.7 and _uppercase_ratio(text) >= 0.75


def _uppercase_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    return sum(char.isupper() for char in letters) / len(letters)
