"""OpenAI Vector Stores and Files for the dashboard UI."""
from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import Any

from openai import APIConnectionError, APIStatusError, OpenAI

logger = logging.getLogger(__name__)

MAX_VECTOR_STORE_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_SUFFIXES = frozenset({".pdf", ".md", ".markdown"})


def validate_upload_filename(filename: str | None) -> str:
    if not filename or not filename.strip():
        raise ValueError("Filename is required")
    name = Path(filename).name
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise ValueError("Only .pdf, .md, and .markdown files are allowed")
    return name


def validate_pdf_leading_bytes(content: bytes) -> None:
    if len(content) < 4 or not content.startswith(b"%PDF"):
        raise ValueError("File does not look like a valid PDF")


def map_openai_exception(exc: Exception) -> tuple[int, str]:
    if isinstance(exc, APIConnectionError):
        return 502, "Could not reach OpenAI."
    if isinstance(exc, APIStatusError):
        sc = getattr(exc, "status_code", None)
        if sc == 429:
            return 429, "OpenAI rate-limited; try again shortly."
        msg: Any = getattr(exc, "message", None)
        if msg is None and hasattr(exc, "body") and isinstance(exc.body, dict):
            err = exc.body.get("error")
            if isinstance(err, dict):
                msg = err.get("message")
        if msg is None:
            msg = "OpenAI API error"
        return 502, str(msg)[:500]
    logger.exception("Unexpected OpenAI error")
    return 502, "OpenAI request failed."


class OpenAIVectorStoreService:
    def __init__(self, api_key: str) -> None:
        self._client = OpenAI(api_key=api_key)

    def list_vector_stores(self, *, limit: int = 20, after: str | None = None) -> dict[str, Any]:
        page = self._client.vector_stores.list(limit=limit, after=after)
        return {
            "data": [self._serialize_vector_store(vs) for vs in page.data],
            "has_more": page.has_more,
            "last_id": getattr(page, "last_id", None),
        }

    def create_vector_store(self, *, name: str | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if name is not None:
            kwargs["name"] = name
        vs = self._client.vector_stores.create(**kwargs)
        return self._serialize_vector_store(vs)

    def retrieve_vector_store(self, vector_store_id: str) -> dict[str, Any]:
        vs = self._client.vector_stores.retrieve(vector_store_id)
        return self._serialize_vector_store(vs)

    def delete_vector_store(self, vector_store_id: str) -> None:
        self._client.vector_stores.delete(vector_store_id)

    def list_vector_store_files(
        self,
        vector_store_id: str,
        *,
        limit: int = 50,
        after: str | None = None,
    ) -> dict[str, Any]:
        page = self._client.vector_stores.files.list(
            vector_store_id=vector_store_id,
            limit=limit,
            after=after,
        )
        rows: list[dict[str, Any]] = []
        for vsf in page.data:
            rows.append(self._serialize_vector_store_file(vector_store_id, vsf))
        return {
            "data": rows,
            "has_more": page.has_more,
            "last_id": getattr(page, "last_id", None),
        }

    def upload_and_attach_file(
        self,
        vector_store_id: str,
        *,
        filename: str,
        content: bytes,
    ) -> dict[str, Any]:
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            validate_pdf_leading_bytes(content)
        file_resp = self._client.files.create(
            file=(filename, BytesIO(content)),
            purpose="assistants",
        )
        try:
            vsf = self._client.vector_stores.files.create(
                vector_store_id=vector_store_id,
                file_id=file_resp.id,
            )
        except Exception:
            try:
                self._client.files.delete(file_resp.id)
            except Exception:
                logger.exception("Failed to delete orphan file after vector store attach error")
            raise
        return self._serialize_vector_store_file(
            vector_store_id, vsf, filename_hint=file_resp.filename or filename
        )

    def detach_file_from_vector_store(self, vector_store_id: str, file_id: str) -> Any:
        """Remove one attachment from the vector store only (does not delete the OpenAI file object)."""
        return self._client.vector_stores.files.delete(
            vector_store_id=vector_store_id,
            file_id=file_id,
        )

    def delete_openai_file(self, file_id: str) -> None:
        """Delete the uploaded file object from OpenAI storage (404 = already gone)."""
        try:
            self._client.files.delete(file_id)
        except APIStatusError as e:
            if getattr(e, "status_code", None) == 404:
                return
            raise

    def _resolve_store_and_openai_file_ids(
        self, vector_store_id: str, target_id: str
    ) -> tuple[str, str | None]:
        """
        Resolve both identifiers needed for deletion:
        - vector_store_file_id: identifier accepted by vector_stores.files.delete(...)
        - openai_file_id: identifier accepted by files.delete(...)
        """
        page = self._client.vector_stores.files.list(vector_store_id=vector_store_id, limit=100)
        for vsf in page.data:
            vector_store_file_id = getattr(vsf, "id", None)
            openai_file_id = getattr(vsf, "file_id", None)
            if vector_store_file_id == target_id or openai_file_id == target_id:
                if vector_store_file_id is None:
                    raise ValueError("Vector store file id is missing from OpenAI response.")
                if openai_file_id is None and isinstance(vector_store_file_id, str):
                    # Some SDK versions expose file IDs directly as `id` on this object.
                    if vector_store_file_id.startswith("file-"):
                        openai_file_id = vector_store_file_id
                return str(vector_store_file_id), str(openai_file_id) if openai_file_id else None
        return target_id, target_id if target_id.startswith("file-") else None

    def remove_file_from_store(self, vector_store_id: str, file_id: str) -> None:
        """Detach from store first, then delete underlying OpenAI file when known."""
        vector_store_file_id, openai_file_id = self._resolve_store_and_openai_file_ids(
            vector_store_id, file_id
        )
        detach_resp = self.detach_file_from_vector_store(vector_store_id, vector_store_file_id)
        if hasattr(detach_resp, "deleted") and getattr(detach_resp, "deleted") is False:
            raise ValueError("OpenAI did not detach the file from the vector store.")
        if openai_file_id:
            self.delete_openai_file(openai_file_id)

    def _serialize_vector_store(self, vs: Any) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": vs.id,
            "name": getattr(vs, "name", None),
            "status": getattr(vs, "status", None),
            "created_at": getattr(vs, "created_at", None),
            "file_counts": None,
        }
        fc = getattr(vs, "file_counts", None)
        if fc is not None:
            if hasattr(fc, "model_dump"):
                out["file_counts"] = fc.model_dump()
            elif isinstance(fc, dict):
                out["file_counts"] = fc
        return out

    def _serialize_vector_store_file(
        self,
        vector_store_id: str,
        vsf: Any,
        filename_hint: str | None = None,
    ) -> dict[str, Any]:
        vector_store_file_id = getattr(vsf, "id", None)
        file_id = getattr(vsf, "file_id", None)
        if file_id is None and isinstance(vector_store_file_id, str):
            if vector_store_file_id.startswith("file-"):
                file_id = vector_store_file_id
        if file_id is None and vector_store_file_id is not None:
            file_id = str(vector_store_file_id)
        filename = filename_hint
        if filename is None and file_id:
            try:
                finfo = self._client.files.retrieve(file_id)
                filename = getattr(finfo, "filename", None)
            except Exception:
                logger.debug("Could not retrieve file metadata for %s", file_id)
        return {
            "file_id": file_id,
            "vector_store_file_id": vector_store_file_id,
            "vector_store_id": vector_store_id,
            "status": getattr(vsf, "status", None),
            "created_at": getattr(vsf, "created_at", None),
            "usage_bytes": getattr(vsf, "usage_bytes", None),
            "filename": filename,
        }
