from __future__ import annotations

from pathlib import Path
import tempfile
import streamlit as st

from enterprise_assistant.analytics import export_powerbi
from enterprise_assistant.config import Settings
from enterprise_assistant.connectors import incidents_from_xlsx, outlook_desktop_calendar
from enterprise_assistant.notifications import critical_incidents, notify_local
from enterprise_assistant.service import EnterpriseAssistant

CSS = """
<style>
:root{--navy:#0a2148;--blue:#075bea;--blue-dark:#0649bb;--red:#ef3f4a;--line:#dce4ef;--muted:#64748b;--surface:#f7f9fc}
html,body,[class*="css"],.stApp,button,input,textarea,select{font-family:"Segoe UI",Inter,Arial,sans-serif!important}
.stApp{color:var(--navy);background:linear-gradient(180deg,#fff 0%,#fbfcff 100%);font-size:14px}
.block-container{max-width:1500px;padding-top:2.4rem;padding-bottom:4rem}h1,h2,h3{color:var(--navy)!important;letter-spacing:-.025em;font-weight:750!important}p,li{line-height:1.65}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#f4f7fb 0%,#edf2f8 100%);border-right:1px solid var(--line)}
[data-testid="stSidebar"] .block-container{padding:2rem 1.35rem}[data-testid="stSidebar"] h3{font-size:15px!important;margin-bottom:8px}[data-testid="stSidebar"] label{font-size:12px!important;font-weight:650;color:#34445e}
[data-testid="stSidebar"] [data-testid="stAlert"]{border-radius:10px;border:1px solid #cbdcff;background:#eaf2ff;color:#164a9b}
.brand-row{display:grid;grid-template-columns:220px 1fr;align-items:center;margin-bottom:22px;padding:2px 0 8px}.brand{color:#0763e7;font-size:31px;font-weight:800;letter-spacing:-1.5px}.brand-title{font-size:31px;font-weight:800;letter-spacing:-.6px}.subtitle{color:#8793a6;font-size:12px;font-weight:500;margin-top:6px;letter-spacing:.02em}
.panel{background:rgba(255,255,255,.95);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:12px 0;box-shadow:0 2px 8px rgba(20,48,90,.035)}.panel h3{margin:0 0 11px;font-size:19px}.details-grid{display:grid;grid-template-columns:1fr 1fr;gap:45px;font-size:12.5px}.details-grid ul{margin:6px 0 0;padding-left:18px;line-height:1.9}
.flow{background:linear-gradient(135deg,#f8fbff,#f1f6ff);border:1.5px solid #cfe0ff;border-radius:26px;padding:42px 28px;display:flex;align-items:center;justify-content:space-between;gap:10px}.flow-card{background:#fff;border:1.5px solid #91b8ff;border-radius:18px;padding:26px 14px;text-align:center;width:18%;min-height:148px;box-shadow:0 10px 24px rgba(38,78,150,.11);transition:transform .2s ease,box-shadow .2s ease}.flow-card:hover{transform:translateY(-4px);box-shadow:0 15px 30px rgba(38,78,150,.16)}.flow-step{color:var(--blue);font-weight:800;font-size:17px;letter-spacing:.02em}.flow-title{font-weight:780;font-size:20px;margin:16px 0}.flow-copy{color:#536786;font-size:15px;line-height:1.55}.arrow{color:#3766df;font-size:40px;font-weight:600}
div[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px!important;box-shadow:0 3px 10px rgba(20,48,90,.04)}div[data-testid="stMetricLabel"]{color:var(--muted);font-size:12px;font-weight:650}div[data-testid="stMetricValue"]{color:var(--navy);font-size:25px;font-weight:750}
.stButton>button,.stDownloadButton>button{min-height:40px;border-radius:8px!important;padding:.55rem 1rem!important;font-size:13px!important;font-weight:700!important;letter-spacing:.01em;border:1px solid #c9d4e3;background:#fff;color:#17335e;box-shadow:0 1px 2px rgba(15,38,75,.05);transition:all .18s ease}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:var(--blue);color:var(--blue);background:#f3f7ff;box-shadow:0 5px 14px rgba(7,91,234,.13);transform:translateY(-1px)}
.stButton>button:focus-visible,.stDownloadButton>button:focus-visible{outline:3px solid rgba(7,91,234,.2);outline-offset:2px}
.stButton>button[kind="primary"]{color:#fff;background:linear-gradient(135deg,#f34b55,#e72f3b);border-color:#e72f3b;box-shadow:0 4px 12px rgba(239,63,74,.2)}.stButton>button[kind="primary"]:hover{color:#fff;background:linear-gradient(135deg,#e93b46,#d92531);border-color:#d92531;box-shadow:0 7px 18px rgba(239,63,74,.28)}
.stButton>button:disabled{opacity:.48;box-shadow:none;transform:none}
[data-baseweb="input"]>div,[data-baseweb="textarea"]>div,[data-baseweb="select"]>div,.stTextInput input,.stTextArea textarea{border-radius:8px!important;border-color:#cfd9e7!important;background:#f8faff!important;font-size:13px!important}.stTextInput input:focus,.stTextArea textarea:focus{border-color:var(--blue)!important;box-shadow:0 0 0 3px rgba(7,91,234,.12)!important}
.stTabs [data-baseweb="tab-list"]{gap:26px;border-bottom:1px solid var(--line);margin-top:10px}.stTabs [data-baseweb="tab"]{padding:14px 1px 11px;font-size:12.5px;font-weight:650;color:#5d6b80}.stTabs [aria-selected="true"]{color:var(--red)!important;font-weight:750}.stTabs [data-baseweb="tab-highlight"]{background-color:var(--red)!important;height:3px}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:10px;overflow:hidden}.small-note{font-size:11px;color:#8b95a7;margin-top:8px}
@media(max-width:900px){.block-container{padding-top:1.25rem}.brand-row{grid-template-columns:1fr;gap:8px}.brand-title{font-size:25px}.flow{overflow-x:auto;padding:28px 20px}.flow-card{min-width:190px}.details-grid{grid-template-columns:1fr}.arrow{font-size:28px}}
</style>"""


