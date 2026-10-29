import hashlib
import io
import os
import re
import tempfile
import warnings
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import UUID

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import get_settings


class MediaStore(Protocol):
    def save(self, user_id: UUID, data: bytes) -> str: ...
    def open(self, file_hash: str) -> BinaryIO: ...
    def delete(self, file_hash: str) -> None: ...


class LocalMediaStore:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def path(self, file_hash: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{64}", file_hash):
            raise ValueError("Invalid content hash")
        return self.root / file_hash

    def save(self, user_id: UUID, data: bytes) -> str:
        file_hash = hashlib.sha256(data).hexdigest()
        target = self.path(file_hash)
        # Atomic replacement avoids exposing partial files to simultaneous readers.
        fd, temporary = tempfile.mkstemp(dir=self.root)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return file_hash

    def open(self, file_hash: str) -> BinaryIO:
        return self.path(file_hash).open("rb")

    def delete(self, file_hash: str) -> None:
        self.path(file_hash).unlink(missing_ok=True)


def normalize_image(data: bytes) -> bytes:
    settings = get_settings()
    if len(data) > settings.max_image_bytes:
        raise HTTPException(413, "Image exceeds upload limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                    raise ValueError("Unsupported image")
                source.seek(0)  # Animated uploads intentionally become a still first frame.
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGBA")
                image.thumbnail((settings.max_image_dimension, settings.max_image_dimension))
                # Fresh pixels prevent EXIF, comments and other source metadata from surviving.
                clean = Image.frombytes("RGBA", image.size, image.tobytes())
                output = io.BytesIO()
                clean.save(output, format="WEBP", lossless=True)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise HTTPException(422, "Upload a valid JPEG, PNG, WebP or GIF image")


def get_media_store() -> MediaStore:
    return LocalMediaStore(get_settings().media_dir)
