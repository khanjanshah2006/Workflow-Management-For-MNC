"""Central database file storage and retrieval service (S9).

Provides persistence of uploaded attachments and generated reports inside Postgres
(stored_file table) rather than on an ephemeral local disk, preventing 404 errors
after container restarts on free-tier hosting (e.g., Render).
"""
import hashlib
import mimetypes
import os
import uuid
from typing import Any, Optional, Tuple, Union
from uuid import UUID

from fastapi import HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.stored_file import StoredFile

# Permitted extensions per purpose
ALLOWED_EXTENSIONS_BY_PURPOSE = {
    "TASK_SUBMISSION": {".pdf", ".zip", ".tar.gz", ".png", ".jpg", ".jpeg", ".docx"},
    "EXECUTIVE_REPORT": {".pdf", ".csv"},
}

DEFAULT_ALLOWED_EXTENSIONS = {
    ".pdf", ".zip", ".tar.gz", ".png", ".jpg", ".jpeg", ".docx", ".csv", ".txt"
}


def get_file_extension(filename: str) -> str:
    """Extract lowercased extension, recognizing compound extensions like .tar.gz."""
    fn = filename.lower()
    if fn.endswith(".tar.gz"):
        return ".tar.gz"
    return os.path.splitext(fn)[1]


def extract_upload_data(upload: Any) -> Tuple[str, bytes, str]:
    """Extract (filename, data_bytes, content_type) from various upload representations."""
    # Handle UploadFile (FastAPI / Starlette) or any file-like wrapper with .file
    if hasattr(upload, "file") and hasattr(upload.file, "read"):
        filename = getattr(upload, "filename", "upload") or "upload"
        content_type = getattr(upload, "content_type", "application/octet-stream") or "application/octet-stream"
        data = upload.file.read()
        try:
            upload.file.seek(0)
        except Exception:
            pass
        if isinstance(data, str):
            data = data.encode("utf-8")
        return filename, data, content_type

    if isinstance(upload, tuple):
        if len(upload) >= 3:
            filename, data, content_type = upload[0], upload[1], upload[2]
        elif len(upload) == 2:
            filename, data = upload[0], upload[1]
            content_type = "application/octet-stream"
        else:
            raise ValueError(f"Invalid upload tuple: {upload}")
        if isinstance(data, str):
            data = data.encode("utf-8")
        return str(filename), data, str(content_type)

    if isinstance(upload, dict):
        filename = upload.get("filename", "upload")
        data = upload.get("data") or upload.get("content", b"")
        if isinstance(data, str):
            data = data.encode("utf-8")
        content_type = upload.get("content_type", "application/octet-stream")
        return str(filename), data, str(content_type)

    if hasattr(upload, "filename") and hasattr(upload, "data"):
        filename = getattr(upload, "filename", "upload")
        content_type = getattr(upload, "content_type", "application/octet-stream")
        data = upload.data
        if isinstance(data, str):
            data = data.encode("utf-8")
        return str(filename), data, str(content_type)

    if hasattr(upload, "read"):
        filename = getattr(upload, "filename", "upload")
        content_type = getattr(upload, "content_type", "application/octet-stream")
        data = upload.read()
        if isinstance(data, str):
            data = data.encode("utf-8")
        return str(filename), data, str(content_type)

    raise ValueError(f"Unsupported upload type: {type(upload)}")


def save_file(
    db: Session,
    purpose: str,
    upload: Any,
    uploaded_by: Any = None,
) -> StoredFile:
    """Validate, digest, and persist a file to Postgres bytea storage.

    Checks MAX_UPLOAD_MB (default 5) and the allowed extensions, computes sha256,
    and flushes without committing so transaction ownership remains with the caller.
    """
    filename, data, content_type = extract_upload_data(upload)

    # 1. Validate allowed extensions
    ext = get_file_extension(filename)
    allowed = ALLOWED_EXTENSIONS_BY_PURPOSE.get(purpose, DEFAULT_ALLOWED_EXTENSIONS)
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(sorted(allowed))}",
        )

    # 2. Validate max upload size
    max_mb = settings.max_upload_mb
    max_bytes = settings.max_upload_bytes
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds the {max_mb}MB limit. Current size: {len(data)} bytes",
        )

    # 3. Compute sha256
    sha256_hash = hashlib.sha256(data).hexdigest()

    # 4. Resolve uploaded_by UUID
    user_id: Optional[UUID] = None
    if hasattr(uploaded_by, "account_id") and uploaded_by.account_id:
        user_id = uploaded_by.account_id
    elif isinstance(uploaded_by, UUID):
        user_id = uploaded_by
    elif isinstance(uploaded_by, str) and uploaded_by:
        try:
            user_id = UUID(uploaded_by)
        except (ValueError, TypeError):
            user_id = None

    # 5. Determine content type if generic
    clean_filename = os.path.basename(filename)
    if not content_type or content_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(clean_filename)
        if guessed:
            content_type = guessed
        elif ext == ".pdf":
            content_type = "application/pdf"
        elif ext == ".csv":
            content_type = "text/csv; charset=utf-8"

    # 6. Instantiate and flush (without committing)
    stored_file = StoredFile(
        purpose=purpose,
        filename=clean_filename,
        content_type=content_type,
        size_bytes=len(data),
        sha256=sha256_hash,
        data=data,
        uploaded_by=user_id,
    )
    db.add(stored_file)
    db.flush()

    return stored_file


def stream_file(stored_file: StoredFile, filename: Optional[str] = None) -> Response:
    """Stream a stored file to the HTTP response with Content-Disposition: attachment."""
    download_filename = filename or stored_file.filename
    headers = {
        "Content-Disposition": f'attachment; filename="{download_filename}"',
        "Content-Length": str(stored_file.size_bytes),
    }
    return Response(
        content=stored_file.data,
        media_type=stored_file.content_type or "application/octet-stream",
        headers=headers,
    )