def _flow_html() -> str:
    steps = [("1 · SOURCES","Enterprise data","Outlook · Teams<br>ServiceNow · Excel"),("2 · COLLECT","Secure ingestion","Read approved<br>operational records"),("3 · NORMALIZE","Knowledge records","Clean · classify<br>index · access control"),("4 · ANALYZE","Ask Assistant","Search and grounded<br>answers with sources"),("5 · ACT","Operational action","Alerts · Meetings<br>Power BI insights")]
    cards=[]
    for i,(step,title,copy) in enumerate(steps):
        if i: cards.append('<div class="arrow">→</div>')
        cards.append(f'<div class="flow-card"><div class="flow-step">{step}</div><div class="flow-title">{title}</div><div class="flow-copy">{copy}</div></div>')
    return '<div class="flow">'+''.join(cards)+'</div>'


def _sidebar(settings: Settings, service: EnterpriseAssistant) -> None:
    st.sidebar.subheader("Demo controls")
    st.sidebar.info(f"Mode: **{settings.app_mode.upper()}**")
    st.sidebar.caption("Collect approved records from configured enterprise sources.")
    if st.sidebar.button("Collect and index data", type="primary", use_container_width=True):
        with st.spinner("Collecting and normalizing records..."):
            count=len(service.ingest(include_demo=settings.app_mode=="local"))
        st.sidebar.success(f"Indexed {count} records"); st.rerun()
    st.sidebar.divider(); st.sidebar.subheader("Import incident data")
    upload=st.sidebar.file_uploader("Incident workbook",type=["xlsx"])
    limit=st.sidebar.selectbox("Incidents to import",[20,50,100])
    groups=st.sidebar.text_input("Access groups","employees,engineering")
    if st.sidebar.button("Import Excel incidents",use_container_width=True,disabled=upload is None):
        with tempfile.NamedTemporaryFile(suffix=".xlsx",delete=False) as handle:
            handle.write(upload.getbuffer()); temp_path=handle.name
        records=incidents_from_xlsx(temp_path)[:limit]; allowed=[x.strip() for x in groups.split(",") if x.strip()]
        for record in records: record.allowed_groups=allowed; service.storage.upsert(record)
        service.search.upsert(records); Path(temp_path).unlink(missing_ok=True)
        st.sidebar.success(f"Imported {len(records)} incidents"); st.rerun()
    st.sidebar.divider(); st.sidebar.subheader("HCLTech Outlook"); st.sidebar.caption("Mailbox")
    st.sidebar.code(settings.outlook_desktop_mailbox or "Not configured",language=None)
    if st.sidebar.button("Fetch Outlook meetings",use_container_width=True,disabled=not settings.outlook_desktop_mailbox):
        meetings=outlook_desktop_calendar(settings)
        for record in meetings: service.storage.upsert(record)
        service.search.upsert(meetings); st.sidebar.success(f"Fetched {len(meetings)} meetings"); st.rerun()


