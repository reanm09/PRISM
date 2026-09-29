from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ArtifactMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    sha256: str
    original_name: str
    size_bytes: int
    claimed_extension: str
    status: Literal["INGESTED"] = "INGESTED"
