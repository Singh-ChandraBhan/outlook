from __future__ import annotations

import hashlib
import json
import math
import re

from .config import Settings
from .models import KnowledgeRecord


def feature_hash(text: str, dimensions: int = 256) -> list[float]:
    vector = [0.0] * dimensions
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        idx = int.from_bytes(digest[:4], "big") % dimensions
        vector[idx] += -1.0 if digest[4] & 1 else 1.0
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def _allowed(record: KnowledgeRecord, groups: set[str]) -> bool:
    return bool(groups.intersection(record.allowed_groups))


class LocalSearch:
    def __init__(self, records: list[KnowledgeRecord]): self.records = records
    def upsert(self, records: list[KnowledgeRecord]) -> None:
        merged = {x.id: x for x in self.records}
        merged.update({x.id: x for x in records})
        self.records = list(merged.values())
    def query(self, query: str, groups: list[str], top: int = 5) -> list[KnowledgeRecord]:
        qv = feature_hash(query)
        def score(r: KnowledgeRecord) -> float:
            rv = feature_hash(f"{r.title} {r.content}")
            return sum(a * b for a, b in zip(qv, rv))
        candidates = [r for r in self.records if _allowed(r, set(groups))]
        return sorted(candidates, key=lambda r: (-score(r), r.id))[:top]


class AzureSearch:
    def __init__(self, settings: Settings, embed):
        from azure.search.documents import SearchClient
        if settings.azure_search_api_key:
            from azure.core.credentials import AzureKeyCredential
            credential = AzureKeyCredential(settings.azure_search_api_key)
        else:
            from azure.identity import DefaultAzureCredential
            credential = DefaultAzureCredential()
        self.client = SearchClient(settings.azure_search_endpoint, settings.azure_search_index, credential)
        self.embed = embed

    def upsert(self, records: list[KnowledgeRecord]) -> None:
        docs = []
        for record in records:
            document = record.to_dict()
            document["metadata"] = json.dumps(document["metadata"], ensure_ascii=False, sort_keys=True)
            document["content_vector"] = self.embed(f"{record.title}\n{record.content}")
            docs.append(document)
        if docs: self.client.merge_or_upload_documents(docs)

    def query(self, query: str, groups: list[str], top: int = 5) -> list[KnowledgeRecord]:
        from azure.search.documents.models import VectorizedQuery
        escaped = [g.replace("'", "''") for g in groups]
        group_filter = " or ".join(f"allowed_groups/any(g: g eq '{g}')" for g in escaped) or "false"
        results = self.client.search(query, vector_queries=[VectorizedQuery(vector=self.embed(query),
                                     k_nearest_neighbors=top, fields="content_vector")],
                                     filter=f"({group_filter})", top=top)
        fields = set(KnowledgeRecord.__dataclass_fields__)
        normalized = []
        for item in results:
            document = {k: v for k, v in dict(item).items() if k in fields}
            if isinstance(document.get("metadata"), str):
                document["metadata"] = json.loads(document["metadata"] or "{}")
            normalized.append(KnowledgeRecord.from_dict(document))
        return normalized
