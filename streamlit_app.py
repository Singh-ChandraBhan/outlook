from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

from enterprise_assistant import __file__ as package_file
from enterprise_assistant.config import Settings
from enterprise_assistant.connectors import (
    ExcelIncidentConnector,
    OutlookDesktopConnector,
)
from enterprise_assistant.service import KnowledgeAssistant

# Running a Streamlit file with plain Python normally produces repeated
# "missing ScriptRunContext" warnings. Make that common IDE/terminal action
# behave as expected by replacing it with the Streamlit server command.
if __name__ == "__main__" and get_script_run_ctx(suppress_warning=True) is None:
    app_path = Path(package_file).resolve().parents[2] / "streamlit_app.py"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.headless=true",
        ],
        check=False,
    )
    raise SystemExit(completed.returncode)


st.set_page_config(
    page_title="Enterprise Knowledge Assistant",
    page_icon="🔎",
    layout="wide",
)

APP_ROOT = Path(__file__).resolve().parent
HCLTECH_LOGO = APP_ROOT / "assets" / "hcltech-logo.svg"
APPLICATION_FLOW = APP_ROOT / "assets" / "application-flow.svg"
SAMPLE_INCIDENT_WORKBOOK = APP_ROOT / "data" / "incident.xlsx"
OUTLOOK_MAILBOX = os.getenv("OUTLOOK_DESKTOP_MAILBOX", "")
OUTLOOK_DATA_VERSION = "outlook-only-v1"


@st.cache_resource
def create_service() -> KnowledgeAssistant:
    return KnowledgeAssistant(Settings.from_env())


def ensure_records(service: KnowledgeAssistant):
    if "records" not in st.session_state:
        result = service.ingest()
        st.session_state.records = list(result.records)
        st.session_state.ingestion = result
    outlook_state_key = f"{OUTLOOK_MAILBOX}:{OUTLOOK_DATA_VERSION}"
    if (
        OUTLOOK_MAILBOX
        and st.session_state.get("outlook_loaded_mailbox") != outlook_state_key
    ):
        records = [
            record
            for record in st.session_state.records
            if record.record_type not in {"meeting_invite", "calendar_event"}
        ]
        try:
            outlook_records = OutlookDesktopConnector(
                OUTLOOK_MAILBOX,
                days_past=service.settings.calendar_days_past,
                days_future=service.settings.calendar_days_future,
            ).collect()
            records_by_id = {record.id: record for record in records + outlook_records}
            records = list(records_by_id.values())
            result = service.ingest_records(records)
            st.session_state.outlook_status = (
                f"Loaded {len(outlook_records)} meetings from {OUTLOOK_MAILBOX}"
            )
            st.session_state.outlook_loaded_mailbox = outlook_state_key
            st.session_state.ingestion = result
        except Exception as exc:
            st.session_state.outlook_status = f"Outlook calendar unavailable: {exc}"
        st.session_state.records = records
    return st.session_state.records


service = create_service()

brand_col, title_col = st.columns([1, 5], vertical_alignment="center")
with brand_col:
    st.image(str(HCLTECH_LOGO), width=170)
with title_col:
    st.title("Enterprise Knowledge Assistant")
    st.caption("Outlook · Microsoft Teams · ServiceNow · Azure AI · Power BI")

with st.container(border=True):
    st.subheader("Project details")
    st.markdown(
        "This application collects approved information from **Outlook, Microsoft Teams, "
        "and ServiceNow** and brings it into one searchable dashboard. It helps users:"
    )
    capability_col1, capability_col2 = st.columns(2)
    capability_col1.markdown(
        "- Ask questions and receive answers supported by source records\n"
        "- View Outlook meetings and schedules\n"
        "- Search and inspect normalized enterprise records"
    )
    capability_col2.markdown(
        "- Identify critical incidents and SLA risks\n"
        "- Create operational notifications\n"
        "- Export analytics data for Power BI"
    )
    st.caption(
        f"HCLTech · Enterprise Knowledge Assistant · v0.1.0 · "
        f"{service.settings.app_mode.title()} environment"
    )

