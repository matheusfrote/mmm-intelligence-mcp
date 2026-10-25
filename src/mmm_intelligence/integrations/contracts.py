"""Backend-neutral boundaries for later adapters. No optional engine is imported.

These Protocols describe extension contracts. The working MCP adapters use the
isolated JSON worker bridge; heavy engine libraries never enter the base runtime.
"""

from dataclasses import dataclass
from datetime import date
from typing import Mapping, Protocol, Sequence

JSONValue = str | int | float | bool | None | list | dict


@dataclass(frozen=True)
class ModelingData:
    dates: Sequence[date]
    target: Sequence[float]
    media: Mapping[str, Sequence[float]]
    controls: Mapping[str, Sequence[float]]
    frequency_days: int
    synthetic: bool
    units: Mapping[str, str]


@dataclass(frozen=True)
class ModelBundle:
    schema_version: str
    backend: str
    backend_version: str
    parameters: Mapping[str, JSONValue]
    diagnostics: Mapping[str, JSONValue]
    provenance: Mapping[str, JSONValue]
    exploratory: bool = True


@dataclass(frozen=True)
class Scenario:
    dates: Sequence[date]
    media: Mapping[str, Sequence[float]]
    controls: Mapping[str, Sequence[float]]
    initial_state: Mapping[str, JSONValue]


class ModelBackend(Protocol):
    def fit(self, data: ModelingData, options: Mapping[str, JSONValue]) -> ModelBundle: ...

    def predict(self, model: ModelBundle, scenario: Scenario) -> Mapping[str, JSONValue]: ...


@dataclass(frozen=True)
class BudgetConstraints:
    total: float
    lower_per_channel: Mapping[str, float]
    upper_per_channel: Mapping[str, float]
    horizon: int


class InvestmentOptimizer(Protocol):
    def optimize(
        self,
        backend: ModelBackend,
        model: ModelBundle,
        scenario: Scenario,
        constraints: BudgetConstraints,
    ) -> Mapping[str, JSONValue]: ...


class DashboardRenderer(Protocol):
    def render(self, model: ModelBundle, scenarios: Sequence[Mapping[str, JSONValue]]) -> bytes: ...


class ReportRenderer(Protocol):
    def render(
        self, model: ModelBundle, scenarios: Sequence[Mapping[str, JSONValue]], locale: str
    ) -> bytes: ...
