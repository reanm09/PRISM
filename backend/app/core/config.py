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
    fracture_root: Path = Path(r"D:\PRISM\prism-fracture")
    artifact_storage: Path = BACKEND_ROOT / "storage" / "artifacts"
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, gt=0)
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


settings = Settings()
