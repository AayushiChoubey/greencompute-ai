from typing import List, Dict, Any
from fastapi import APIRouter
from app.dependencies import bq_client

router = APIRouter()

@router.get("")
def get_telemetry() -> List[Dict[str, Any]]:
    """Returns top 10 latest executions from BigQuery summary view."""
    queries = [
        "SELECT * FROM `greencompute-ai.greencompute_events.v_execution_summary` ORDER BY last_event_time DESC LIMIT 10",
        "SELECT * FROM `greencompute-ai.greencompute_analytics.v_execution_summary` ORDER BY latest_status_at DESC LIMIT 10"
    ]
    for q in queries:
        try:
            results = bq_client.client.query(q).result()
            rows = [dict(row) for row in results]
            for r in rows:
                for k, v in r.items():
                    if hasattr(v, "isoformat"):
                        r[k] = v.isoformat()
            if rows:
                return rows
        except Exception:
            continue
    return []
