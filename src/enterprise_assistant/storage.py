from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .config import Settings
from .models import KnowledgeRecord


def record_path(record: KnowledgeRecord) -> str:
    date = (record.created_at or record.updated_at)[:10].split("-")
    year, month, day = date if len(date) == 3 else ("unknown", "00", "00")
    return f"normalized/{record.source}/{year}/{month}/{day}/{record.id}.json"


class RecordStorage(Protocol):
    def upsert(self, record: KnowledgeRecord) -> str: ...
    def load_all(self) -> list[KnowledgeRecord]: ...


class LocalStorage:
    def __init__(self, root: str | Path): self.root = Path(root)

    def upsert(self, record: KnowledgeRecord) -> str:
        path = self.root / record_path(record)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(record.to_json(), encoding="utf-8")
        return str(path)

    def load_all(self) -> list[KnowledgeRecord]:
        base = self.root / "normalized"
        if not base.exists(): return []
        return [KnowledgeRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
                for path in sorted(base.rglob("*.json"))]


class AzureBlobStorage:
    def __init__(self, settings: Settings):
        from azure.storage.blob import ContainerClient
        if settings.azure_storage_connection_string:
            self.client = ContainerClient.from_connection_string(settings.azure_storage_connection_string,
                                                                  settings.azure_storage_container)
        else:
            from azure.identity import DefaultAzureCredential
            self.client = ContainerClient(settings.azure_storage_account_url,
                                          settings.azure_storage_container, DefaultAzureCredential())

    def upsert(self, record: KnowledgeRecord) -> str:
        name = record_path(record)
        self.client.upload_blob(name, record.to_json(), overwrite=True)
        return name

    def load_all(self) -> list[KnowledgeRecord]:
        records = []
        for blob in self.client.list_blobs(name_starts_with="normalized/"):
            raw = self.client.download_blob(blob.name).readall()
            records.append(KnowledgeRecord.from_dict(json.loads(raw)))
        return records
