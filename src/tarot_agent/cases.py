from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from .config import AppConfig


CASE_EXTRACTION_PROMPT = """你是贴吧塔罗占卜截图的结构化抽取助手。
请从截图中抽取“完整案例候选”，注意：
1. 一张图可能有多个案例，必须拆开。
2. 只保留问题、占卜师文字写出的牌面、占卜师回答。
3. 随机数不要入库。
4. 用户上传牌图但占卜师没有写出牌名时，标记为 needs_manual_card_annotation。
5. 自动脱敏昵称、联系方式和明显个人隐私。
6. 如果问题 + 牌面 + 回答不完整，quality 设为 incomplete。

返回 JSON，格式：
{
  "cases": [
    {
      "question": "...",
      "background": "...",
      "spread": "无牌阵三张牌",
      "cards": [{"name": "星币一", "orientation": "逆位"}],
      "reader_answer": "...",
      "followups": [{"speaker": "querent", "text": "..."}, {"speaker": "reader", "text": "..."}],
      "quality": "candidate",
      "notes": ""
    }
  ],
  "needs_manual_card_annotation": []
}
"""


def redact_text(text: str) -> str:
    text = re.sub(r"1[3-9]\d{9}", "[手机号]", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[邮箱]", text)
    text = re.sub(r"(微信|wx|qq)[:：]?\s*[A-Za-z0-9_-]{5,}", r"\1:[已脱敏]", text, flags=re.I)
    return text


def image_to_data_url(path: Path) -> str:
    mime = "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def extract_cases_from_image(config: AppConfig, image_path: Path, reader_id: str) -> dict[str, Any]:
    if not config.vision_api_key or not config.vision_base_url or not config.vision_model:
        return {
            "source_image": str(image_path),
            "reader_id": reader_id,
            "status": "skipped_no_vision_config",
            "cases": [],
            "needs_manual_card_annotation": [],
        }
    try:
        from openai import OpenAI
    except ImportError:
        return {
            "source_image": str(image_path),
            "reader_id": reader_id,
            "status": "skipped_missing_openai_dependency",
            "cases": [],
            "needs_manual_card_annotation": [],
        }

    client = OpenAI(api_key=config.vision_api_key, base_url=config.vision_base_url)
    response = client.chat.completions.create(
        model=config.vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": CASE_EXTRACTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}},
                ],
            }
        ],
        temperature=0,
    )
    content = response.choices[0].message.content or "{}"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {"raw": content, "cases": [], "needs_manual_card_annotation": []}
    parsed["source_image"] = str(image_path)
    parsed["reader_id"] = reader_id
    return parsed


def load_case_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def retrieve_similar_cases(config: AppConfig, reader_id: str, query: str, limit: int = 3) -> list[dict[str, Any]]:
    path = config.cases_dir / f"{reader_id}_reviewed.jsonl"
    cases = load_case_jsonl(path)
    if not cases:
        return []
    query_terms = set(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", query.lower()))
    scored = []
    for case in cases:
        blob = " ".join(
            [
                case.get("question", ""),
                case.get("background", ""),
                case.get("reader_answer", ""),
                " ".join(card.get("name", "") for card in case.get("cards", [])),
            ]
        ).lower()
        score = sum(1 for term in query_terms if term and term in blob)
        scored.append((score, case))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [case for score, case in scored[:limit] if score > 0] or [case for _, case in scored[:limit]]
