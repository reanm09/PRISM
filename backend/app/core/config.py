from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PRISM_", env_file=BACKEND_ROOT / ".env", extra="ignore"
    )

    data_root: Path = Path(r"D:\PRISM")
    datasets_root: Path = Path(r"D:\PRISM\datasets")
    models_root: Path = Path(r"D:\PRISM\models")
    knowledge_root: Path = Path(r"D:\PRISM\knowledge")
    bge_model_path: Path = Path(r"D:\PRISM\models\bge-m3")
    ollama_base_url: str = "http://localhost:11434"
    ollama_num_ctx: int = 4096
    rag_llm_model: str = "llama3.2:3b"
    rag_index_path: Path = BACKEND_ROOT / "storage" / "rag_index.json"
    fracture_root: Path = Path(r"D:\PRISM\prism-fracture")
    artifact_storage: Path = BACKEND_ROOT / "storage" / "artifacts"

    laya_model_path: Path = Path(r"D:\PRISM\models\prism-laya-exp2-v3")
    laya_model_sha256: str = "3a48c2cacf937abbf94179ee540d4458c465829d311e60dbaae26ac508711595"

    laya_device: str = "auto"

    laya_cuda_amp: str = "fp16"

    max_upload_bytes: int = Field(default=25 * 1024 * 1024, gt=0)
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "http://127.0.0.1:3001", "http://localhost:5173"]


settings = Settings()
