from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tarot_agent.cases import is_reviewable_case
from src.tarot_agent.config import AppConfig


def main() -> None:
    config = AppConfig.load()
    config.ensure_dirs()

    reader_id = sys.argv[1] if len(sys.argv) > 1 else "tarotist_1"
    candidate_path = config.cases_dir / f"{reader_id}_candidates.jsonl"
    reviewed_path = config.cases_dir / f"{reader_id}_reviewed.jsonl"
    incomplete_path = config.cases_dir / f"{reader_id}_needs_review.jsonl"

    if not candidate_path.exists():
        raise SystemExit(f"未找到候选案例文件：{candidate_path}")

    reviewed = []
    needs_review = []
    with candidate_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            batch = json.loads(line)
            source_image = batch.get("source_image", "")
            for case in batch.get("cases", []):
                case.setdefault("source_images", [source_image] if source_image else [])
                if is_reviewable_case(case):
                    case["quality"] = "reviewed"
                    reviewed.append(case)
                else:
                    needs_review.append(case)
            for item in batch.get("needs_manual_card_annotation", []):
                if isinstance(item, dict):
                    item.setdefault("source_image", source_image)
                    item.setdefault("reader_id", reader_id)
                    needs_review.append(item)
                else:
                    needs_review.append(
                        {
                            "reader_id": reader_id,
                            "source_image": source_image,
                            "reason": str(item),
                            "quality": "needs_manual_card_annotation",
                        }
                    )

    for index, case in enumerate(reviewed, start=1):
        case["case_id"] = f"{reader_id}_{index:04d}"

    with reviewed_path.open("w", encoding="utf-8") as f:
        for case in reviewed:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")

    with incomplete_path.open("w", encoding="utf-8") as f:
        for case in needs_review:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")

    print(f"已自动入库 reviewed 案例：{len(reviewed)} -> {reviewed_path}")
    print(f"需要人工处理的候选：{len(needs_review)} -> {incomplete_path}")


if __name__ == "__main__":
    main()