with st.sidebar:
    st.header("Demo controls")
    st.info(f"Mode: **{service.settings.app_mode.upper()}**")
    if service.settings.app_mode == "local":
        st.caption(
            "Demo records with meetings read from the signed-in HCLTech Outlook profile."
        )
    if st.button("Collect and index data", type="primary", width="stretch"):
        with st.spinner("Collecting, normalizing, storing, and indexing records..."):
            result = service.ingest()
            st.session_state.records = result.records
            st.session_state.ingestion = result
            st.session_state.pop("outlook_loaded_mailbox", None)
        st.success(f"Processed {result.indexed} records")
    st.divider()
    st.subheader("Import incident data")
    incident_upload = st.file_uploader("Incident workbook", type=["xlsx"])
    incident_limit = st.selectbox("Incidents to import", options=[20, 30], index=0)
    workbook_source = incident_upload or (
        SAMPLE_INCIDENT_WORKBOOK if SAMPLE_INCIDENT_WORKBOOK.exists() else None
    )
    if SAMPLE_INCIDENT_WORKBOOK.exists() and incident_upload is None:
        st.caption("Ready to import bundled incident.xlsx")
    if st.button(
        "Import Excel incidents", disabled=workbook_source is None, width="stretch"
    ):
        try:
            with st.spinner("Reading, normalizing, and indexing incident records..."):
                imported_records = ExcelIncidentConnector(workbook_source).collect()[
                    :incident_limit
                ]
                result = service.ingest_records(imported_records)
                current_records = list(st.session_state.get("records", []))
                records_by_id = {
                    record.id: record for record in current_records + imported_records
                }
                st.session_state.records = list(records_by_id.values())
            st.success(f"Imported {result.indexed} incidents from Excel")
        except Exception as exc:
            st.error(f"Excel import failed: {exc}")
    access_groups = st.text_input("Access groups", value="employees,engineering")
    st.divider()
    st.subheader("HCLTech Outlook")
    outlook_mailbox = st.text_input("Mailbox", value=OUTLOOK_MAILBOX)
    if "outlook_status" in st.session_state:
        st.caption(st.session_state.outlook_status)
    if st.button("Fetch Outlook meetings", width="stretch"):
        try:
            with st.spinner("Reading the signed-in Outlook calendar..."):
                outlook_records = OutlookDesktopConnector(
                    outlook_mailbox,
                    days_past=service.settings.calendar_days_past,
                    days_future=service.settings.calendar_days_future,
                ).collect()
                result = service.ingest_records(outlook_records)
                current_records = [
                    record
                    for record in st.session_state.get("records", [])
                    if record.record_type not in {"meeting_invite", "calendar_event"}
                ]
                records_by_id = {
                    record.id: record for record in current_records + outlook_records
                }
                st.session_state.records = list(records_by_id.values())
                st.session_state.outlook_loaded_mailbox = (
                    f"{outlook_mailbox.lower()}:{OUTLOOK_DATA_VERSION}"
                )
            st.success(f"Fetched {result.indexed} Outlook meetings")
        except Exception as exc:
            st.error(f"Outlook calendar fetch failed: {exc}")

try:
    records = ensure_records(service)
except Exception as exc:
    st.error(f"Application initialization failed: {exc}")
    st.stop()

sources = {record.source for record in records}
critical = {
    record.metadata.get("incident_id", record.id)
    for record in records
    if record.priority.upper() == "P1"
}
meetings = [
    record
    for record in records
    if record.record_type in {"meeting_invite", "calendar_event"}
]

