from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_jwt_user
from app.models import User
from app.services.openai_credential_service import get_openai_api_key_for_user
from app.services.openai_vector_store_service import (
    MAX_VECTOR_STORE_UPLOAD_BYTES,
    OpenAIVectorStoreService,
    map_openai_exception,
    validate_upload_filename,
)

router = APIRouter(prefix="/api/ui", tags=["ui-vector-stores"])

_MAX_LIST_LIMIT = 100


def _vector_store_service(
    user: User = Depends(require_jwt_user),
    db: Session = Depends(get_db),
) -> OpenAIVectorStoreService:
    api_key = get_openai_api_key_for_user(db, user)
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OpenAI is not configured. Add your API key in Settings (or set OPENAI_API_KEY for local dev).",
        )
    return OpenAIVectorStoreService(api_key)


def _exec_openai(fn):
    try:
        return fn()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        code, msg = map_openai_exception(e)
        raise HTTPException(status_code=code, detail=msg) from e


class VectorStoreCreateBody(BaseModel):
    name: str | None = None


@router.get("/vector-stores")
def list_vector_stores(
    limit: Annotated[int, Query(ge=1, le=_MAX_LIST_LIMIT)] = 20,
    after: str | None = None,
    _user: User = Depends(require_jwt_user),
    service: OpenAIVectorStoreService = Depends(_vector_store_service),
) -> dict:
    return _exec_openai(lambda: service.list_vector_stores(limit=limit, after=after))


@router.post("/vector-stores")
def create_vector_store(
    body: VectorStoreCreateBody,
    _user: User = Depends(require_jwt_user),
    service: OpenAIVectorStoreService = Depends(_vector_store_service),
) -> dict:
    name = (body.name or "").strip() or None
    return _exec_openai(lambda: service.create_vector_store(name=name))


@router.get("/vector-stores/{vector_store_id}")
def get_vector_store(
    vector_store_id: str,
    _user: User = Depends(require_jwt_user),
    service: OpenAIVectorStoreService = Depends(_vector_store_service),
) -> dict:
    return _exec_openai(lambda: service.retrieve_vector_store(vector_store_id))


@router.get("/vector-stores/{vector_store_id}/files")
def list_vector_store_files(
    vector_store_id: str,
    limit: Annotated[int, Query(ge=1, le=_MAX_LIST_LIMIT)] = 50,
    after: str | None = None,
    _user: User = Depends(require_jwt_user),
    service: OpenAIVectorStoreService = Depends(_vector_store_service),
) -> dict:
    return _exec_openai(
        lambda: service.list_vector_store_files(vector_store_id, limit=limit, after=after)
    )


async def _read_upload_capped(upload: UploadFile) -> bytes:
    total = 0
    parts: list[bytes] = []
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_VECTOR_STORE_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds {MAX_VECTOR_STORE_UPLOAD_BYTES // (1024 * 1024)}MB limit.",
            )
        parts.append(chunk)
    return b"".join(parts)


@router.post("/vector-stores/{vector_store_id}/files")
async def upload_vector_store_file(
    vector_store_id: str,
    file: UploadFile = File(...),
    _user: User = Depends(require_jwt_user),
    service: OpenAIVectorStoreService = Depends(_vector_store_service),
) -> dict:
    try:
        safe_name = validate_upload_filename(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    content = await _read_upload_capped(file)
    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")

    return _exec_openai(
        lambda: service.upload_and_attach_file(
            vector_store_id,
            filename=safe_name,
            content=content,
        )
    )


@router.delete("/vector-stores/{vector_store_id}/files/{file_id}")
def delete_vector_store_file(
    vector_store_id: str,
    file_id: str,
    _user: User = Depends(require_jwt_user),
    service: OpenAIVectorStoreService = Depends(_vector_store_service),
) -> dict:
    _exec_openai(lambda: service.remove_file_from_store(vector_store_id, file_id))
    return {"ok": True}


@router.delete("/vector-stores/{vector_store_id}")
def delete_vector_store(
    vector_store_id: str,
    _user: User = Depends(require_jwt_user),
    service: OpenAIVectorStoreService = Depends(_vector_store_service),
) -> dict:
    _exec_openai(lambda: service.delete_vector_store(vector_store_id))
    return {"ok": True}
