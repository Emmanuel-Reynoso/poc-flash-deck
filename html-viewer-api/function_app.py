"""Azure Functions entry point (Python v2 programming model).

Hosts the FastAPI app (app/main.py) through the ASGI adapter and adds the
scheduled jobs. Not used for local development: run `uvicorn app.main:app`.
"""

import azure.functions as func

from app.core.container import get_services
from app.main import app as fastapi_app

app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)


@app.timer_trigger(schedule="0 0 3 * * *", arg_name="timer", run_on_startup=False, use_monitor=True)
def purge_stale_uploads(timer: func.TimerRequest) -> None:
    """Removes upload tickets that were never completed (and any orphan blob)."""
    get_services().files.purge_stale_pending()
