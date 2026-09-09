"""HTTP API entrypoint for GreenCompute."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.routers import views, optimization, execution, workflows, telemetry

app = FastAPI(
    title="GreenCompute AI API",
    version="0.5.0",
    description="Deterministic optimization, Batch dispatch, Cloud Workflows orchestration, and Gemini explainability.",
)

# Mount static assets
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Register Routers without duplicate nested prefixes
app.include_router(views.router, tags=["Views"])
app.include_router(optimization.router)
app.include_router(execution.router, prefix="/api/v1", tags=["Execution"])
app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["Workflows"])
app.include_router(telemetry.router, prefix="/api/v1/telemetry", tags=["Telemetry"])
