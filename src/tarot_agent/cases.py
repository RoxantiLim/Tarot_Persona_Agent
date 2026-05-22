from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from .config import AppConfig


CASE_EXTRACTION_PROMPT = """你是贴吧塔罗占卜截图的结构化抽取助手。

请从截图中抽取“完整案例候选”。规则：
1. 一张截图可能包含多个案例，必须拆开。
2. 只保留：提问者问题、必要背景、占卜师文字写出的牌面、占卜师回答、后续追问/反馈。
3. 随机数只用于当时抽牌，不要写入结构化案例。
4. 如果提问者上传了牌图，但占卜师没有在文字里写出牌名，请放入 needs_manual_card_annotation，不要猜牌。
5. 自动脱敏昵称、联系方式、明显个人隐私；不要保留真实账号名。
6. 只有“问题 + 牌面 + 占卜师回答”都完整，quality 才能设为 candidate；否则设为 incomplete。
7. cards.orientation 只能是“正位”或“逆位”；无法确认时设为 incomplete。
8. 输出必须是 JSON 对象，不要 Markdown，不要解释。

返回格式：
{
  "cases": [
    {
      "question": "...",
      "background": "...",
      "spread": "无牌阵三张牌",
      "cards": [
        {"name": "星币一", "orientation": "逆位"}
      ],
      "reader_answer": "...",
      "followups": [
        {"speaker": "querent", "text": "..."},
        {"speaker": "reader", "text": "..."}
      ],
      "quality": "candidate",
      "notes": ""
    }
  ],
  "needs_manual_card_annotation": [
    {
      "question": "...",
      "reason": "提问者上传牌图，但文字中没有完整牌名"
    }
  ]
}
"""


OCR_EXTRACTION_PROMPT = CASE_EXTRACTION_PROMPT + """

下面不是原图，而是本地 OCR 识别出的文本。OCR 可能有错别字、漏字、顺序轻微错乱。
请尽量根据贴吧评论结构恢复案例，但不要臆造牌名或回答。
"""


BATCH_OCR_EXTRACTION_PROMPT = """你是贴吧塔罗占卜截图的结构化抽取助手。

下面会给你多张截图的 OCR 文本，每段以 === IMAGE: 文件名 === 开头。OCR 可能有错别字、漏字、顺序轻微错乱。

请逐张图片抽取“完整案例候选”。规则：
1. 一张截图可能包含多个案例，必须拆开。
2. 只保留：提问者问题、必要背景、占卜师文字写出的牌面、占卜师回答、后续追问/反馈。
3. 随机数只用于当时抽牌，不要写入结构化案例。
4. 如果提问者上传了牌图，但占卜师没有在文字里写出牌名，请放入 needs_manual_card_annotation，不要猜牌。
5. 自动脱敏昵称、联系方式、明显个人隐私；不要保留真实账号名。
6. 只有“问题 + 牌面 + 占卜师回答”都完整，quality 才能设为 candidate；否则设为 incomplete。
7. cards.orientation 只能是“正位”或“逆位”；无法确认时设为 incomplete。
8. 输出必须是 JSON 对象，不要 Markdown，不要解释。

返回格式：
{
  "images": [
    {
      "source_image": "截图文件名.jpg",
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
  ]
}
"""


