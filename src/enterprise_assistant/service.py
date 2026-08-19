from __future__ import annotations

from .config import Settings
from .connectors import GraphConnector, ServiceNowConnector, demo_records, outlook_desktop_calendar
from .rag import AzureOpenAI, local_answer
from .search import AzureSearch, LocalSearch
from .storage import AzureBlobStorage, LocalStorage


class EnterpriseAssistant:
    def __init__(self, settings: Settings):
        self.settings = settings
        if settings.app_mode == "azure":
            self.ai = AzureOpenAI(settings); self.storage = AzureBlobStorage(settings)
            self.search = AzureSearch(settings, self.ai.embed)
        else:
            self.ai = None; self.storage = LocalStorage(settings.data_dir)
            self.search = LocalSearch(self.storage.load_all())

    def ingest(self, include_demo: bool = False, include_desktop: bool = False):
        if self.settings.app_mode == "local" or include_demo:
            records = demo_records()
        else:
            graph = GraphConnector(self.settings)
            records = graph.messages() + graph.calendar() + graph.teams()
            if self.settings.servicenow_url: records += ServiceNowConnector(self.settings).incidents()
        if include_desktop: records += outlook_desktop_calendar(self.settings)
        for record in records: self.storage.upsert(record)
        self.search.upsert(records)
        return records

    def ask(self, question: str, groups: list[str]):
        records = self.search.query(question, groups)
        return (self.ai.answer(question, records) if self.ai else local_answer(question, records)), records
