import hashlib
from pathlib import PureWindowsPath
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.core.config import Settings
from app.schemas.artifact import ArtifactMetadata


class EmptyArtifactError(ValueError):
    pass


class ArtifactTooLargeError(ValueError):
    pass


class ArtifactService:
    def __init__(self, config: Settings):
        self.config = config
        self._registry: dict[UUID, ArtifactMetadata] = {}

    def get(self, artifact_id: UUID) -> ArtifactMetadata | None:
        return self._registry.get(artifact_id)

    async def ingest(self, upload: UploadFile) -> ArtifactMetadata:
        artifact_id = uuid4()
        storage = self.config.artifact_storage
        storage.mkdir(parents=True, exist_ok=True)
        destination = storage / str(artifact_id)
        digest = hashlib.sha256()
        size = 0
        created = False
        complete = False

        try:
            with destination.open("xb") as output:
                created = True
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.config.max_upload_bytes:
                        raise ArtifactTooLargeError("Upload exceeds maximum size")
                    digest.update(chunk)
                    output.write(chunk)
                if size == 0:
                    raise EmptyArtifactError("Empty uploads are not accepted")

            original_name = upload.filename or ""
            metadata = ArtifactMetadata(
                artifact_id=artifact_id,
                sha256=digest.hexdigest(),
                original_name=original_name,
                size_bytes=size,
                claimed_extension=PureWindowsPath(original_name).suffix,
            )
            self._registry[artifact_id] = metadata
            complete = True
            return metadata
        finally:
            if created and not complete:
                destination.unlink(missing_ok=True)