def render_app() -> None:
    st.set_page_config(page_title="Enterprise Knowledge Assistant",page_icon="🔎",layout="wide")
    st.markdown(CSS,unsafe_allow_html=True)
    settings=Settings.from_env(); service=EnterpriseAssistant(settings); _sidebar(settings,service)
    st.markdown('<div class="brand-row"><div class="brand">HCLTech</div><div><div class="brand-title">Enterprise Knowledge Assistant</div><div class="subtitle">Outlook · Microsoft Teams · ServiceNow · Azure AI · Power BI</div></div></div>',unsafe_allow_html=True)
    st.markdown('<div class="panel"><h3>Project details</h3><div style="font-size:12px">This application collects approved information from <b>Outlook, Microsoft Teams, and ServiceNow</b> and brings it into one searchable dashboard. It helps users:</div><div class="details-grid"><ul><li>Ask questions and receive answers supported by source records</li><li>View Outlook meetings and schedules</li><li>Search and inspect normalized enterprise records</li></ul><ul><li>Identify critical incidents and SLA risks</li><li>Create operational notifications</li><li>Export analytics data for Power BI</li></ul></div><div class="small-note">HCLTech · Enterprise Knowledge Assistant · v0.1.0</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="panel"><h3>Use case</h3><p style="font-size:12px">MPC Midstream support teams bring incidents, Outlook communication, Teams collaboration, and meetings into one operational view.</p><div style="font-size:12px;font-weight:700;margin:14px 0">Application flow</div>'+_flow_html()+'</div>',unsafe_allow_html=True)
    records=service.storage.load_all(); alerts=critical_incidents(records); meetings=[r for r in records if r.record_type=="calendar"]
    values=[("Knowledge records",len(records)),("Connected sources",len({r.source for r in records})),("Critical incidents",len(alerts)),("Meetings",len(meetings)),("Operating mode",settings.app_mode.title())]
    for col,(label,value) in zip(st.columns(5),values): col.metric(label,value)
    ask_tab,meetings_tab,records_tab,notifications_tab,powerbi_tab=st.tabs(["Ask Assistant","Meeting schedule","Knowledge records","Notifications","Power BI data"])
    with ask_tab:
        st.subheader("Ask across enterprise systems")
        caller_groups=st.multiselect("Access groups",["employees","engineering","hr","leadership"],["employees","engineering"])
        question=st.text_area("Question","Summarize the most critical incident, including impact, owner, cause, workaround, and SLA risk.")
        if st.button("Generate grounded answer",type="primary",disabled=not question):
            answer,citations=service.ask(question,caller_groups); st.markdown("#### Grounded answer"); st.write(answer)
            with st.expander(f"Sources ({len(citations)})",expanded=True):
                for record in citations: st.markdown(f"- `{record.id[:12]}` **{record.source}** — {record.title}")
    with meetings_tab:
        st.subheader("Meeting schedule")
        if meetings: st.dataframe([{"Title":r.title,"Owner":r.owner,"Start":r.metadata.get("start",""),"Status":r.status} for r in meetings],use_container_width=True,hide_index=True)
        else: st.info("No meetings indexed. Collect data or configure Outlook Desktop.")
    with records_tab:
        st.subheader("Normalized knowledge records"); source=st.selectbox("Filter source",["All"]+sorted({r.source for r in records})); shown=records if source=="All" else [r for r in records if r.source==source]
        st.dataframe([{"Source":r.source,"Type":r.record_type,"Title":r.title,"Status":r.status,"Priority":r.priority,"Owner":r.owner,"Groups":", ".join(r.allowed_groups)} for r in shown],use_container_width=True,hide_index=True)
    with notifications_tab:
        st.subheader("Critical incident notifications"); st.dataframe([{"Incident":r.source_id,"Title":r.title,"Priority":r.priority,"SLA hours":r.metadata.get("sla_hours"),"Owner":r.owner} for r in alerts],use_container_width=True,hide_index=True)
        if st.button("Create local notification",disabled=not alerts): st.success(f"Notification created: {notify_local(alerts,settings.data_dir)}")
    with powerbi_tab:
        st.subheader("Power BI operational export"); output=Path(settings.data_dir)/"powerbi"/"operations.csv"
        if st.button("Build Power BI CSV"): export_powerbi(records,output)
        if output.exists(): st.download_button("Download operations.csv",output.read_bytes(),"operations.csv","text/csv")


if __name__=="__main__": render_app()
