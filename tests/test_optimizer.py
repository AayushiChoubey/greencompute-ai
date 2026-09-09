from datetime import datetime, timezone, timedelta
from app.models import OptimizeRequest, RegionMetric, ProvisioningModel, DataLocationType
from app.optimizer import optimize

def sample_metrics():
    return [
        RegionMetric(
            region="asia-south1",
            machine_type="n2-standard-8",
            provisioning_model=ProvisioningModel.SPOT,
            vcpus=8,
            memory_gb=32,
            hourly_cost_usd=0.16,
            carbon_score=650.0,
            reliability_score=0.85,
        ),
        RegionMetric(
            region="europe-west1",
            machine_type="n2-standard-8",
            provisioning_model=ProvisioningModel.STANDARD,
            vcpus=8,
            memory_gb=32,
            hourly_cost_usd=0.35,
            carbon_score=170.0,
            reliability_score=0.99,
        )
    ]

def test_data_local_blocks_cross_region():
    now = datetime.now(timezone.utc)
    req = OptimizeRequest(
        workload_name="etl_test",
        data_location_type=DataLocationType.DATA_LOCAL,
        home_region="asia-south1",
        required_vcpus=8,
        required_memory_gb=32,
        estimated_runtime_minutes=60,
        earliest_start_at=now,
        deadline_at=now + timedelta(hours=5),
        spot_allowed=True,
        checkpointable=True,
        minimum_reliability_score=0.80
    )
    resp, _ = optimize(req, sample_metrics())
    assert resp.selected_candidate is not None
    assert resp.selected_candidate.region == "asia-south1"

def test_spot_rejected_if_not_checkpointable():
    now = datetime.now(timezone.utc)
    req = OptimizeRequest(
        workload_name="non_checkpointable_test",
        data_location_type=DataLocationType.DATA_LOCAL,
        home_region="asia-south1",
        required_vcpus=8,
        required_memory_gb=32,
        estimated_runtime_minutes=60,
        earliest_start_at=now,
        deadline_at=now + timedelta(hours=5),
        spot_allowed=True,
        checkpointable=False
    )
    resp, _ = optimize(req, sample_metrics())
    assert resp.feasible_candidate_count == 0
