from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from .analytics import export_powerbi
from .config import Settings
from .connectors import (
    GraphConnector,
    ServiceNowConnector,
    demo_records,
    outlook_desktop_calendar,
)
from .models import KnowledgeRecord
from .notifications import critical_incidents, notify_email, notify_local, notify_teams
from .rag import AzureOpenAI, local_answer
from .search import AzureSearch, LocalSearch
from .storage import AzureBlobStorage, LocalStorage


class EnterpriseAssistant:
    def __init__(self, settings: Settings):
        self.settings = settings
        if settings.app_mode == "azure":
            self.ai = AzureOpenAI(settings)
            self.storage = AzureBlobStorage(settings)
            self.search = AzureSearch(settings, self.ai.embed)
        else:
            self.ai = None
            self.storage = LocalStorage(settings.data_dir)
            self.search = LocalSearch(self.storage.load_all())

    def ingest(self, include_demo: bool = False, include_desktop: bool = False):
        if self.settings.app_mode == "local" or include_demo:
            records = demo_records()
        else:
            graph = GraphConnector(self.settings)
            records = graph.messages() + graph.calendar() + graph.teams()
            if self.settings.servicenow_url:
                records += ServiceNowConnector(self.settings).incidents()
        if include_desktop:
            records += outlook_desktop_calendar(self.settings)
        for record in records:
            self.storage.upsert(record)
        self.search.upsert(records)
        return records

    def ask(self, question: str, groups: list[str]):
        records = self.search.query(question, groups)
        return (
            self.ai.answer(question, records)
            if self.ai
            else local_answer(question, records)
        ), records


@dataclass(slots=True)
class IngestionResult:
    records: list[KnowledgeRecord]
    indexed: int


@dataclass(slots=True)
class AnswerResult:
    text: str
    citations: list[dict[str, str | int]]


class KnowledgeAssistant(EnterpriseAssistant):
    """Dashboard-friendly facade over the core assistant service."""

    def ingest(
        self, include_demo: bool = False, include_desktop: bool = False
    ) -> IngestionResult:
        records = super().ingest(
            include_demo=include_demo, include_desktop=include_desktop
        )
        return IngestionResult(records=records, indexed=len(records))

    def ingest_records(self, records: list[KnowledgeRecord]) -> IngestionResult:
        deduplicated = list({record.id: record for record in records}.values())
        for record in deduplicated:
            self.storage.upsert(record)
        self.search.upsert(deduplicated)
        return IngestionResult(records=deduplicated, indexed=len(deduplicated))

    def ask(self, question: str, groups: list[str]) -> AnswerResult:
        text, records = super().ask(question, groups)
        citations = [
            {
                "number": index,
                "source": record.source,
                "title": record.title,
                "url": record.url,
                "id": record.id,
            }
            for index, record in enumerate(records, start=1)
        ]
        return AnswerResult(text=text, citations=citations)

    def notify(
        self, records: list[KnowledgeRecord], channel: str, teams_webhook_url: str = ""
    ) -> int:
        alerts = critical_incidents(records)
        if not alerts:
            return 0
        if channel == "local":
            notify_local(alerts, self.settings.data_dir)
        elif channel == "email":
            notify_email(alerts, self.settings)
        elif channel == "teams":
            notify_teams(
                alerts,
                replace(
                    self.settings,
                    teams_webhook_url=teams_webhook_url
                    or self.settings.teams_webhook_url,
                ),
            )
        else:
            raise ValueError("channel must be local, email, or teams")
        return len(alerts)

    def post_teams_summary(
        self, records: list[KnowledgeRecord], webhook_url: str
    ) -> None:
        notify_teams(records, replace(self.settings, teams_webhook_url=webhook_url))

    def export(self, records: list[KnowledgeRecord]) -> str:
        return export_powerbi(
            records,
            Path(self.settings.data_dir) / "powerbi" / "operational_records.csv",
        )
