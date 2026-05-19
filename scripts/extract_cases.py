from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tarot_agent.cases import extract_cases_from_image
from src.tarot_agent.config import AppConfig


def main() -> None:
    config = AppConfig.load()
    config.ensure_dirs()
    reader_id = sys.argv[1] if len(sys.argv) > 1 else "tarotist_1"
    image_dir = ROOT / ("Tarotist-1" if reader_id == "tarotist_1" else reader_id)
    output_path = config.cases_dir / f"{reader_id}_candidates.jsonl"
    images = sorted([*image_dir.glob("*.jpg"), *image_dir.glob("*.png")])
    with output_path.open("w", encoding="utf-8") as f:
        for image in images:
            result = extract_cases_from_image(config, image, reader_id)
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
            print(f"{image.name}: {result.get('status', 'ok')}")
    print(f"候选案例已写入：{output_path}")


if __name__ == "__main__":
    main()
