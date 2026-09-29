import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[3]


class RAGSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Supabase credentials
    supabase_url: str = os.getenv("SUPABASE_URL", "https://xeykdmwgxcmgussvsiwp.supabase.co")
    supabase_secret_key: str = os.getenv("SUPABASE_SECRET_KEY", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")

    # Embedding Model settings
    bge_model_name: str = os.getenv("BGE_MODEL_NAME", "BAAI/bge-m3")
    bge_dimension: int = int(os.getenv("BGE_DIMENSION", "1024"))
    bge_use_real_model: bool = os.getenv("BGE_USE_REAL_MODEL", "false").lower() in ("true", "1", "yes")

    # Qwen LLM settings
    qwen_model_name: str = os.getenv("QWEN_MODEL_NAME", "qwen3:4b")
    qwen_load_local_model: bool = os.getenv("QWEN_LOAD_LOCAL_MODEL", "false").lower() in ("true", "1", "yes")
    qwen_max_new_tokens: int = int(os.getenv("MAX_NEW_TOKENS", "512"))
    qwen_temperature: float = float(os.getenv("TEMPERATURE", "0.1"))
    qwen_top_p: float = float(os.getenv("TOP_P", "0.9"))
    qwen_top_k: int = int(os.getenv("TOP_K", "50"))
    qwen_enable_thinking: bool = os.getenv("ENABLE_THINKING", "false").lower() in ("true", "1", "yes")
    qwen_inference_url: Optional[str] = os.getenv("QWEN_INFERENCE_URL", "http://localhost:11434")

    # Vector Retrieval settings
    vector_top_k: int = int(os.getenv("VECTOR_TOP_K", "3"))
    vector_match_threshold: float = float(os.getenv("VECTOR_MATCH_THRESHOLD", "0.20"))

    # Knowledge directory
    knowledge_root: Path = (
        Path(r"D:\PRISM\knowledge")
        if Path(r"D:\PRISM\knowledge").exists()
        else BACKEND_ROOT / "knowledge"
    )

    # Development & Authentication settings
    dev_mode: bool = os.getenv("DEV_MODE", "true").lower() in ("true", "1", "yes")
    dev_user_id: str = "00000000-0000-0000-0000-000000000001"
    dev_user_email: str = "dev@prism.local"


rag_settings = RAGSettings()