def redact_text(text: str) -> str:
    text = re.sub(r"1[3-9]\d{9}", "[手机号]", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[邮箱]", text)
    text = re.sub(r"(微信|wx|qq)[:：]?\s*[A-Za-z0-9_-]{5,}", r"\1:[已脱敏]", text, flags=re.I)
    text = re.sub(r"回复\s+[^:：\s]{1,24}[:：]", "回复 [用户]:", text)
    return text.strip()


def image_to_data_url(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def extract_cases_from_image(config: AppConfig, image_path: Path, reader_id: str) -> dict[str, Any]:
    vision_error: dict[str, str] | None = None
    if config.vision_api_key and config.vision_base_url and config.vision_model:
        result, vision_error = try_extract_with_vision(config, image_path, reader_id)
        if result is not None:
            return result

    return extract_cases_from_ocr_text(config, image_path, reader_id, vision_error=vision_error)


def try_extract_with_vision(
    config: AppConfig, image_path: Path, reader_id: str
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    try:
        from openai import OpenAI
    except ImportError:
        return None, {"error_type": "ImportError", "error": "missing openai dependency"}

    client = OpenAI(api_key=config.vision_api_key, base_url=config.vision_base_url)
    try:
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
    except Exception as exc:
        error = {"error_type": exc.__class__.__name__, "error": str(exc)}
        if should_fallback_to_ocr(exc):
            return None, error
        return build_error_result(image_path, reader_id, "api_error", error), None

    content = response.choices[0].message.content or ""
    if not content.strip():
        return None, {"error_type": "EmptyVisionResponse", "error": "vision model returned empty content"}

    parsed = parse_json_object(content)
    return normalize_batch(parsed, reader_id, image_path, status=parsed.get("status", "ok")), None


def should_fallback_to_ocr(exc: Exception) -> bool:
    message = str(exc).lower()
    return "image_url" in message or "expected `text`" in message or "expected text" in message


def extract_cases_from_ocr_text(
    config: AppConfig,
    image_path: Path,
    reader_id: str,
    vision_error: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not config.deepseek_api_key or not config.deepseek_base_url or not config.deepseek_model:
        error = vision_error or {"error_type": "ConfigError", "error": "no text model config"}
        return build_error_result(image_path, reader_id, "skipped_no_text_model_config", error)

    try:
        ocr_text = ocr_image_to_text(config, image_path, reader_id)
    except Exception as exc:
        error = {"error_type": exc.__class__.__name__, "error": str(exc)}
        if vision_error:
            error["vision_error"] = json.dumps(vision_error, ensure_ascii=False)
        return build_error_result(image_path, reader_id, "ocr_error", error)

    if not ocr_text.strip():
        error = {"error_type": "EmptyOCR", "error": "OCR did not return text"}
        if vision_error:
            error["vision_error"] = json.dumps(vision_error, ensure_ascii=False)
        return build_error_result(image_path, reader_id, "ocr_empty", error)

    try:
        from openai import OpenAI
    except ImportError:
        return build_error_result(
            image_path,
            reader_id,
            "skipped_missing_openai_dependency",
            {"error_type": "ImportError", "error": "missing openai dependency"},
        )

    client = OpenAI(api_key=config.deepseek_api_key, base_url=config.deepseek_base_url)
    try:
        response = client.chat.completions.create(
            model=config.case_extract_model,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{OCR_EXTRACTION_PROMPT}\n\n"
                        f"截图文件：{image_path.name}\n"
                        f"OCR文本：\n{ocr_text[:16000]}"
                    ),
                }
            ],
            temperature=0,
        )
    except Exception as exc:
        error = {"error_type": exc.__class__.__name__, "error": str(exc)}
        if vision_error:
            error["vision_error"] = json.dumps(vision_error, ensure_ascii=False)
        return build_error_result(image_path, reader_id, "text_api_error", error)

    content = response.choices[0].message.content or "{}"
    parsed = parse_json_object(content)
    result = normalize_batch(parsed, reader_id, image_path, status=parsed.get("status", "ok_ocr"))
    result["ocr_text_path"] = str(ocr_text_path(config, reader_id, image_path))
    if vision_error:
        result["vision_fallback_reason"] = vision_error
    return result


def extract_cases_from_ocr_batch(
    config: AppConfig, image_paths: list[Path], reader_id: str
) -> list[dict[str, Any]]:
    if not config.deepseek_api_key or not config.deepseek_base_url or not config.deepseek_model:
        return [
            build_error_result(
                image_path,
                reader_id,
                "skipped_no_text_model_config",
                {"error_type": "ConfigError", "error": "no text model config"},
            )
            for image_path in image_paths
        ]

    try:
        from openai import OpenAI
    except ImportError:
        return [
            build_error_result(
                image_path,
                reader_id,
                "skipped_missing_openai_dependency",
                {"error_type": "ImportError", "error": "missing openai dependency"},
            )
            for image_path in image_paths
        ]

    sections = []
    image_by_name = {image_path.name: image_path for image_path in image_paths}
    for image_path in image_paths:
        try:
            ocr_text = ocr_image_to_text(config, image_path, reader_id)
        except Exception as exc:
            ocr_text = f"[OCR_ERROR] {exc.__class__.__name__}: {exc}"
        sections.append(f"=== IMAGE: {image_path.name} ===\n{ocr_text[:9000]}")

    client = OpenAI(api_key=config.deepseek_api_key, base_url=config.deepseek_base_url)
    try:
        response = client.chat.completions.create(
            model=config.case_extract_model,
            messages=[
                {
                    "role": "user",
                    "content": f"{BATCH_OCR_EXTRACTION_PROMPT}\n\n" + "\n\n".join(sections),
                }
            ],
            temperature=0,
        )
    except Exception as exc:
        error = {"error_type": exc.__class__.__name__, "error": str(exc)}
        return [build_error_result(image_path, reader_id, "text_api_error", error) for image_path in image_paths]

    parsed = parse_json_object(response.choices[0].message.content or "{}")
    image_results = parsed.get("images", [])
    if not isinstance(image_results, list):
        error = {"error_type": "ParseError", "error": "batch response did not contain images list"}
        return [build_error_result(image_path, reader_id, "parse_failed", error) for image_path in image_paths]

    results_by_name = {}
    for result_index, image_result in enumerate(image_results):
        if not isinstance(image_result, dict):
            continue
        source_name = Path(str(image_result.get("source_image", ""))).name
        image_path = image_by_name.get(source_name)
        if image_path is None and result_index < len(image_paths):
            image_path = image_paths[result_index]
        if not image_path:
            continue
        normalized = normalize_batch(image_result, reader_id, image_path, status=image_result.get("status", "ok_ocr_batch"))
        normalized["ocr_text_path"] = str(ocr_text_path(config, reader_id, image_path))
        results_by_name[source_name] = normalized

    results = []
    for image_path in image_paths:
        result = results_by_name.get(image_path.name)
        if result is None:
            result = build_error_result(
                image_path,
                reader_id,
                "missing_from_batch_response",
                {"error_type": "MissingImageResult", "error": "model did not return this image"},
            )
        results.append(result)
    return results


def ocr_image_to_text(config: AppConfig, image_path: Path, reader_id: str) -> str:
    cache_path = ocr_text_path(config, reader_id, image_path)
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise RuntimeError("missing rapidocr-onnxruntime dependency") from exc

    ocr = RapidOCR()
    result, _ = ocr(str(image_path))
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
    text = "\n".join(line for _, _, line in lines if line)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text


def ocr_text_path(config: AppConfig, reader_id: str, image_path: Path) -> Path:
    return config.processed_dir / "ocr" / reader_id / f"{image_path.stem}.txt"


def build_error_result(
    image_path: Path, reader_id: str, status: str, error: dict[str, str]
) -> dict[str, Any]:
    return {
        "source_image": str(image_path),
        "reader_id": reader_id,
        "status": status,
        **error,
        "cases": [],
        "needs_manual_card_annotation": [],
    }


def normalize_batch(
    parsed: dict[str, Any], reader_id: str, image_path: Path, status: str
) -> dict[str, Any]:
    parsed["source_image"] = str(image_path)
    parsed["reader_id"] = reader_id
    parsed["status"] = status
    parsed["cases"] = [
        normalize_case(case, reader_id=reader_id, image_path=image_path)
        for case in parsed.get("cases", [])
        if isinstance(case, dict)
    ]
    parsed["needs_manual_card_annotation"] = parsed.get("needs_manual_card_annotation", [])
    return parsed


def parse_json_object(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.I).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {"cases": []}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if match:
            try:
                parsed = json.loads(match.group(0))
                return parsed if isinstance(parsed, dict) else {"cases": []}
            except json.JSONDecodeError:
                pass

    return {"raw": content, "status": "parse_failed", "cases": [], "needs_manual_card_annotation": []}


def normalize_case(case: dict[str, Any], reader_id: str, image_path: Path) -> dict[str, Any]:
    normalized = dict(case)
    normalized["reader_id"] = reader_id
    normalized["source_images"] = [str(image_path)]
    normalized["case_type"] = normalized.get("case_type", "tieba_screenshot")
    normalized["privacy_status"] = "auto_redacted"
    normalized["spread"] = normalized.get("spread") or "无牌阵三张牌"
    normalized["question"] = redact_text(str(normalized.get("question", "")))
    normalized["background"] = redact_text(str(normalized.get("background", "")))
    normalized["reader_answer"] = redact_text(str(normalized.get("reader_answer", "")))
    normalized["notes"] = str(normalized.get("notes", "")).strip()

    cards = normalized.get("cards", [])
    normalized_cards = []
    if isinstance(cards, list):
        for card in cards:
            if not isinstance(card, dict):
                continue
            name = str(card.get("name", "")).strip()
            orientation = str(card.get("orientation", "")).strip()
            if name and orientation in {"正位", "逆位"}:
                normalized_cards.append({"name": name, "orientation": orientation})
    normalized["cards"] = normalized_cards

    followups = normalized.get("followups", [])
    normalized_followups = []
    if isinstance(followups, list):
        for item in followups:
            if not isinstance(item, dict):
                continue
            speaker = item.get("speaker", "unknown")
            text = redact_text(str(item.get("text", "")))
            if text:
                normalized_followups.append({"speaker": speaker, "text": text})
    normalized["followups"] = normalized_followups

    if not is_reviewable_case(normalized):
        normalized["quality"] = "incomplete"
    else:
        normalized["quality"] = normalized.get("quality", "candidate")
    return normalized


def is_reviewable_case(case: dict[str, Any]) -> bool:
    return bool(
        case.get("question")
        and case.get("reader_answer")
        and case.get("cards")
        and case.get("quality") == "candidate"
    )


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
