"""Versioned tool input/output contracts; unknown fields are rejected."""

import re
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DISCLAIMER = (
    "Exploratory statistical association, not demonstrated causal attribution. "
    "Synthetic data do not establish market effectiveness. Simulations and any intervals "
    "are conditional on the model and assumptions; no real campaign or budget is changed."
)
IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"
Identifier = Annotated[str, Field(pattern=IDENTIFIER_PATTERN, max_length=64)]
Spend = Annotated[float, Field(ge=0, le=1e9, allow_inf_nan=False, strict=True)]
Number = Annotated[float, Field(ge=-1e12, le=1e12, allow_inf_nan=False, strict=True)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class EmptyRequest(Contract):
    pass


class RetentionRequest(Contract):
    older_than_days: int = Field(default=90, ge=0, le=36500, strict=True)


class GenerateRequest(Contract):
    dataset_id: Identifier | None = None
    periods: int = Field(default=156, ge=52, le=10000, strict=True)
    seed: int = Field(default=42, ge=0, le=2**32 - 1, strict=True)
    start_date: date = date(2023, 1, 2)
    frequency: Literal["daily", "weekly"] = "weekly"


class DatasetRequest(Contract):
    dataset_id: Identifier


class ModelRequest(Contract):
    model_id: Identifier


class DatasetSpec(DatasetRequest):
    media_columns: list[str] = Field(
        default_factory=lambda: ["spend_search", "spend_social", "spend_video"],
        min_length=1,
        max_length=10,
    )
    control_columns: list[str] = Field(
        default_factory=lambda: ["price_index", "promotion"], max_length=10
    )
    target_column: str = "revenue"
    date_column: str = "date"
    test_fraction: float = Field(default=0.2, ge=0.1, le=0.4)
    warmup_periods: int = Field(default=8, ge=0, le=52, strict=True)

    @field_validator("target_column", "date_column")
    @classmethod
    def scalar_column(cls, value):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", value):
            raise ValueError("Invalid column name")
        return value

    @field_validator("media_columns", "control_columns")
    @classmethod
    def columns(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Duplicate columns")
        if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", c) for c in value):
            raise ValueError("Invalid column names")
        if set(value) & {"intercept", "trend_years", "sin_year", "cos_year"}:
            raise ValueError("Column name reserved for internal features")
        return value

    @model_validator(mode="after")
    def disjoint(self):
        columns = [*self.media_columns, *self.control_columns, self.target_column, self.date_column]
        if len(columns) != len(set(columns)):
            raise ValueError("Date, target, media and controls must be distinct")
        return self


class TrainRequest(DatasetSpec):
    model_id: Identifier | None = None
    ridge_alpha: float = Field(default=0.1, gt=0, le=10000)
    adstock_decay: float = Field(default=0.5, ge=0, lt=0.99)
    saturation_multiplier: float = Field(default=1.0, gt=0, le=100)
    bootstrap_samples: int = Field(default=0, ge=0, le=500, strict=True)
    bootstrap_block_size: int = Field(default=4, ge=1, le=26, strict=True)
    bootstrap_seed: int = Field(default=42, ge=0, le=2**32 - 1, strict=True)


class ValidateRequest(DatasetSpec):
    """Uses the same dataset schema and split requirements as training."""


class SimulateRequest(ModelRequest):
    horizon: int = Field(default=13, ge=1, le=104, strict=True)
    total_budget: Spend = Field(description="Total over the entire horizon, in dataset spend units")
    allocation: dict[str, Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]] = Field(
        min_length=1,
        max_length=10,
        description="Exact modeled media names; fractions sum to 1. Spending is flat per period.",
    )
    future_controls: dict[str, list[Number]] | None = Field(
        default=None,
        description="Optional exact control names and horizon-length numeric vectors",
    )

    @model_validator(mode="after")
    def allocation_sum(self):
        if abs(sum(self.allocation.values()) - 1) > 1e-8:
            raise ValueError("Allocation fractions must sum to 1")
        if self.future_controls is not None:
            if len(self.future_controls) > 10:
                raise ValueError("Too many controls")
            if any(len(v) != self.horizon for v in self.future_controls.values()):
                raise ValueError("Each future control must have horizon values")
        return self


class PublicError(Contract):
    code: str
    message: str


class ImportMetadata(Contract):
    dataset_id: Identifier | None = None
    frequency: Literal["daily", "weekly"] = "weekly"
    synthetic: bool
    target_type: Literal["revenue", "non_revenue", "unspecified"] = "unspecified"
    data_context: dict[str, Annotated[str, Field(min_length=1, max_length=1000)]] = Field(
        default_factory=dict,
        max_length=12,
        description="Declared source_reference, extracted_at, timezone, currency, kpi_definition, complete_through, geography, tracking_notes",
    )
    authorization_reference: str = Field(min_length=3, max_length=200)
    units: dict[str, str] = Field(
        default_factory=lambda: {"spend": "declared_currency", "target": "declared_kpi"},
        max_length=10,
    )
    media_columns: list[str] = Field(
        default_factory=lambda: ["spend_search", "spend_social", "spend_video"]
    )
    control_columns: list[str] = Field(default_factory=lambda: ["price_index", "promotion"])
    target_column: str = "revenue"
    date_column: str = "date"

    @model_validator(mode="after")
    def valid_column_spec(self):
        DatasetSpec(
            dataset_id=self.dataset_id or "pending-import",
            media_columns=self.media_columns,
            control_columns=self.control_columns,
            target_column=self.target_column,
            date_column=self.date_column,
        )
        return self


class ImportRequest(ImportMetadata):
    rows: list[dict[str, Any]] = Field(min_length=52, max_length=10000)


class CSVImportRequest(ImportMetadata):
    csv_text: str = Field(min_length=1, max_length=4000000)
    delimiter: Literal[",", ";", "\t"] = ","
    decimal_separator: Literal[".", ","] = "."
    column_mapping: dict[str, str] = Field(default_factory=dict, max_length=22)
    date_format: Literal["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "iso_datetime"] = "%Y-%m-%d"
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    sort_dates: bool = False
    duplicate_policy: Literal["reject", "aggregate"] = "reject"
    source_frequency: Literal["daily", "weekly"] = "weekly"
    aggregate_weekly: bool = False
    reducers: dict[str, Literal["sum", "mean", "last"]] = Field(default_factory=dict, max_length=21)

    @model_validator(mode="after")
    def explicit_policy(self):
        if self.aggregate_weekly:
            if self.source_frequency != "daily" or self.frequency != "weekly":
                raise ValueError("Weekly aggregation requires daily source and weekly output")
        elif self.source_frequency != self.frequency:
            raise ValueError("Frequency conversion requires explicit aggregation")
        numeric = {self.target_column, *self.media_columns, *self.control_columns}
        if self.aggregate_weekly or self.duplicate_policy == "aggregate":
            if set(self.reducers) != numeric:
                raise ValueError("Declare reducers for every numeric column")
            if any(self.reducers[c] != "sum" for c in [self.target_column, *self.media_columns]):
                raise ValueError("KPI and spend aggregation must use sum")
        elif self.reducers:
            raise ValueError("Reducers require aggregation")
        if self.date_format == "iso_datetime" and self.timezone is None:
            raise ValueError("Timestamp normalization requires an explicit reporting timezone")
        if self.date_format != "iso_datetime" and self.timezone is not None:
            raise ValueError("Timezone conversion applies only to timestamps")
        if len(set(self.column_mapping.values())) != len(self.column_mapping):
            raise ValueError("Column mapping must be one to one")
        if any(not k or len(k) > 128 for k in self.column_mapping):
            raise ValueError("Invalid source column name")
        return self


class OptimizeRequest(ModelRequest):
    backend: Literal["ridge", "google_meridian", "pymc_marketing", "meta_robyn"] = "ridge"
    horizon: int = Field(default=13, ge=1, le=104)
    total_budget: Spend
    lower: dict[str, Spend] = Field(default_factory=dict, max_length=10)
    upper: dict[str, Spend] = Field(default_factory=dict, max_length=10)
    future_controls: dict[str, list[Number]] | None = None


class AnalyzeRequest(ModelRequest):
    decays: list[float] = Field(default_factory=lambda: [0.2, 0.5, 0.8], min_length=1, max_length=5)
    multipliers: list[float] = Field(
        default_factory=lambda: [0.5, 1.0, 2.0], min_length=1, max_length=5
    )


class TuneRequest(TrainRequest):
    decays: list[Annotated[float, Field(ge=0, lt=0.99)]] = Field(
        default_factory=lambda: [0.2, 0.5, 0.8], min_length=1, max_length=5
    )
    multipliers: list[Annotated[float, Field(gt=0, le=100)]] = Field(
        default_factory=lambda: [0.5, 1.0, 2.0], min_length=1, max_length=5
    )


class RenderRequest(ModelRequest):
    artifact_id: Identifier | None = None


class MonteCarloProtocol(Contract):
    replications: int = Field(default=20, ge=2, le=1000, strict=True)
    periods: int = Field(default=156, ge=52, le=520, strict=True)
    seed: int = Field(default=2026, ge=0, le=2**31 - 1, strict=True)
    bootstrap_samples: int = Field(default=40, ge=20, le=500, strict=True)
    minimum_replications_for_assessment: int = Field(default=100, ge=30, le=1000, strict=True)
    coverage_tolerance: float = Field(default=0.05, ge=0, le=0.2)
    max_absolute_bias: float | None = Field(default=None, ge=0, le=1e12)
    max_rmse: float | None = Field(default=None, ge=0, le=1e12)
    scenarios: list[
        Literal[
            "well_specified",
            "null_effect",
            "collinear",
            "omitted_confounder",
            "tracking_break",
            "heavy_tailed",
            "misspecified_adstock",
            "weak_signal",
            "missing_target",
            "constant_spend",
        ]
    ] = Field(
        default=["well_specified", "null_effect", "omitted_confounder"],
        min_length=1,
        max_length=10,
    )


class ScientificCalibration(Contract):
    experiment_result_id: Identifier
    channel: str = Field(min_length=1, max_length=64)
    treatment_spend: Spend
    control_spend: Spend
    horizon: int = Field(default=4, ge=1, le=52, strict=True)
    initial_adstock: Spend = 0
    aggregate_multiplier: float = Field(gt=0, le=1e9, allow_inf_nan=False)
    outcome_unit: str = Field(min_length=1, max_length=100)
    transformation_justification: str = Field(min_length=10, max_length=1000)
    matching_population: bool
    matching_measurement_window: bool


class ScientificProtocol(Contract):
    policy_version: Literal["scientific-v1"] = "scientific-v1"
    refit: bool = True
    collect_native: bool = True
    seeds: list[Annotated[int, Field(ge=0, le=2**31 - 1, strict=True)]] = Field(
        default_factory=lambda: [17, 29], min_length=2, max_length=5
    )
    regularization: list[Annotated[float, Field(gt=0, le=1e6)]] = Field(
        default_factory=lambda: [0.01, 0.1, 1.0], min_length=2, max_length=5
    )
    max_rhat: float = Field(default=1.01, gt=1, le=1.05)
    min_ess_per_chain: int = Field(default=100, ge=100, le=10000, strict=True)
    min_draws: int = Field(default=1000, ge=400, le=2000, strict=True)
    max_mcse_sd_ratio: float = Field(default=0.05, gt=0, le=0.1)
    max_relative_spread: float = Field(default=0.5, gt=0, le=2)
    experiment_result_ids: list[Identifier] = Field(default_factory=list, max_length=10)
    placebo_result_ids: list[Identifier] = Field(default_factory=list, max_length=10)
    negative_control_result_ids: list[Identifier] = Field(default_factory=list, max_length=10)
    equivalence_margin: float | None = Field(default=None, gt=0, le=1e12)
    assumptions: dict[
        Literal[
            "random_assignment",
            "no_interference",
            "no_unmeasured_confounding",
            "no_post_treatment_controls",
            "positivity",
            "measurement_consistency",
            "prespecified_analysis",
            "complete_followup",
        ],
        Literal["supported", "violated", "unknown"],
    ] = Field(default_factory=dict)
    review_reference: str | None = Field(default=None, min_length=1, max_length=500)
    confounding_bias_grid: list[Number] = Field(default_factory=list, max_length=20)
    monte_carlo: MonteCarloProtocol | None = None
    calibration: ScientificCalibration | None = None

    @model_validator(mode="after")
    def distinct_scientific_inputs(self):
        ids = [
            *self.experiment_result_ids,
            *self.placebo_result_ids,
            *self.negative_control_result_ids,
        ]
        if len(set(ids)) != len(ids) or len(set(self.seeds)) != len(self.seeds):
            raise ValueError("Use independent seeds and disjoint evidence sets")
        if self.calibration is not None and self.calibration.experiment_result_id in ids:
            raise ValueError(
                "Calibration evidence must be independent from validation/falsification evidence"
            )
        if len(set(self.regularization)) != len(self.regularization):
            raise ValueError("Use distinct regularization settings")
        return self


class AuditRequest(ModelRequest):
    backend: Literal["ridge", "google_meridian", "pymc_marketing", "meta_robyn"] = "ridge"
    scientific: ScientificProtocol | None = None

    @model_validator(mode="after")
    def matched_monte_carlo_engine(self):
        if (
            self.backend != "ridge"
            and self.scientific is not None
            and self.scientific.monte_carlo is not None
        ):
            raise ValueError("The matched-effect Monte Carlo suite currently evaluates Ridge only")
        return self

    folds: int = Field(default=3, ge=2, le=5, strict=True)
    max_allocation_spread: float = Field(
        default=0.2,
        ge=0,
        le=1,
        description="Operational warning screen in allocation-share units, not a universal statistical validity threshold",
    )
    decays: list[Annotated[float, Field(ge=0, lt=0.99)]] = Field(
        default_factory=lambda: [0.2, 0.5, 0.8], min_length=1, max_length=5
    )
    multipliers: list[Annotated[float, Field(gt=0, le=100)]] = Field(
        default_factory=lambda: [0.5, 1.0, 2.0], min_length=1, max_length=5
    )


class CalibrationRequest(ModelRequest):
    channel: str = Field(min_length=1, max_length=64)
    treatment_spend: Spend
    control_spend: Spend
    horizon: int = Field(default=4, ge=1, le=52)
    initial_adstock: Spend = 0
    lift_mean: Number
    lift_sd: float = Field(gt=0, le=1e9)
    experiment_id: Identifier
    synthetic: bool


class BackendRequest(DatasetSpec):
    backend: Literal["google_meridian", "pymc_marketing", "meta_robyn"]
    model_id: Identifier | None = None
    draws: int = Field(default=100, ge=20, le=2000)
    tune: int = Field(default=100, ge=20, le=2000)
    chains: int = Field(default=2, ge=2, le=4)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    robyn_trials: int | None = Field(default=None, ge=1, le=10, strict=True)
    robyn_iterations: int | None = Field(default=None, ge=200, le=10000, strict=True)

    @model_validator(mode="after")
    def supported_native_split(self):
        if self.backend != "meta_robyn" and (
            self.robyn_trials is not None or self.robyn_iterations is not None
        ):
            raise ValueError("Robyn search controls apply only to Meta Robyn")
        if self.backend == "meta_robyn" and self.test_fraction != 0.2:
            raise ValueError(
                "Meta Robyn adapter requires test_fraction=0.2 (native 60/20/20 split)"
            )
        return self


class BackendPredictRequest(ModelRequest):
    media_multiplier: dict[str, Annotated[float, Field(ge=0, le=10)]] = Field(
        default_factory=dict, max_length=10
    )


class ToolResponse(Contract):
    schema_version: str = "1.0"
    ok: bool
    exploratory: bool = True
    disclaimer: str = DISCLAIMER
    data: dict[str, Any] | None = None
    error: PublicError | None = None
    warnings: list[str] = Field(default_factory=list)


BackendName = Literal["ridge", "google_meridian", "pymc_marketing", "meta_robyn"]


class CapabilityRequest(Contract):
    backend: BackendName


class AnalysisRequest(ModelRequest):
    backend: BackendName = "ridge"
    scientific_report_id: Identifier | None = None
    max_rhat: float = Field(default=1.01, gt=1, le=1.2)
    min_ess_per_chain: int = Field(default=100, ge=10, le=10000, strict=True)


class ExportRequest(AnalysisRequest):
    format: Literal["json", "csv", "markdown"] = "json"


class CompareRequest(Contract):
    models: list[AnalysisRequest] = Field(min_length=2, max_length=5)
    window_policy: Literal["exact", "intersection"] = "exact"

    @model_validator(mode="after")
    def distinct(self):
        if len({(m.backend, m.model_id) for m in self.models}) != len(self.models):
            raise ValueError("Compare distinct models")
        return self


class ForecastRequest(ModelRequest):
    backend: BackendName = "ridge"
    media_plan: dict[str, list[Spend]] = Field(min_length=1, max_length=10)
    future_controls: dict[str, list[Number]] = Field(max_length=10)

    @model_validator(mode="after")
    def same_horizon(self):
        lengths = {len(v) for v in [*self.media_plan.values(), *self.future_controls.values()]}
        if len(lengths) != 1 or not 1 <= next(iter(lengths)) <= 104:
            raise ValueError("Every series must have the same horizon of 1..104 periods")
        if sum(sum(v) for v in self.media_plan.values()) > 1e9:
            raise ValueError("Total plan spend exceeds 1e9")
        return self
