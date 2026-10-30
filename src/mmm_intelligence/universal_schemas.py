"""Bounded, explicit contracts for supplied files and learning records."""

from datetime import date
from typing import Literal

from pydantic import Field

from .schemas import Contract, Identifier


class SourceRequest(Contract):
    content_base64: str = Field(max_length=140000000)
    format: Literal["csv", "tsv", "json", "jsonl", "xlsx", "xls", "parquet", "xml"]
    xml_record: str | None = Field(default=None, max_length=128)
    xml_fields: dict[str, str] = Field(default_factory=dict, max_length=80)
    xml_max_depth: int = Field(default=24, ge=1, le=64)
    xml_schema_base64: str | None = Field(default=None, max_length=87384)
    origin: str = Field(min_length=1, max_length=300)
    synthetic: bool = False
    authorization_reference: str | None = Field(default=None, max_length=300)
    confirm: bool = False
    delimiter: str | None = Field(default=None, min_length=1, max_length=1)
    encoding: Literal["utf-8-sig", "utf-8", "cp1252", "latin-1"] = "utf-8-sig"
    sheet: str | None = Field(default=None, max_length=128)
    header_row: int = Field(default=1, ge=1, le=100)


class ArtifactRequest(Contract):
    artifact_id: Identifier


class JoinRequest(Contract):
    context: dict[str, str] = Field(default_factory=dict, max_length=30)
    left_id: Identifier
    right_id: Identifier
    keys: dict[str, str] = Field(min_length=1, max_length=10)
    how: Literal["inner", "left", "right", "full"] = "inner"
    cardinality: Literal["1:1", "1:m", "m:1", "m:m"] = "1:1"
    confirm: bool = False
    unmatched: Literal["allow", "error"] = "allow"
    frequency: Literal["original", "daily", "weekly"] = "original"
    left_aggregations: dict[str, Literal["sum", "mean"]] = Field(
        default_factory=dict, max_length=80
    )
    right_aggregations: dict[str, Literal["sum", "mean"]] = Field(
        default_factory=dict, max_length=80
    )
    right_suffix: str = Field(
        default="_right", min_length=1, max_length=20, pattern=r"^_[a-z0-9_]+$"
    )


class ProfileRequest(Contract):
    expected_units: dict[str, str] = Field(default_factory=dict, max_length=80)
    name: Identifier
    version: str = Field(min_length=1, max_length=30)
    family: str = Field(min_length=1, max_length=80)
    required: list[str] = Field(min_length=1, max_length=80)
    optional: list[str] = Field(default_factory=list, max_length=80)
    nonadditive: list[str] = Field(
        default_factory=lambda: [
            "reach",
            "users",
            "rating",
            "share",
            "frequency",
            "ctr",
            "cpc",
            "cpa",
        ],
        max_length=80,
    )


class MappingRequest(Contract):
    source_id: Identifier
    profile: Identifier
    mapping: dict[str, str] = Field(min_length=1, max_length=80)
    units: dict[str, str] = Field(default_factory=dict, max_length=80)
    dimensions: dict[str, str] = Field(default_factory=dict, max_length=30)
    date_format: str = Field(default="%Y-%m-%d", max_length=40)
    timezone: str = Field(default="UTC", max_length=80)
    frequency_days: int = Field(default=7, ge=1, le=366)


class CrossRequest(Contract):
    artifact_ids: list[Identifier] = Field(min_length=1, max_length=30)


class BuildRequest(CrossRequest):
    frequency: Literal["daily", "weekly"] = "weekly"
    aggregations: dict[str, Literal["sum", "weighted_mean", "ratio"]] = Field(
        default_factory=dict, max_length=80
    )
    weights: dict[str, str] = Field(default_factory=dict, max_length=80)
    ratios: dict[str, list[str]] = Field(default_factory=dict, max_length=80)


class EligibilityRequest(ArtifactRequest):
    target_type: Literal["revenue", "non_revenue", "unspecified"] = "unspecified"
    kpi: str = Field(min_length=1, max_length=80)
    media: list[str] = Field(min_length=1, max_length=30)
    controls: list[str] = Field(default_factory=list, max_length=30)
    backend: Literal["ridge", "google_meridian", "pymc_marketing", "meta_robyn"] = "ridge"


class PreparationRequest(EligibilityRequest):
    target_type: Literal["revenue", "non_revenue"]
    currency: Literal["BRL", "USD", "EUR", "GBP"]


