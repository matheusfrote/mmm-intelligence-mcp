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


class ImportRequest(Contract):
    dataset_id: Identifier | None = None
    rows: list[dict[str, Any]] = Field(min_length=52, max_length=10000)
    frequency: Literal["daily", "weekly"] = "weekly"
    synthetic: bool
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


class OptimizeRequest(ModelRequest):
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

    @model_validator(mode="after")
    def supported_native_split(self):
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
