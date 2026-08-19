from __future__ import annotations

from pathlib import Path
import typer

from .analytics import export_powerbi
from .config import Settings
from .notifications import critical_incidents, notify_email, notify_local, notify_teams
from .service import EnterpriseAssistant

app = typer.Typer(help="Enterprise Knowledge Assistant")


@app.command("config-check")
def config_check():
    settings = Settings.from_env()
    missing = settings.missing_azure() if settings.app_mode == "azure" else []
    if missing: raise typer.BadParameter("Missing Azure settings: " + ", ".join(missing))
    typer.echo(f"Configuration is valid for {settings.app_mode} mode.")


@app.command()
def ingest(desktop: bool = typer.Option(False, help="Also read Outlook Desktop calendar")):
    records = EnterpriseAssistant(Settings.from_env()).ingest(include_desktop=desktop)
    typer.echo(f"Ingested {len(records)} records.")


@app.command()
def demo():
    settings = Settings.from_env()
    if settings.app_mode != "local": raise typer.BadParameter("eka demo requires APP_MODE=local")
    service = EnterpriseAssistant(settings); records = service.ingest(include_demo=True)
    answer, _ = service.ask("What critical incident needs attention?", ["employees", "engineering"])
    typer.echo(f"Ingested {len(records)} deterministic demo records.\n{answer}")


@app.command()
def ask(question: str, groups: str = typer.Option("employees", help="Comma-separated caller groups")):
    answer, _ = EnterpriseAssistant(Settings.from_env()).ask(question, [x.strip() for x in groups.split(",")])
    typer.echo(answer)


@app.command()
def notify(channel: str = typer.Option("local", help="local, email, or teams")):
    settings = Settings.from_env(); records = critical_incidents(EnterpriseAssistant(settings).storage.load_all())
    if channel == "local": result = notify_local(records, settings.data_dir); typer.echo(result)
    elif channel == "email": notify_email(records, settings); typer.echo("Email sent.")
    elif channel == "teams": notify_teams(records, settings); typer.echo("Teams card sent.")
    else: raise typer.BadParameter("channel must be local, email, or teams")


@app.command("export-powerbi")
def export_powerbi_command(output: str = "data/powerbi/operations.csv"):
    service = EnterpriseAssistant(Settings.from_env())
    typer.echo(export_powerbi(service.storage.load_all(), Path(output)))
