from __future__ import annotations

from dataclasses import dataclass, fields
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_mode: str = "local"
    data_dir: str = "data"
    outlook_desktop_mailbox: str = ""
    azure_storage_account_url: str = ""
    azure_storage_connection_string: str = ""
    azure_storage_container: str = "knowledge-json"
    azure_search_endpoint: str = ""
    azure_search_index: str = "enterprise-knowledge"
    azure_search_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str = ""
    azure_openai_embedding_deployment: str = ""
    embedding_dimensions: int = 1536
    graph_tenant_id: str = ""
    graph_client_id: str = ""
    graph_client_secret: str = ""
    graph_user_id: str = ""
    graph_team_id: str = ""
    graph_channel_id: str = ""
    notification_email: str = ""
    teams_webhook_url: str = ""
    calendar_days_past: int = 7
    calendar_days_future: int = 30
    servicenow_url: str = ""
    servicenow_username: str = ""
    servicenow_password: str = ""
    servicenow_table: str = "incident"

    @classmethod
    def from_env(cls) -> "Settings":
        values = {}
        for item in fields(cls):
            raw = os.environ.get(item.name.upper())
            if raw is not None:
                values[item.name] = int(raw) if item.type == "int" or item.name in {
                    "embedding_dimensions", "calendar_days_past", "calendar_days_future"} else raw
        settings = cls(**values)
        if settings.app_mode not in {"local", "azure"}:
            raise ValueError("APP_MODE must be local or azure")
        return settings

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    def missing_azure(self) -> list[str]:
        required = ["azure_storage_account_url", "azure_search_endpoint", "azure_openai_endpoint",
                    "azure_openai_chat_deployment", "azure_openai_embedding_deployment",
                    "graph_tenant_id", "graph_client_id", "graph_client_secret", "graph_user_id"]
        return [name.upper() for name in required if not getattr(self, name) or "<" in getattr(self, name)]