with st.container(border=True):
    st.subheader("Use case")
    st.write(
        "MPC Midstream support teams use this application to bring incidents, Outlook communication, "
        "Teams collaboration, and meeting schedules into one operational view. Users can identify "
        "critical issues, search normalized records, ask grounded questions, track meetings, create "
        "notifications, and export data for Power BI reporting."
    )

    st.markdown("**Application flow**")
    st.image(str(APPLICATION_FLOW), width="stretch")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric(
    "Knowledge records",
    len(records),
    help="Total normalized and searchable records collected from all configured sources.",
)
col2.metric(
    "Connected sources",
    len(sources),
    help="Number of enterprise source systems currently represented in the dashboard.",
)
col3.metric(
    "Critical incidents",
    len(critical),
    help="Unique incidents classified as priority P1 and requiring immediate attention.",
)
col4.metric(
    "Meetings",
    len(meetings),
    help="Outlook calendar events and Microsoft Teams meeting invitations available for review.",
)
col5.metric(
    "Operating mode",
    service.settings.app_mode.title(),
    help="Local uses safe demo data; Azure connects to configured enterprise services.",
)

ask_tab, meetings_tab, records_tab, alerts_tab, analytics_tab = st.tabs(
    [
        "Ask Assistant",
        "Meeting schedule",
        "Knowledge records",
        "Notifications",
        "Power BI data",
    ]
)

with ask_tab:
    st.subheader("Ask across enterprise systems")
    question = st.text_area(
        "Question",
        value="Summarize DEMO-INC-1001, including impact, owner, cause, workaround, and SLA risk.",
        height=100,
    )
    if st.button(
        "Generate grounded answer", type="primary", disabled=not question.strip()
    ):
        with st.spinner("Searching accessible records..."):
            answer = service.ask(
                question.strip(),
                [group.strip() for group in access_groups.split(",") if group.strip()],
            )
        st.markdown(answer.text)
        if answer.citations:
            st.subheader("Sources")
            for citation in answer.citations:
                label = f"[{citation['number']}] {citation['source'].title()} — {citation['title']}"
                if citation["url"]:
                    st.markdown(f"- [{label}]({citation['url']})")
                else:
                    st.markdown(f"- {label}")

with meetings_tab:
    st.subheader("Outlook meeting invitations and schedule")
    if meetings:
        meeting_rows = [
            {
                "Start": meeting.metadata.get("meeting_start", ""),
                "End": meeting.metadata.get("meeting_end", ""),
                "Subject": meeting.title,
                "Type": "Invitation"
                if meeting.record_type == "meeting_invite"
                else "Organized event",
                "Response": meeting.metadata.get("response", meeting.status),
                "Organizer": meeting.metadata.get("organizer", meeting.owner),
                "Location": meeting.metadata.get("location", ""),
                "Attendees": "; ".join(meeting.metadata.get("attendees", [])),
                "Online": meeting.metadata.get("is_online_meeting", False),
            }
            for meeting in sorted(
                meetings, key=lambda item: item.metadata.get("meeting_start", "")
            )
        ]
        st.dataframe(pd.DataFrame(meeting_rows), width="stretch", hide_index=True)
        meeting = st.selectbox(
            "Meeting details", meetings, format_func=lambda item: item.title
        )
        start = meeting.metadata.get("meeting_start", "Not provided")
        end = meeting.metadata.get("meeting_end", "Not provided")
        st.write(
            f"**Schedule:** {start} – {end} ({meeting.metadata.get('timezone', '')})"
        )
        st.write(f"**Organizer:** {meeting.metadata.get('organizer', meeting.owner)}")
        st.write(f"**Location:** {meeting.metadata.get('location', 'Not provided')}")
        attendees = meeting.metadata.get("attendees", [])
        optional_attendees = meeting.metadata.get("optional_attendees", [])
        st.write(
            f"**Required attendees:** {'; '.join(attendees) if attendees else 'Not provided'}"
        )
        if optional_attendees:
            st.write(f"**Optional attendees:** {'; '.join(optional_attendees)}")
        if meeting.content:
            with st.expander("Meeting notes"):
                st.text(meeting.content)
        if meeting.metadata.get("join_url"):
            st.link_button("Join online meeting", meeting.metadata["join_url"])
        if meeting.url:
            st.link_button("Open in Outlook", meeting.url)
    else:
        st.info("No meetings were found in the configured calendar window.")

