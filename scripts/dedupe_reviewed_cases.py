from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tarot_agent.config import AppConfig


def case_key(case: dict[str, Any]) -> str:
    return json.dumps(
        {
            "question": str(case.get("question", "")).strip(),
            "reader_answer": str(case.get("reader_answer", "")).strip(),
            "cards": case.get("cards", []),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def main() -> None:
    config = AppConfig.load()
    reader_id = sys.argv[1] if len(sys.argv) > 1 else "tarotist_1"
    path = config.cases_dir / f"{reader_id}_reviewed.jsonl"
    if not path.exists():
        raise SystemExit(f"未找到 reviewed 案例文件：{path}")

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    backup_dir = config.cases_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{path.stem}_before_dedupe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    shutil.copy2(path, backup_path)

    seen = set()
    deduped = []
    for row in rows:
        key = case_key(row)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in deduped) + "\n",
        encoding="utf-8",
    )
    print(f"原始 reviewed：{len(rows)}")
    print(f"去重后 reviewed：{len(deduped)}")
    print(f"移除重复：{len(rows) - len(deduped)}")
    print(f"备份：{backup_path}")


if __name__ == "__main__":
    main()
