from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tarot_agent.config import AppConfig
from src.tarot_agent.documents import Document
from src.tarot_agent.vector_store import build_vector_store, validate_local_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-embed existing documents into a separate API index; no PDF/OCR or old-index deletion.")
    parser.add_argument("--source", type=Path, help="Existing documents.jsonl file")
    parser.add_argument("--output", type=Path, help="Directory for the separate API index")
    parser.add_argument("--validate-only", action="store_true", help="Validate the API index without calling external services")
    args = parser.parse_args()
    config = AppConfig.load()
    source = args.source or config.data_dir / "indexes" / "local_vectors" / "documents.jsonl"
    output = args.output or (config.local_index_dir if config.embedding_provider == "api" else config.data_dir / "indexes" / "api_vectors")
    config = replace(config, embedding_provider="api", vector_store_backend="numpy", build_chroma=False, local_index_dir=output.resolve())
    if args.validate_only:
        info = validate_local_index(config)
        print(f"Validated API index: {info['count']} documents, {info['dimensions']} dimensions")
        return
    if output.resolve() == source.resolve().parent:
        raise ValueError("API index output must differ from the original source index directory")
    documents = []
    with source.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                documents.append(Document(page_content=row["page_content"], metadata=row.get("metadata", {})))
    print(f"Rebuilding {len(documents)} documents into {output}; original index is retained")
    store = build_vector_store(config, documents)
    store.vectors._mmap.close()
    info = validate_local_index(config)
    print(f"API index ready: {info['count']} documents, {info['dimensions']} dimensions")


if __name__ == "__main__":
    main()
