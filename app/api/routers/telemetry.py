import logging
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException
from app.dependencies import bq_client

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("")
def get_telemetry() -> List[Dict[str, Any]]:
    """Returns top 10 latest executions from BigQuery summary view."""
    query = """
        SELECT *
        FROM `greencompute-ai.greencompute_analytics.v_execution_summary`
        ORDER BY latest_status_at DESC
        LIMIT 10
    """
    try:
        results = bq_client.client.query(query).result()
        rows = [dict(row) for row in results]
        for row in rows:
            for key, value in row.items():
                if hasattr(value, "isoformat"):
                    row[key] = value.isoformat()
        return rows
    except Exception as exc:
        # Returning an empty list here made a broken BigQuery view look like
        # a healthy system with no executions, which hid the real problem.
        logger.exception("Unable to load execution telemetry from BigQuery")
        raise HTTPException(
            status_code=503,
            detail="Execution telemetry is temporarily unavailable.",
        ) from exc
