from datetime import datetime, timezone, timedelta
from app.models import (
    DataLocationType,
    ObjectiveWeights,
    OptimizeRequest,
    ProvisioningModel,
    RegionMetric,
)
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


def weighted_metrics():
    return [
        RegionMetric(
            region="asia-south1",
            machine_type="n2-standard-4",
            provisioning_model=ProvisioningModel.STANDARD,
            vcpus=4,
            memory_gb=16,
            hourly_cost_usd=0.10,
            carbon_score=650.0,
            reliability_score=0.90,
        ),
        RegionMetric(
            region="europe-west1",
            machine_type="n2-standard-4",
            provisioning_model=ProvisioningModel.STANDARD,
            vcpus=4,
            memory_gb=16,
            hourly_cost_usd=0.20,
            carbon_score=170.0,
            reliability_score=0.99,
        ),
    ]


def weighted_request(weights: ObjectiveWeights) -> OptimizeRequest:
    now = datetime.now(timezone.utc)
    return OptimizeRequest(
        workload_name="weighted_scoring_test",
        data_location_type=DataLocationType.PORTABLE,
        allowed_regions=["asia-south1", "europe-west1"],
        required_vcpus=4,
        required_memory_gb=16,
        estimated_runtime_minutes=60,
        earliest_start_at=now,
        deadline_at=now + timedelta(hours=2),
        spot_allowed=False,
        checkpointable=False,
        minimum_reliability_score=0.80,
        objective_weights=weights,
    )


def test_cost_weight_selects_cheapest_region():
    request = weighted_request(
        ObjectiveWeights(cost=1.0, carbon=0.0, reliability=0.0, sla_buffer=0.0)
    )

    response, _ = optimize(request, weighted_metrics())

    assert response.selected_candidate is not None
    assert response.selected_candidate.region == "asia-south1"
    assert response.selected_candidate.final_score == 1.0


def test_carbon_weight_selects_lower_carbon_region():
    request = weighted_request(
        ObjectiveWeights(cost=0.0, carbon=1.0, reliability=0.0, sla_buffer=0.0)
    )

    response, _ = optimize(request, weighted_metrics())

    assert response.selected_candidate is not None
    assert response.selected_candidate.region == "europe-west1"
    assert response.selected_candidate.final_score == 1.0


def test_cost_premium_guardrail_overrides_carbon_preference():
    request = weighted_request(
        ObjectiveWeights(cost=0.0, carbon=1.0, reliability=0.0, sla_buffer=0.0)
    )
    request.maximum_cost_increase_percent = 5.0

    response, _ = optimize(request, weighted_metrics())

    assert response.selected_candidate is not None
    assert response.selected_candidate.region == "asia-south1"
    europe_candidate = next(
        candidate for candidate in response.candidates
        if candidate.region == "europe-west1"
    )
    assert europe_candidate.is_feasible is False
    assert any(
        reason.startswith("COST_INCREASE_ABOVE_POLICY_THRESHOLD")
        for reason in europe_candidate.rejection_reasons
    )


def test_optimizer_returns_traceable_decision_id():
    request = weighted_request(ObjectiveWeights())

    response, _ = optimize(request, weighted_metrics())

    assert response.decision_id.startswith("dec_")


def test_oversized_machine_does_not_distort_cost_weighted_selection():
    now = datetime.now(timezone.utc)
    request = OptimizeRequest(
        workload_name="right_sizing_test",
        data_location_type=DataLocationType.DATA_LOCAL,
        home_region="asia-south1",
        required_vcpus=4,
        required_memory_gb=16,
        estimated_runtime_minutes=60,
        earliest_start_at=now,
        deadline_at=now + timedelta(hours=2),
        spot_allowed=True,
        checkpointable=True,
        minimum_reliability_score=0.80,
        objective_weights=ObjectiveWeights(
            cost=0.80,
            carbon=0.05,
            reliability=0.10,
            sla_buffer=0.05,
        ),
    )
    metrics = [
        RegionMetric(
            region="asia-south1",
            machine_type="n2-standard-4",
            provisioning_model=ProvisioningModel.STANDARD,
            vcpus=4,
            memory_gb=16,
            hourly_cost_usd=0.20,
            carbon_score=650,
            reliability_score=0.99,
        ),
        RegionMetric(
            region="asia-south1",
            machine_type="n2-standard-4",
            provisioning_model=ProvisioningModel.SPOT,
            vcpus=4,
            memory_gb=16,
            hourly_cost_usd=0.05,
            carbon_score=650,
            reliability_score=0.85,
        ),
        RegionMetric(
            region="asia-south1",
            machine_type="n2-standard-32",
            provisioning_model=ProvisioningModel.STANDARD,
            vcpus=32,
            memory_gb=128,
            hourly_cost_usd=3.20,
            carbon_score=650,
            reliability_score=0.99,
        ),
    ]

    response, _ = optimize(request, metrics)

    assert response.selected_candidate is not None
    assert response.selected_candidate.machine_type == "n2-standard-4"
    assert response.selected_candidate.provisioning_model == ProvisioningModel.SPOT
    oversized = next(
        candidate
        for candidate in response.candidates
        if candidate.machine_type == "n2-standard-32"
    )
    assert oversized.is_feasible is False
    assert any(
        reason.startswith("DOMINATED_RESOURCE_CONFIGURATION")
        for reason in oversized.rejection_reasons
    )
