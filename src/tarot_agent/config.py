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
    deepseek_timeout_seconds: float
    embedding_model: str
    embedding_device: str
    retrieval_mode: str
    vector_store_backend: str
    pdf_ocr_enabled: bool
    pdf_ocr_dpi: int
    pdf_ocr_min_chars: int
    vision_api_key: str
    vision_base_url: str
    vision_model: str
    case_extract_model: str
    build_chroma: bool
    embedding_provider: str = "local"
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_timeout_seconds: float = 20
    embedding_batch_size: int = 16
    local_index_dir: Path | None = None
    api_access_token: str = ""
    cors_origins: tuple[str, ...] = ("http://127.0.0.1:3000", "http://localhost:3000")

    @classmethod
    def load(cls) -> "AppConfig":
        project_root = Path(__file__).resolve().parents[2]
        load_dotenv(project_root / ".env")
        data_dir = project_root / os.getenv("TAROT_DATA_DIR", "data")
        default_aux = r"E:\for-LLM\AUXI\Tarot_Persona_Agent" if os.name == "nt" else "/tmp/tarot-agent"
        aux_dir = Path(os.getenv("TAROT_AUX_DIR", default_aux))
        model_cache_dir = Path(os.getenv("MODEL_CACHE_DIR", str(aux_dir / "models")))
        provider = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
        if provider not in {"local", "api"}:
            raise ValueError("EMBEDDING_PROVIDER must be local or api")
        backend = os.getenv("VECTOR_STORE_BACKEND", "numpy" if provider == "api" else "chroma").strip().lower()
        if backend not in {"numpy", "chroma"}:
            raise ValueError("VECTOR_STORE_BACKEND must be numpy or chroma")
        index_name = "api_vectors" if provider == "api" else "local_vectors"
        local_index_dir = project_root / (os.getenv("LOCAL_INDEX_DIR", "").strip() or str(data_dir / "indexes" / index_name))
        return cls(
            project_root=project_root,
            doc_dir=project_root / "Doc",
            data_dir=data_dir,
            processed_dir=data_dir / "processed",
            chroma_dir=project_root / os.getenv("CHROMA_DIR", str(data_dir / "indexes" / ("api_chroma" if provider == "api" else "chroma"))),
            cases_dir=data_dir / "cases",
            personas_dir=data_dir / "personas",
            reports_dir=data_dir / "reports",
            aux_dir=aux_dir,
            model_cache_dir=model_cache_dir,
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            deepseek_timeout_seconds=float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "90")),
            embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
            embedding_device=os.getenv("EMBEDDING_DEVICE", "auto").strip().lower(),
            retrieval_mode=os.getenv("RETRIEVAL_MODE", "vector").strip().lower(),
            vector_store_backend=backend,
            pdf_ocr_enabled=os.getenv("PDF_OCR_ENABLED", "0").lower() in {"1", "true", "yes"},
            pdf_ocr_dpi=int(os.getenv("PDF_OCR_DPI", "180")),
            pdf_ocr_min_chars=int(os.getenv("PDF_OCR_MIN_CHARS", "40")),
            vision_api_key=os.getenv("VISION_API_KEY", ""),
            vision_base_url=os.getenv("VISION_BASE_URL", ""),
            vision_model=os.getenv("VISION_MODEL", ""),
            case_extract_model=os.getenv("CASE_EXTRACT_MODEL", "deepseek-chat"),
            build_chroma=os.getenv("BUILD_CHROMA", "0").lower() in {"1", "true", "yes"},
            embedding_provider=provider,
            embedding_api_key=os.getenv("EMBEDDING_API_KEY", ""),
            embedding_base_url=os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/"),
            embedding_timeout_seconds=float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "20")),
            embedding_batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "16")),
            local_index_dir=local_index_dir,
            api_access_token=os.getenv("API_ACCESS_TOKEN", ""),
            cors_origins=tuple(origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000").split(",") if origin.strip()),
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
