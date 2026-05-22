from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tarot_agent.cases import extract_cases_from_image, extract_cases_from_ocr_batch
from src.tarot_agent.config import AppConfig


def main() -> None:
    config = AppConfig.load()
    config.ensure_dirs()

    reader_id = sys.argv[1] if len(sys.argv) > 1 else "tarotist_1"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    batch_size = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    image_dir = ROOT / ("Tarotist-1" if reader_id == "tarotist_1" else reader_id)
    output_path = config.cases_dir / f"{reader_id}_candidates.jsonl"

    images = sorted([*image_dir.glob("*.jpg"), *image_dir.glob("*.png")])
    if limit:
        images = images[:limit]

    if not images:
        raise SystemExit(f"没有找到截图目录或图片：{image_dir}")

    with output_path.open("w", encoding="utf-8") as f:
        if batch_size > 1:
            for start in range(0, len(images), batch_size):
                batch = images[start : start + batch_size]
                results = extract_cases_from_ocr_batch(config, batch, reader_id)
                for offset, result in enumerate(results, start=1):
                    index = start + offset
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
                    case_count = len(result.get("cases", []))
                    manual_count = len(result.get("needs_manual_card_annotation", []))
                    print(
                        f"[{index}/{len(images)}] {Path(result.get('source_image', '')).name}: "
                        f"{result.get('status', 'ok')} cases={case_count} manual={manual_count}"
                    )
        else:
            for index, image in enumerate(images, start=1):
                result = extract_cases_from_image(config, image, reader_id)
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                case_count = len(result.get("cases", []))
                manual_count = len(result.get("needs_manual_card_annotation", []))
                print(
                    f"[{index}/{len(images)}] {image.name}: "
                    f"{result.get('status', 'ok')} cases={case_count} manual={manual_count}"
                )

    print(f"候选案例已写入：{output_path}")


if __name__ == "__main__":
    main()