with records_tab:
    st.subheader("Normalized records")
    source_filter = st.multiselect("Source", sorted(sources), default=sorted(sources))
    rows = [
        {
            "Record ID": (
                record.metadata.get("incident_id")
                or record.metadata.get("request_id")
                or record.source_id
            ),
            "Source": record.source,
            "Type": record.record_type,
            "Business Area": record.metadata.get(
                "business_area", "Enterprise Operations"
            ),
            "Title": record.title,
            "Status": record.status,
            "Priority": record.priority,
            "Owner": record.owner,
            "Assignment Group": record.metadata.get("assignment_group", ""),
            "SLA Remaining (hrs)": str(record.metadata.get("sla_hours_remaining", "")),
            "Keywords": ", ".join(record.metadata.get("keywords", [])),
            "Updated": record.updated_at,
        }
        for record in records
        if record.source in source_filter
    ]
    records_dataframe = pd.DataFrame(rows)
    if not records_dataframe.empty:
        # PyArrow requires a column to have one stable type. Excel and demo
        # records can supply SLA values as integers, blanks, or nulls.
        records_dataframe["SLA Remaining (hrs)"] = (
            records_dataframe["SLA Remaining (hrs)"].fillna("").astype("string")
        )
    st.dataframe(records_dataframe, width="stretch", hide_index=True)
    selected = st.selectbox(
        "Inspect JSON", records, format_func=lambda record: record.title
    )
    st.json(selected.to_dict())

with alerts_tab:
    st.subheader("Operational notifications")
    teams_webhook_url = st.text_input(
        "Teams Workflow webhook URL",
        value=service.settings.teams_webhook_url,
        type="password",
        help="Kept only in this browser session; it is not saved to the repository.",
    ).strip()
    webhook_ready = bool(teams_webhook_url)
    st.caption(
        f"Teams Workflow webhook: {'Configured' if webhook_ready else 'Not configured'}"
    )
    if st.button("Post operational summary to Teams", disabled=not webhook_ready):
        try:
            service.post_teams_summary(records, teams_webhook_url)
            st.success("Posted the operational summary to Microsoft Teams.")
        except Exception as exc:
            st.error(f"Teams summary failed: {exc}")
    st.write(
        "Evaluate critical priority and near-SLA-breach conditions. Duplicate source records are correlated into one alert."
    )
    channel = st.selectbox("Delivery channel", ["local", "email", "teams"])
    if channel == "email":
        st.warning("Email delivery requires configured Microsoft Graph credentials.")
    elif channel == "teams":
        st.warning(
            "Teams delivery requires TEAMS_WEBHOOK_URL. Local mode writes safe outbox files."
        )
    if st.button("Evaluate and send notifications"):
        try:
            count = service.notify(
                records, channel, teams_webhook_url=teams_webhook_url
            )
            st.success(f"Created {count} notification(s).")
        except Exception as exc:
            st.error(f"Notification failed: {exc}")
    outbox = Path(service.settings.data_dir) / "outbox"
    files = sorted(outbox.glob("*.json")) if outbox.exists() else []
    if files:
        st.caption("Local notification outbox")
        for file in files:
            payload = json.loads(file.read_text(encoding="utf-8"))
            subject = (
                payload.get("subject", file.name)
                if isinstance(payload, dict)
                else file.name
            )
            with st.expander(subject):
                st.json(payload)

with analytics_tab:
    st.subheader("Power BI-ready operational data")
    report_path = service.export(records)
    dataframe = pd.read_csv(report_path)
    left, right = st.columns(2)
    with left:
        st.write("Records by source")
        st.bar_chart(dataframe["source"].value_counts())
    with right:
        st.write("Records by priority")
        st.bar_chart(dataframe["priority"].fillna("Not set").value_counts())
    st.dataframe(dataframe, width="stretch", hide_index=True)
    st.download_button(
        "Download Power BI CSV",
        data=Path(report_path).read_bytes(),
        file_name="operational_records.csv",
        mime="text/csv",
    )
