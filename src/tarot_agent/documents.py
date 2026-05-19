from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimpleDocument:
    page_content: str
    metadata: dict[str, Any] = field(default_factory=dict)


try:
    from langchain_core.documents import Document as LangChainDocument
except ImportError:
    LangChainDocument = SimpleDocument


Document = LangChainDocument
