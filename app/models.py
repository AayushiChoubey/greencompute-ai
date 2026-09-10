"""Typed API contracts for the GreenCompute optimizer."""

from datetime import datetime
from enum import StrEnum
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator


class ProvisioningModel(StrEnum):
    STANDARD = "STANDARD"
    SPOT = "SPOT"


class StartMode(StrEnum):
    EXACT = "EXACT"
    FLEXIBLE = "FLEXIBLE"


class DataLocationType(StrEnum):
    DATA_LOCAL = "DATA_LOCAL"
    REPLICATED = "REPLICATED"
    PORTABLE = "PORTABLE"


class ObjectiveWeights(BaseModel):
    cost: float = Field(default=0.45, ge=0, le=1)
    carbon: float = Field(default=0.25, ge=0, le=1)
    reliability: float = Field(default=0.25, ge=0, le=1)
    sla_buffer: float = Field(default=0.05, ge=0, le=1)

    @model_validator(mode="after")
    def weights_must_total_one(self) -> "ObjectiveWeights":
        total = self.cost + self.carbon + self.reliability + self.sla_buffer
        if abs(total - 1.0) > 0.00001:
            raise ValueError("Objective weights must add up to 1.0")
        return self


class RegionMetric(BaseModel):
    region: str = Field(min_length=1)
    machine_type: str = Field(min_length=1)
    provisioning_model: ProvisioningModel
    vcpus: int = Field(gt=0)
    memory_gb: float = Field(gt=0)
    hourly_cost_usd: float = Field(ge=0)
    carbon_score: float = Field(ge=0)
    reliability_score: float = Field(ge=0, le=1)
    capacity_available: bool = True
    carbon_is_synthetic: bool = True


class OptimizeRequest(BaseModel):
    workload_name: str = Field(min_length=1, max_length=200)
    workload_id: str = Field(default="wl_default")
    policy_version_id: str = Field(default="pol_v1_default")
    estimated_runtime_minutes: int = Field(gt=0)
    earliest_start_at: datetime
    deadline_at: datetime
    start_mode: StartMode = StartMode.FLEXIBLE
    data_location_type: DataLocationType = DataLocationType.PORTABLE
    home_region: str = "asia-south1"
    approved_replica_regions: List[str] = Field(default_factory=list)
    allowed_regions: List[str] = Field(default_factory=list)
    required_vcpus: int = Field(gt=0)
    required_memory_gb: float = Field(gt=0)
    spot_allowed: bool = False
    checkpointable: bool = False
    minimum_reliability_score: float = Field(default=0.85, ge=0, le=1)
    minimum_sla_buffer_minutes: int = Field(default=30, ge=0)
    maximum_cost_increase_percent: Optional[float] = Field(default=None, ge=0)
    objective_weights: ObjectiveWeights = Field(default_factory=ObjectiveWeights)
    region_metrics: List[RegionMetric] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_time_window(self) -> "OptimizeRequest":
        if self.earliest_start_at.tzinfo is None or self.deadline_at.tzinfo is None:
            raise ValueError("earliest_start_at and deadline_at must include a timezone")
        if self.deadline_at <= self.earliest_start_at:
            raise ValueError("deadline_at must be later than earliest_start_at")
        return self


class Candidate(BaseModel):
    candidate_id: str
    region: str
    machine_type: str
    provisioning_model: ProvisioningModel
    scheduled_start_at: datetime
    predicted_finish_at: datetime
    estimated_compute_cost_usd: float
    carbon_score: float
    reliability_score: float
    sla_buffer_minutes: int
    is_feasible: bool
    rejection_reasons: List[str]
    final_score: Optional[float] = None


class OptimizeResponse(BaseModel):
    optimization_run_id: str
    decision_id: str
    workload_name: str
    start_mode: StartMode
    candidate_count: int
    feasible_candidate_count: int
    selected_candidate: Optional[Candidate]
    message: str
    transparency_notice: str
    candidates: List[Candidate]
