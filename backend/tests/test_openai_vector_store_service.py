from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.openai_vector_store_service import OpenAIVectorStoreService


class _FakeVectorStoreFilesApi:
    def __init__(self, rows: list[SimpleNamespace], deleted: bool = True) -> None:
        self._rows = rows
        self._deleted = deleted
        self.delete_calls: list[tuple[str, str]] = []

    def list(self, *, vector_store_id: str, limit: int = 100):  # noqa: ARG002
        return SimpleNamespace(data=self._rows)

    def delete(self, *, vector_store_id: str, file_id: str):
        self.delete_calls.append((vector_store_id, file_id))
        return SimpleNamespace(deleted=self._deleted)


class _FakeFilesApi:
    def __init__(self) -> None:
        self.deleted_file_ids: list[str] = []

    def delete(self, file_id: str):
        self.deleted_file_ids.append(file_id)
        return SimpleNamespace(deleted=True)


class _FakeClient:
    def __init__(self, rows: list[SimpleNamespace], detach_deleted: bool = True) -> None:
        self.vector_stores = SimpleNamespace(
            files=_FakeVectorStoreFilesApi(rows=rows, deleted=detach_deleted)
        )
        self.files = _FakeFilesApi()


def _make_service_with_client(fake_client: _FakeClient) -> OpenAIVectorStoreService:
    with patch("app.services.openai_vector_store_service.OpenAI", return_value=fake_client):
        return OpenAIVectorStoreService("test-key")


def test_remove_file_from_store_uses_vector_store_file_id_for_detach() -> None:
    fake_client = _FakeClient(rows=[SimpleNamespace(id="vsf_123", file_id="file_abc")])
    service = _make_service_with_client(fake_client)

    service.remove_file_from_store("vs_1", "file_abc")

    assert fake_client.vector_stores.files.delete_calls == [("vs_1", "vsf_123")]
    assert fake_client.files.deleted_file_ids == ["file_abc"]


def test_remove_file_from_store_handles_sdk_shape_with_only_file_id() -> None:
    fake_client = _FakeClient(rows=[SimpleNamespace(id="file_abc")])
    service = _make_service_with_client(fake_client)

    service.remove_file_from_store("vs_1", "file_abc")

    assert fake_client.vector_stores.files.delete_calls == [("vs_1", "file_abc")]
    assert fake_client.files.deleted_file_ids == ["file_abc"]


def test_remove_file_from_store_raises_when_detach_not_deleted() -> None:
    fake_client = _FakeClient(
        rows=[SimpleNamespace(id="vsf_123", file_id="file_abc")],
        detach_deleted=False,
    )
    service = _make_service_with_client(fake_client)

    with pytest.raises(ValueError, match="did not detach"):
        service.remove_file_from_store("vs_1", "file_abc")

    assert fake_client.vector_stores.files.delete_calls == [("vs_1", "vsf_123")]
    assert fake_client.files.deleted_file_ids == []
