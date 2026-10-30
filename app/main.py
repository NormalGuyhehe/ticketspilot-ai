"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import admin, metrics, tickets, webhooks


class TicketsPilotApplication:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-powered support ticket automation system",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
    app.include_router(tickets.router, prefix="/tickets", tags=["Tickets"])
    app.include_router(admin.router, prefix="/admin", tags=["Admin"])
    app.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])


    @app.get("/health", tags=["System"])
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": settings.APP_NAME}
