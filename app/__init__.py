from google.adk.apps import App
from .agent import safestaff_workflow

app = App(
    name="safestaff",
    root_agent=safestaff_workflow,
)
