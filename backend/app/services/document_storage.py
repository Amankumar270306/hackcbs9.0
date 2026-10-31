"""Document storage service for Compliance Sentinel.

Provides persistent file storage outside the database with directory isolation:
{storage_root}/{organization_id}/{audit_id}/{document_id}/{stored_filename}
Includes path traversal prevention, secure permissions, and modular architecture.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
from typing import BinaryIO, Optional, Union
import uuid

from app.config import settings


class DocumentStorageError(Exception):
    """Raised when file storage operations fail."""
    pass


class DocumentStorageService:
    def __init__(self, base_path: Optional[str] = None) -> None:
        raw_base = base_path or settings.STORAGE_LOCAL_PATH
        self.base_path = Path(raw_base).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and unsafe characters."""
        clean = os.path.basename(filename)
        clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', clean)
        return clean or "document.bin"

    def generate_stored_filename(self, original_filename: str) -> str:
        """Generate a random server-side stored filename preserving extension."""
        ext = ""
        if "." in original_filename:
            ext = "." + original_filename.rsplit(".", 1)[-1].lower()
            ext = re.sub(r'[^a-z0-9]', '', ext)
            if ext:
                ext = f".{ext}"
        return f"{uuid.uuid4().hex}{ext}"

    def build_storage_key(
        self,
        organization_id: Union[uuid.UUID, str],
        audit_id: Union[uuid.UUID, str],
        document_id: Union[uuid.UUID, str],
        stored_filename: str,
    ) -> str:
        """Build a relative storage key for multi-tenant isolation."""
        sanitized = self._sanitize_filename(stored_filename)
        return f"{str(organization_id)}/{str(audit_id)}/{str(document_id)}/{sanitized}"

    def get_absolute_path(self, storage_key_or_path: str) -> Path:
        """Resolve absolute path and prevent directory traversal outside base_path."""
        # If absolute path was given, check if it starts with base_path
        candidate = Path(storage_key_or_path)
        if not candidate.is_absolute():
            resolved = (self.base_path / candidate).resolve()
        else:
            resolved = candidate.resolve()

        # Enforce that resolved path resides inside base_path
        try:
            resolved.relative_to(self.base_path)
        except ValueError:
            raise DocumentStorageError("Directory traversal detected: path outside allowed storage root")

        return resolved

    def save_file(
        self,
        organization_id: Union[uuid.UUID, str],
        audit_id: Union[uuid.UUID, str],
        document_id: Union[uuid.UUID, str],
        stored_filename: str,
        content: Union[bytes, BinaryIO],
    ) -> tuple[str, str, int]:
        """Save document content to persistent storage.

        Returns: (storage_path, storage_key, file_size_bytes)
        """
        storage_key = self.build_storage_key(organization_id, audit_id, document_id, stored_filename)
        dest_path = self.get_absolute_path(storage_key)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        size = 0
        try:
            if isinstance(content, bytes):
                dest_path.write_bytes(content)
                size = len(content)
            else:
                with open(dest_path, "wb") as f:
                    while chunk := content.read(64 * 1024):
                        f.write(chunk)
                        size += len(chunk)
        except Exception as exc:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            raise DocumentStorageError(f"Failed to write file to storage: {exc}") from exc

        return str(dest_path), storage_key, size

    def read_file_bytes(self, storage_key_or_path: str) -> bytes:
        """Read full binary contents from storage."""
        path = self.get_absolute_path(storage_key_or_path)
        if not path.is_file():
            raise DocumentStorageError(f"Stored file not found: {path.name}")
        return path.read_bytes()

    def file_exists(self, storage_key_or_path: str) -> bool:
        """Check if file exists on disk."""
        try:
            path = self.get_absolute_path(storage_key_or_path)
            return path.is_file()
        except DocumentStorageError:
            return False

    def delete_file(self, storage_key_or_path: str) -> bool:
        """Delete file and its parent document directory if empty."""
        try:
            path = self.get_absolute_path(storage_key_or_path)
            if path.is_file():
                path.unlink()
                # Clean up empty parent document directory
                parent_dir = path.parent
                if parent_dir.is_dir() and not any(parent_dir.iterdir()):
                    parent_dir.rmdir()
                return True
            return False
        except Exception as exc:
            raise DocumentStorageError(f"Failed to delete stored file: {exc}") from exc


storage_service = DocumentStorageService()

