from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


def stable_id(source: str, source_id: str) -> str:
    return hashlib.sha256(f"{source}:{source_id}".encode("utf-8")).hexdigest()


@dataclass(slots=True)
class KnowledgeRecord:
    id: str
    source: str
    source_id: str
    title: str
    content: str
    created_at: str
    updated_at: str
    url: str = ""
    record_type: str = "document"
    status: str = ""
    priority: str = ""
    owner: str = ""
    classification: str = "internal"
    allowed_groups: list[str] = field(default_factory=lambda: ["employees"])
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, source: str, source_id: str, title: str, content: str, **kwargs: Any) -> "KnowledgeRecord":
        now = datetime.now(timezone.utc).isoformat()
        return cls(id=stable_id(source, source_id), source=source, source_id=source_id,
                   title=title, content=content, created_at=kwargs.pop("created_at", now),
                   updated_at=kwargs.pop("updated_at", now), **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "KnowledgeRecord":
        return cls(**value)