class GrowthAnalysisRequest(ArtifactRequest):
    lag_pairs: list[dict[Literal["spend", "outcome"], str]] = Field(
        default_factory=list, max_length=10
    )
    max_lag: int = Field(default=4, ge=0, le=26)
    metrics: list[str] = Field(min_length=1, max_length=20)
    group_by: list[str] = Field(default_factory=list, max_length=4)
    rolling_window: int = Field(default=4, ge=2, le=104)
    minimum_group_size: int = Field(default=5, ge=5, le=1000)


class CohortRequest(ArtifactRequest):
    population_column: str | None = Field(default=None, min_length=1, max_length=128)
    population_value: str | None = Field(default=None, min_length=1, max_length=300)
    unit_column: str = Field(min_length=1, max_length=128)
    event_column: str = Field(min_length=1, max_length=128)
    date_column: str = Field(default="date", max_length=128)
    entry_event: str = Field(min_length=1, max_length=128)
    return_event: str = Field(min_length=1, max_length=128)
    as_of: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    horizon: int = Field(default=12, ge=1, le=104)
    frequency_days: int = Field(default=7, ge=1, le=31)
    group_by: list[str] = Field(default_factory=list, max_length=4)
    minimum_group_size: int = Field(default=5, ge=5, le=1000)
    cumulative: bool = False


class GuardrailSpec(Contract):
    outcome_type: Literal["binary", "continuous"]
    direction: Literal["increase", "decrease"]
    max_adverse_change: float = Field(ge=0, allow_inf_nan=False)


class ExperimentPlanRequest(Contract):
    hypothesis: str | None = Field(default=None, min_length=1, max_length=2000)
    analysis_plan: str | None = Field(default=None, min_length=1, max_length=2000)
    randomization_unit: str | None = Field(default=None, min_length=1, max_length=128)
    duration_days: int | None = Field(default=None, ge=1, le=3650)
    conversion_window_days: int | None = Field(default=None, ge=0, le=3650)
    observation_start: date | None = None
    observation_end: date | None = None
    date_column: str | None = Field(default=None, min_length=1, max_length=128)
    population_column: str | None = Field(default=None, min_length=1, max_length=128)
    population_value: str | None = Field(default=None, min_length=1, max_length=300)
    exclusion_criteria: str | None = Field(default=None, min_length=1, max_length=2000)
    operational_constraints: str | None = Field(default=None, min_length=1, max_length=2000)
    guardrail_specs: dict[str, GuardrailSpec] = Field(default_factory=dict, max_length=20)
    method: Literal["randomized", "geographic", "observational", "before_after", "mmm_calibration"]
    outcome_type: Literal["binary", "continuous"]
    kpi: str = Field(min_length=1, max_length=128)
    unit_column: str = Field(min_length=1, max_length=128)
    group_column: str = Field(min_length=1, max_length=128)
    treatment: str = Field(min_length=1, max_length=100)
    control: str = Field(min_length=1, max_length=100)
    baseline: float = Field(allow_inf_nan=False)
    standard_deviation: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    minimum_effect: float = Field(gt=0, allow_inf_nan=False)
    power: float = Field(default=0.8, gt=0.5, lt=1)
    alpha: float = Field(default=0.05, gt=0, lt=0.5)
    comparison_family_size: int = Field(default=1, ge=1, le=1000)
    expected_treatment_fraction: float = Field(default=0.5, gt=0, lt=1)
    population: str = Field(min_length=1, max_length=1000)
    measurement_window: str = Field(min_length=1, max_length=100)
    stop_rule: str = Field(min_length=1, max_length=1000)
    guardrails: list[str] = Field(min_length=1, max_length=20)
    cost_column: str | None = Field(default=None, max_length=128)


class ExperimentAnalysisRequest(ArtifactRequest):
    plan_id: Identifier


class DecisionRequest(Contract):
    diagnostic_id: Identifier
    problem: str = Field(min_length=1, max_length=2000)
    hypothesis: str = Field(min_length=1, max_length=2000)
    action: str = Field(min_length=1, max_length=2000)
    kpi: str = Field(min_length=1, max_length=80)
    guardrails: list[str] = Field(min_length=1, max_length=30)
    baseline: str = Field(min_length=1, max_length=100)
    horizon: str = Field(min_length=1, max_length=100)
    method: Literal["randomized", "geographic", "observational", "before_after", "mmm_calibration"]
    risks: list[str] = Field(min_length=1, max_length=30)


class TransitionRequest(ArtifactRequest):
    state: Literal["approved", "rejected", "planned", "evaluated", "learned"]
    actor: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=2000)
    plan: dict[str, str] | None = Field(default=None, max_length=20)
    results_id: Identifier | None = None
