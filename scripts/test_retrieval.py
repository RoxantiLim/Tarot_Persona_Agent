from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tarot_agent.config import AppConfig
from src.tarot_agent.rag_chain import retrieve_context


def main() -> None:
    query = " ".join(sys.argv[1:]) or "恋人逆位 感情"
    config = AppConfig.load()
    docs = retrieve_context(config, query, top_k=5)
    print(f"Query: {query}")
    print(f"Results: {len(docs)}")
    for idx, doc in enumerate(docs, start=1):
        print(f"\n[{idx}] {doc.metadata}")
        print(doc.page_content[:600])


if __name__ == "__main__":
    main()
