"""Uvicorn entrypoint."""

from __future__ import annotations

from app.app import TicketsPilotApplication
from app.config import build_settings


def create_application() -> TicketsPilotApplication:
    settings = build_settings()
    return TicketsPilotApplication(settings)


application = create_application()
app = application.app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=application.settings.DEBUG,
    )
