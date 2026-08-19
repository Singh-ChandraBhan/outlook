from __future__ import annotations

import csv
from pathlib import Path

from .models import KnowledgeRecord

POWERBI_COLUMNS = ["id", "source", "source_id", "record_type", "title", "status", "priority", "owner",
                   "classification", "created_at", "updated_at", "url", "allowed_groups"]


def export_powerbi(records: list[KnowledgeRecord], path: str | Path) -> str:
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=POWERBI_COLUMNS)
        writer.writeheader()
        for r in records:
            row = r.to_dict(); row["allowed_groups"] = "|".join(r.allowed_groups)
            writer.writerow({k: row.get(k, "") for k in POWERBI_COLUMNS})
    return str(target)
