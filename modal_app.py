"""Deploy with: python -m modal deploy modal_app.py (after preparing data and Secrets)."""
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "data" / "deploy" / "modal"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements(str(ROOT / "requirements-api.txt"))
    .env({
        "PYTHONPATH": "/app",
        "TAROT_DATA_DIR": "/app/data",
        "TAROT_AUX_DIR": "/tmp/tarot-agent",
        "EMBEDDING_PROVIDER": "api",
        "EMBEDDING_MODEL": "BAAI/bge-m3",
        "EMBEDDING_BASE_URL": "https://api.siliconflow.cn/v1",
        "EMBEDDING_TIMEOUT_SECONDS": "20",
        "VECTOR_STORE_BACKEND": "numpy",
        "LOCAL_INDEX_DIR": "/app/data/indexes/api_vectors",
        "BUILD_CHROMA": "0",
        "PDF_OCR_ENABLED": "0",
        "DEEPSEEK_MODEL": "deepseek-v4-pro",
        "CASE_EXTRACT_MODEL": "deepseek-v4-pro",
        "DEEPSEEK_TIMEOUT_SECONDS": "90",
        "PUBLIC_API_DOCS": "0",
        "API_REQUESTS_PER_MINUTE": "10",
    })
    .add_local_dir(str(ROOT / "src"), "/app/src", ignore=["**/__pycache__/**"])
    .add_local_dir(str(ROOT / "api"), "/app/api", ignore=["**/__pycache__/**"])
    .add_local_dir(str(BUNDLE), "/app/data")
)

app = modal.App("tarot-persona-api")


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("tarot-api-secrets")],
    cpu=0.5,
    memory=1024,
    min_containers=0,
    max_containers=1,
    scaledown_window=60,
    timeout=140,
)
@modal.concurrent(max_inputs=2)
@modal.asgi_app()
def api():
    from src.tarot_agent.config import AppConfig
    from src.tarot_agent.vector_store import validate_local_index

    config = AppConfig.load()
    if not all((config.deepseek_api_key.strip(), config.embedding_api_key.strip(), config.api_access_token.strip())):
        raise RuntimeError("Modal Secret must contain DEEPSEEK_API_KEY, EMBEDDING_API_KEY and API_ACCESS_TOKEN")
    validate_local_index(config)
    from api.main import app as fastapi_app

    return fastapi_app
