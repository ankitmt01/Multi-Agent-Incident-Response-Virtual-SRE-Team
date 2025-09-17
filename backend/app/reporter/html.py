# backend/app/reporter/html.py
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..models import PipelineResult, Incident

# templates directory: backend/app/templates/report.html
_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

def render_report(incident: Incident, result: PipelineResult) -> str:
    """Render the incident report to HTML using templates/report.html."""
    tpl = _env.get_template("report.html")
    # Pass the same keys your template expects; add more as needed
    return tpl.render(incident=incident, result=result)
