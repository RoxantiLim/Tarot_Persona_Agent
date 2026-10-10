from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tarot_agent.config import AppConfig
from src.tarot_agent.vector_store import _publish_indexes, validate_local_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the explicit private data bundle for Modal; no raw files or .env are copied.")
    parser.add_argument("--index", type=Path, help="Validated API index directory")
    parser.add_argument("--without-cases", action="store_true", help="Exclude reviewed case data from the deployment")
    args = parser.parse_args()
    config = AppConfig.load()
    index_dir = args.index or (config.local_index_dir if config.embedding_provider == "api" else config.data_dir / "indexes" / "api_vectors")
    config = replace(config, embedding_provider="api", vector_store_backend="numpy", build_chroma=False, local_index_dir=index_dir)
    info = validate_local_index(config)
    bundle = ROOT / "data" / "deploy" / "modal"
    bundle.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".modal-bundle-", dir=bundle.parent) as temp_dir:
        staging = Path(temp_dir) / "bundle"
        target_index = staging / "indexes" / "api_vectors"
        target_index.mkdir(parents=True)
        for name in ("vectors.npy", "documents.jsonl", "manifest.json"):
            shutil.copy2(index_dir / name, target_index / name)
        validate_local_index(replace(config, local_index_dir=target_index))
        for directory, pattern in ((config.personas_dir, "*.json"), (config.cases_dir, "*_reviewed.jsonl")):
            if args.without_cases and directory == config.cases_dir:
                continue
            destination = staging / directory.name
            destination.mkdir()
            for source in directory.glob(pattern):
                text = source.read_text(encoding="utf-8")
                if source.suffix == ".jsonl":
                    for line in text.splitlines():
                        if line.strip():
                            json.loads(line)
                else:
                    json.loads(text)
                shutil.copy2(source, destination / source.name)
        _publish_indexes([(staging, bundle)])
    files = [file for file in bundle.rglob("*") if file.is_file()]
    print(f"Modal bundle ready: {info['count']} documents, {len(files)} files, {sum(file.stat().st_size for file in files) / 1024 / 1024:.2f} MiB")
    print(f"Private bundle path: {bundle} (ignored by Git)")


if __name__ == "__main__":
    main()
