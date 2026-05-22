from __future__ import annotations

import json
import random
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tarot_agent.config import AppConfig
from src.tarot_agent.persona import persona_path, save_persona
from src.tarot_agent.schemas import PersonaProfile


PERSONA_PROMPT = """你是一个 Agent 项目的占卜师风格画像分析助手。

请根据真实塔罗占卜案例，总结该占卜师的自然回答风格。注意：
1. 不要复制原案例长句。
2. 画像要用于后续生成回答，所以要具体、可执行。
3. 不要把风格夸张化，不要写成玄学人设。
4. 只输出 JSON，不要 Markdown。

JSON 字段必须完全符合：
{
  "reader_id": "tarotist_1",
  "display_name": "Tarotist 1",
  "tone": "...",
  "answer_structure": ["...", "..."],
  "common_phrases": ["...", "..."],
  "reasoning_style": "...",
  "avoid": ["...", "..."]
}
"""


def load_reviewed_cases(config: AppConfig, reader_id: str) -> list[dict]:
    path = config.cases_dir / f"{reader_id}_reviewed.jsonl"
    if not path.exists():
        raise SystemExit(f"未找到 reviewed 案例文件：{path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sample_cases(cases: list[dict], limit: int) -> list[dict]:
    if len(cases) <= limit:
        return cases
    random.seed(42)
    return random.sample(cases, limit)


def compact_case(case: dict) -> dict:
    return {
        "question": str(case.get("question", ""))[:220],
        "cards": case.get("cards", [])[:5],
        "answer": str(case.get("reader_answer", ""))[:520],
    }


def parse_json_object(content: str) -> dict:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.I).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if match:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
    raise ValueError("模型没有返回合法 JSON")


def main() -> None:
    config = AppConfig.load()
    reader_id = sys.argv[1] if len(sys.argv) > 1 else "tarotist_1"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    cases = load_reviewed_cases(config, reader_id)
    selected = sample_cases(cases, limit)

    from openai import OpenAI

    client = OpenAI(api_key=config.deepseek_api_key, base_url=config.deepseek_base_url)
    payload = {
        "reader_id": reader_id,
        "case_count_total": len(cases),
        "case_count_sampled": len(selected),
        "cases": [compact_case(case) for case in selected],
    }
    response = client.chat.completions.create(
        model=config.case_extract_model,
        messages=[
            {"role": "system", "content": PERSONA_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.2,
    )
    parsed = parse_json_object(response.choices[0].message.content or "{}")
    parsed["reader_id"] = reader_id
    parsed.setdefault("display_name", "Tarotist 1" if reader_id == "tarotist_1" else reader_id)
    profile = PersonaProfile.model_validate(parsed)

    path = persona_path(config, reader_id)
    if path.exists():
        backup_dir = config.personas_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"{reader_id}_before_generate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        shutil.copy2(path, backup_path)
        print(f"备份旧画像：{backup_path}")

    save_persona(config, profile)
    print(f"已更新画像：{path}")
    print(json.dumps(profile.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
