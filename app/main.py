"""HTTP API entrypoint for GreenCompute."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routers.views import router as views_router
from app.api.routers.optimization import router as optimization_router
from app.api.routers.execution import router as execution_router
from app.api.routers.workflows import router as workflows_router
from app.api.routers.telemetry import router as telemetry_router

app = FastAPI(
    title="GreenCompute AI API",
    version="0.5.0",
    description="Deterministic optimization, Batch dispatch, Cloud Workflows orchestration, and Gemini explainability.",
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/health")
def health_check():
    """Standard health check endpoint."""
    return {"status": "healthy", "version": "0.5.0"}

# Include modular routers
app.include_router(views_router)
app.include_router(optimization_router, prefix="/api/v1", tags=["Optimization"])
app.include_router(execution_router, prefix="/api/v1", tags=["Execution"])
app.include_router(workflows_router, prefix="/api/v1/workflows", tags=["Workflows"])
app.include_router(telemetry_router, prefix="/api/v1/telemetry", tags=["Telemetry"])
