"""Local object storage. Swapped for Cloud Storage + signed URLs in Bloco 8."""
from pathlib import Path

from app.config import settings


def save_bytes(rel_path: str, data: bytes) -> str:
    dest = Path(settings.storage_dir) / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return str(dest)
