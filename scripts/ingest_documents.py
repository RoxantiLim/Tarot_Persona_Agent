from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tarot_agent.config import AppConfig
from src.tarot_agent.pdf_ingest import chunks_to_documents, ingest_pdfs_to_chunks, write_processed_outputs
from src.tarot_agent.persona import save_default_personas
from src.tarot_agent.vector_store import build_vector_store


def main() -> None:
    config = AppConfig.load()
    config.ensure_dirs()
    save_default_personas(config)

    chunks, report = ingest_pdfs_to_chunks(config)
    write_processed_outputs(config, chunks, report)
    if not chunks:
        print("没有生成任何 chunk。请检查 PDF 是否为扫描版或是否安装 PyMuPDF。")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    documents = chunks_to_documents(chunks)
    store = build_vector_store(config, documents)
    report["vector_store_backend"] = getattr(store, "backend_name", "unknown")
    write_processed_outputs(config, chunks, report)
    print("入库完成")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
