from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    doc_dir: Path
    data_dir: Path
    processed_dir: Path
    chroma_dir: Path
    cases_dir: Path
    personas_dir: Path
    reports_dir: Path
    aux_dir: Path
    model_cache_dir: Path
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    embedding_model: str
    vision_api_key: str
    vision_base_url: str
    vision_model: str
    build_chroma: bool

    @classmethod
    def load(cls) -> "AppConfig":
        project_root = Path(__file__).resolve().parents[2]
        load_dotenv(project_root / ".env")
        data_dir = project_root / "data"
        aux_dir = Path(os.getenv("TAROT_AUX_DIR", r"E:\for-LLM\AUXI\Tarot_Persona_Agent"))
        model_cache_dir = Path(os.getenv("MODEL_CACHE_DIR", str(aux_dir / "models")))
        return cls(
            project_root=project_root,
            doc_dir=project_root / "Doc",
            data_dir=data_dir,
            processed_dir=data_dir / "processed",
            chroma_dir=project_root / os.getenv("CHROMA_DIR", r"data\indexes\chroma"),
            cases_dir=data_dir / "cases",
            personas_dir=data_dir / "personas",
            reports_dir=data_dir / "reports",
            aux_dir=aux_dir,
            model_cache_dir=model_cache_dir,
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
            vision_api_key=os.getenv("VISION_API_KEY", ""),
            vision_base_url=os.getenv("VISION_BASE_URL", ""),
            vision_model=os.getenv("VISION_MODEL", ""),
            build_chroma=os.getenv("BUILD_CHROMA", "0").lower() in {"1", "true", "yes"},
        )

    def ensure_dirs(self) -> None:
        for path in [
            self.data_dir,
            self.processed_dir,
            self.chroma_dir,
            self.cases_dir,
            self.personas_dir,
            self.reports_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


def dependency_report() -> dict[str, bool]:
    packages = [
        "streamlit",
        "langchain",
        "langchain_community",
        "langchain_chroma",
        "langgraph",
        "chromadb",
        "sentence_transformers",
        "fitz",
        "openai",
        "dotenv",
    ]
    return {name: importlib.util.find_spec(name) is not None for name in packages}
