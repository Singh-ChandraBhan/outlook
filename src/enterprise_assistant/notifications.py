from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests

from .config import Settings
from .models import KnowledgeRecord


def critical_incidents(records: list[KnowledgeRecord]) -> list[KnowledgeRecord]:
    found = {}
    for r in records:
        try: sla = float(r.metadata.get("sla_hours"))
        except (TypeError, ValueError): sla = 999
        if r.record_type == "incident" and (r.priority.lower() in {"p1", "1", "critical"} or sla <= 4):
            found[r.source_id] = r
    return list(found.values())


def adaptive_card(records: list[KnowledgeRecord]) -> dict:
    facts = [{"title": r.source_id, "value": f"{r.priority or 'SLA'} — {r.title}"} for r in records]
    return {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive",
        "content": {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard",
                    "version": "1.4", "body": [{"type": "TextBlock", "text": "Critical incident alert",
                    "weight": "Bolder", "size": "Medium"}, {"type": "FactSet", "facts": facts}]}}]}


def _safe_webhook(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("TEAMS_WEBHOOK_URL must be a valid HTTPS URL")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def notify_local(records: list[KnowledgeRecord], data_dir: str) -> str:
    folder = Path(data_dir) / "outbox"; folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"alerts-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps([r.to_dict() for r in records], indent=2), encoding="utf-8")
    return str(path)


def notify_teams(records: list[KnowledgeRecord], settings: Settings) -> None:
    _safe_webhook(settings.teams_webhook_url)
    try:
        response = requests.post(settings.teams_webhook_url, json=adaptive_card(records), timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Teams webhook request failed for {_safe_webhook(settings.teams_webhook_url)}") from exc


def notify_email(records: list[KnowledgeRecord], settings: Settings) -> None:
    from azure.identity import ClientSecretCredential
    token = ClientSecretCredential(settings.graph_tenant_id, settings.graph_client_id,
                                   settings.graph_client_secret).get_token("https://graph.microsoft.com/.default").token
    lines = "<br>".join(f"{r.source_id}: {r.title}" for r in records)
    payload = {"message": {"subject": "Enterprise critical incident alert",
              "body": {"contentType": "HTML", "content": lines},
              "toRecipients": [{"emailAddress": {"address": settings.notification_email}}]}, "saveToSentItems": True}
    response = requests.post(f"https://graph.microsoft.com/v1.0/users/{settings.graph_user_id}/sendMail",
                             headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=30)
    response.raise_for_status()
