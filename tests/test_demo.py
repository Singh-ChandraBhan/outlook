import csv
import json

from enterprise_assistant.analytics import POWERBI_COLUMNS, export_powerbi
from enterprise_assistant.connectors import demo_records
from enterprise_assistant.models import KnowledgeRecord, stable_id
from enterprise_assistant.notifications import adaptive_card, critical_incidents
from enterprise_assistant.rag import local_answer
from enterprise_assistant.search import LocalSearch
from enterprise_assistant.storage import LocalStorage, record_path


def test_demo_is_deterministic():
    assert [r.to_json() for r in demo_records()] == [r.to_json() for r in demo_records()]


def test_stable_ids():
    assert stable_id("outlook", "42") == stable_id("outlook", "42")
    assert stable_id("outlook", "42") != stable_id("teams", "42")


def test_storage_and_index_upserts(tmp_path):
    record = demo_records()[0]; store = LocalStorage(tmp_path)
    first = store.upsert(record); second = store.upsert(record)
    assert first == second and len(store.load_all()) == 1
    index = LocalSearch([]); index.upsert([record, record])
    assert len(index.records) == 1
    assert record_path(record).endswith(f"/{record.id}.json")


def test_access_filtering_happens_before_results():
    search = LocalSearch(demo_records())
    assert all("employees" in r.allowed_groups for r in search.query("checkout", ["employees"]))
    assert not search.query("checkout", ["unknown"])


def test_grounded_citations_and_refusal():
    record = demo_records()[0]
    assert f"[{record.id}]" in local_answer("when", [record])
    assert "enough authorized evidence" in local_answer("when", [])


def test_alerts_are_deduplicated_and_card_is_valid():
    incident = demo_records()[-1]
    alerts = critical_incidents([incident, incident])
    assert len(alerts) == 1
    card = adaptive_card(alerts)
    assert card["type"] == "message"
    assert card["attachments"][0]["content"]["type"] == "AdaptiveCard"
    assert incident.source_id in json.dumps(card)


def test_powerbi_schema_and_bom(tmp_path):
    path = tmp_path / "operations.csv"
    export_powerbi(demo_records(), path)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        assert next(csv.reader(handle)) == POWERBI_COLUMNS
