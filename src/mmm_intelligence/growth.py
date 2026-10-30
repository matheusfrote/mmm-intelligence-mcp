"""Supplied files, versioned semantic mappings and immutable decision snapshots."""

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .errors import MMMError
from .ingestion import reporting_timezone
from .media_validation import PROFILES, eligibility, validate_media
from .schemas import Contract, EmptyRequest
from .supplied_files import parse_file
from .universal_schemas import (
    ArtifactRequest,
    BuildRequest,
    CohortRequest,
    CrossRequest,
    DecisionRequest,
    EligibilityRequest,
    ExperimentAnalysisRequest,
    ExperimentPlanRequest,
    GrowthAnalysisRequest,
    JoinRequest,
    MappingRequest,
    PreparationRequest,
    ProfileRequest,
    SourceRequest,
    TransitionRequest,
)

REQUESTS: dict[str, type[Contract]] = {
    "analyze_growth": GrowthAnalysisRequest,
    "analyze_cohorts": CohortRequest,
    "plan_experiment": ExperimentPlanRequest,
    "analyze_experiment": ExperimentAnalysisRequest,
    "prepare_mmm_dataset": PreparationRequest,
    "join_datasets": JoinRequest,
    "preview_dataset": SourceRequest,
    "import_source": SourceRequest,
    "map_dataset_schema": MappingRequest,
    "register_media_profile": ProfileRequest,
    "list_media_profiles": EmptyRequest,
    "validate_media_dataset": ArtifactRequest,
    "validate_crossmedia_dataset": CrossRequest,
    "build_growth_dataset": BuildRequest,
    "check_mmm_eligibility": EligibilityRequest,
    "create_growth_diagnostic": ArtifactRequest,
    "create_growth_decision": DecisionRequest,
    "transition_growth_decision": TransitionRequest,
    "get_growth_artifact": ArtifactRequest,
}
READ_TOOLS = {
    "preview_dataset",
    "list_media_profiles",
    "validate_media_dataset",
    "validate_crossmedia_dataset",
    "check_mmm_eligibility",
    "get_growth_artifact",
}
DESCRIPTIONS = {
    name: f"{name.replace('_', ' ').capitalize()}. Supplied files only; explicit semantics, tenant authorization and exploratory results. No live campaign actions."
    for name in REQUESTS
}


class GrowthMixin:
    def analyze_growth(self, request):
        from .growth_analytics import temporal_analysis

        artifact = self._growth_read(request.artifact_id, {"normalized"})
        quality = validate_media(artifact)
        if quality["dataset_applicability"]["state"] != "applicable" or any(
            quality["field_applicability"].get(metric, {}).get("state") != "applicable"
            for metric in request.metrics
        ):
            raise MMMError(
                "ANALYSIS_APPLICABILITY",
                "Select a profile and metrics applicable to the declared dataset before analysis",
            )
        if quality["errors"] or set(request.metrics) & set(quality["unknown_units"]):
            raise MMMError(
                "ANALYSIS_QUALITY",
                "Resolve invalid observations and declare selected metric units before analysis",
            )
        result = temporal_analysis(artifact, request)
        result["input_quality"] = quality
        return self._growth_save("growth_analysis", result)

    def analyze_cohorts(self, request):
        from .growth_analytics import cohort_analysis

        artifact = self._growth_read(request.artifact_id, {"source"})
        return self._growth_save("cohort_analysis", cohort_analysis(artifact, request))

    def plan_experiment(self, request):
        from .experiments import plan_experiment

        return self._growth_save("experiment_plan", plan_experiment(request))

    def analyze_experiment(self, request):
        from .experiments import analyze_experiment

        artifact = self._growth_read(request.artifact_id, {"source"})
        plan = self._growth_read(request.plan_id, {"experiment_plan"})
        return self._growth_save("experiment_result", analyze_experiment(artifact, plan))

    def prepare_mmm_dataset(self, request):
        from .materialization import materialize

        artifact = self._growth_read(request.artifact_id, {"normalized"})
        payload, training = materialize(artifact, request, self.settings.max_rows)
        dataset_id = "prepared-" + uuid4().hex
        training["dataset_id"] = dataset_id
        checksum = self.store.write("datasets", dataset_id, payload)
        return {
            "dataset_id": dataset_id,
            "sha256": checksum,
            "training_tool": "train_mmm" if request.backend == "ridge" else "train_backend",
            "training_request": training,
            "source_ids": payload["source_ids"],
            "warnings": payload["preparation"]["warnings"],
        }

    def join_datasets(self, request):
        from .joins import combine

        left = self._growth_read(request.left_id, {"normalized"})
        right = self._growth_read(request.right_id, {"normalized"})
        result = combine(left, right, request, self.settings.max_rows)
        return self._growth_save("normalized", result) if request.confirm else result

    def _growth_save(self, kind, payload, artifact_id=None):
        artifact_id = artifact_id or kind + "-" + uuid4().hex
        record = {
            **payload,
            "artifact_type": kind,
            "artifact_id": artifact_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.store.write("reports", artifact_id, record)
        return record

    def _growth_read(self, artifact_id, kinds=None):
        value = self.store.read("reports", artifact_id)
        self.authorize(value)
        if value.get("artifact_type") not in (
            kinds
            or {
                "source",
                "normalized",
                "growth",
                "profile",
                "diagnostic",
                "decision",
                "growth_analysis",
                "cohort_analysis",
                "experiment_plan",
                "experiment_result",
            }
        ):
            raise MMMError("ARTIFACT_TYPE", "Unexpected artifact type")
        return value

    def preview_dataset(self, request):
        self.authorize(request.model_dump())
        if not request.synthetic and not request.authorization_reference:
            raise MMMError(
                "AUTHORIZATION_REQUIRED", "Host permission and authorization reference required"
            )
        raw, rows, columns, sheets, checksum = parse_file(request, self.settings)
        return {
            "format": request.format,
            "sha256": checksum,
            "bytes": len(raw),
            "columns": columns,
            "sheets": sheets,
            "row_count": len(rows),
            "preview": rows[:10],
            "semantic_detection": "unidentified; explicit mapping required",
            "privacy_notice": "Preview contains supplied cell values; review personal data before sharing.",
        }

    def import_source(self, request):
        self.preview_dataset(request)
        if not request.confirm:
            raise MMMError("CONFIRM_REQUIRED", "Review preview and explicitly confirm import")
        _, rows, columns, sheets, checksum = parse_file(request, self.settings)
        return self._growth_save(
            "source",
            {
                **request.model_dump(),
                "rows": rows,
                "schema_original": columns,
                "sheets": sheets,
                "source_sha256": checksum,
            },
        )

    def list_media_profiles(self, request):
        from .lifecycle import inventory

        custom = [
            self._growth_read(item["artifact_id"], {"profile"})
            for item in inventory(self.store)["artifacts"]
            if item["artifact_type"] == "profile"
        ]
        return {
            "profiles": [*PROFILES.values(), *custom],
            "custom_profiles": "Register immutable definitions with register_media_profile; select returned ID",
        }

    def register_media_profile(self, request):
        fields = [*request.required, *request.optional]
        if (
            len(fields) != len(set(fields))
            or "date" not in request.required
            or any(not c or len(c) > 80 for c in fields)
        ):
            raise MMMError("PROFILE_INVALID", "Unique fields and required date are necessary")
        return self._growth_save("profile", {**request.model_dump(), "synthetic": True})

    def map_dataset_schema(self, request):
        source = self._growth_read(request.source_id, {"source"})
        profile = PROFILES.get(request.profile) or self._growth_read(request.profile, {"profile"})
        if len(set(request.mapping.values())) != len(request.mapping) or set(request.mapping) - set(
            source["schema_original"]
        ):
            raise MMMError(
                "MAPPING_INVALID", "Map existing source columns to distinct logical fields"
            )
        from .media_validation import OPTIONAL

        allowed = set(profile["required"] + profile["optional"] + OPTIONAL) | {
            "campaign",
            "region",
            "channel",
            "platform",
            "strategy",
            "format",
            "segment",
        }
        if set(request.mapping.values()) - allowed:
            raise MMMError(
                "MAPPING_INVALID", "Declare unknown fields in a versioned custom profile"
            )
        reporting_tz = reporting_timezone(request.timezone)
        rows = []
        for raw in source["rows"]:
            row = {}
            for original, logical in request.mapping.items():
                value = raw[original]
                if value is not None:
                    if logical == "date":
                        instant = datetime.strptime(str(value), request.date_format)
                        if instant.tzinfo is not None:
                            instant = instant.astimezone(reporting_tz)
                        elif any(part in request.date_format for part in ("%H", "%I", "%M", "%S")):
                            raise MMMError(
                                "DATE_AMBIGUOUS", "Timestamps require an explicit UTC offset"
                            )
                        value = instant.date().isoformat()
                    elif logical not in {
                        "campaign",
                        "region",
                        "channel",
                        "platform",
                        "strategy",
                        "format",
                        "segment",
                    }:
                        if isinstance(value, bool):
                            raise MMMError("MAPPING_INVALID", "Boolean is not a numeric metric")
                        value = float(value)
                        if not math.isfinite(value) or abs(value) > 1e12:
                            raise MMMError("MAPPING_INVALID", "Nonfinite or excessive number")
                row[logical] = value
            rows.append(row)
        record = {
            **request.model_dump(),
            "rows": rows,
            "profile": profile,
            "synthetic": source["synthetic"],
            "source_sha256": source["source_sha256"],
            "origin": source["origin"],
            "authorization_reference": source["authorization_reference"],
            "transformations": [
                "explicit column selection/mapping",
                "declared numeric/date conversion",
            ],
            "unmapped_columns": sorted(set(source["schema_original"]) - set(request.mapping)),
        }
        return self._growth_save("normalized", record)

    def get_growth_artifact(self, request):
        return self._growth_read(request.artifact_id)

    def validate_media_dataset(self, request):
        artifact = self._growth_read(request.artifact_id, {"normalized"})
        return {
            "artifact_id": request.artifact_id,
            "source_id": artifact.get("source_id"),
            **validate_media(artifact),
        }

    def validate_crossmedia_dataset(self, request):
        artifacts = [self._growth_read(i, {"normalized"}) for i in request.artifact_ids]
        matrix = [
            {
                "artifact_id": a["artifact_id"],
                "channel_confirmed": a["dimensions"].get("channel"),
                "channel_detected": None,
                "units": a["units"],
                **validate_media(a),
            }
            for a in artifacts
        ]
        incompatibilities = []
        for key in ["region", "universe", "methodology", "measurement_period"]:
            values = {a["dimensions"].get(key) for a in artifacts}
            if len(values) > 1 or None in values:
                incompatibilities.append("Different or unidentified " + key)
        for key in ["frequency_days", "timezone"]:
            if len({a[key] for a in artifacts}) > 1:
                incompatibilities.append("Different " + key)
        shared = set().union(*(set(a["units"]) for a in artifacts))
        for metric in shared:
            if len({a["units"][metric] for a in artifacts if metric in a["units"]}) > 1:
                incompatibilities.append("Incompatible unit: " + metric)
        periods = [set(r.get("date") for r in a["rows"]) for a in artifacts]
        overlap = set.intersection(*periods)
        if not overlap:
            incompatibilities.append("No common periods")
        return {
            "coverage_matrix": matrix,
            "incompatibilities": incompatibilities,
            "shared_dates": sorted(d for d in overlap if d),
            "crossmedia_reach": None,
            "warnings": [
                "Audience, reach, impressions, circulation and GRPs remain distinct. No deduplicated crossmedia reach."
            ],
        }

    def build_growth_dataset(self, request):
        artifacts = [self._growth_read(i, {"normalized"}) for i in request.artifact_ids]
        output = []
        for artifact in artifacts:
            report = validate_media(artifact)
            if report["errors"]:
                raise MMMError(
                    "INVALID_MEDIA", "Resolve media validation errors before aggregation"
                )
            groups = defaultdict(list)
            dimensions = {
                "campaign",
                "region",
                "channel",
                "platform",
                "strategy",
                "format",
                "segment",
            }
            for row in artifact["rows"]:
                day = datetime.fromisoformat(row["date"]).date()
                if request.frequency == "weekly":
                    day -= timedelta(days=day.weekday())
                grain = tuple((k, row.get(k)) for k in sorted(dimensions & set(row)))
                groups[(day.isoformat(), grain)].append(row)
            for (day, grain), rows in groups.items():
                row = {"date": day, **dict(grain)}
                for metric in set(rows[0]) - dimensions - {"date"}:
                    rule = request.aggregations.get(metric)
                    if not rule:
                        raise MMMError(
                            "AGGREGATION_REQUIRED",
                            "Declare aggregation for every metric: " + metric,
                        )
                    if rule == "sum" and metric in artifact["profile"]["nonadditive"]:
                        raise MMMError("NONADDITIVE", "Sum is not defensible for " + metric)
                    values = [r[metric] for r in rows]
                    if any(v is None for v in values):
                        row[metric] = None
                    elif rule == "sum":
                        row[metric] = sum(values)
                    elif rule == "weighted_mean":
                        weight = request.weights.get(metric)
                        weights = [r.get(weight) for r in rows]
                        if (
                            any(not isinstance(w, (int, float)) or w < 0 for w in weights)
                            or sum(weights) <= 0
                        ):
                            raise MMMError(
                                "WEIGHT_INVALID",
                                "Explicit nonnegative weights with positive total required",
                            )
                        row[metric] = sum(v * w for v, w in zip(values, weights)) / sum(weights)
                    else:
                        pair = request.ratios.get(metric, [])
                        if len(pair) != 2 or any(r.get(c) is None for r in rows for c in pair):
                            raise MMMError(
                                "RATIO_INVALID", "Declare available numerator and denominator"
                            )
                        denominator = sum(r[pair[1]] for r in rows)
                        row[metric] = (
                            sum(r[pair[0]] for r in rows) / denominator if denominator > 0 else None
                        )
                output.append(
                    {
                        "source_id": artifact.get("source_id"),
                        "source_ids": artifact.get("source_ids") or [artifact["source_id"]],
                        "normalized_id": artifact["artifact_id"],
                        "dimensions": artifact["dimensions"],
                        "units": artifact["units"],
                        "values": row,
                    }
                )
        return self._growth_save(
            "growth",
            {
                "synthetic": all(a["synthetic"] for a in artifacts),
                "source_ids": request.artifact_ids,
                "observations": output,
                "aggregation": request.model_dump(),
                "warnings": [
                    "Canonical long observations preserve source grain; no automatic join or crossmedia metric sum."
                ],
            },
        )

    def check_mmm_eligibility(self, request):
        artifact = self._growth_read(request.artifact_id, {"normalized"})
        return eligibility(artifact, request)

    def create_growth_diagnostic(self, request):
        artifact = self._growth_read(request.artifact_id, {"normalized"})
        report = validate_media(artifact)
        observations = []
        for metric in ["spend", "sales", "leads", "conversions", "audience", "clicks"]:
            values = [r.get(metric) for r in artifact["rows"]]
            if len(values) > 1 and all(isinstance(v, (int, float)) for v in values):
                ordered = sorted(artifact["rows"], key=lambda r: r["date"])
                observations.append(
                    {
                        "metric": metric,
                        "unit": artifact["units"].get(metric),
                        "first": ordered[0][metric],
                        "last": ordered[-1][metric],
                    }
                )
        return self._growth_save(
            "diagnostic",
            {
                "synthetic": artifact["synthetic"],
                "source_id": request.artifact_id,
                "problem": "Descriptive changes or data quality require investigation",
                "evidence": observations,
                "period": report["period"],
                "validation": report,
                "abstained": not report["growth_compatible"] or not observations,
                "hypothesis": "Measurement or audience/commercial mix changed",
                "alternatives": ["Seasonality", "Tracking change", "Confounding"],
                "next_investigation": "Reconcile definitions and inspect aligned commercial outcomes",
                "validation_criterion": "Predeclare an appropriate comparison and outcome measurement",
                "limitations": [
                    "Endpoints are descriptive; no trend significance, business recommendation or causal effect inferred."
                ],
            },
        )

    def create_growth_decision(self, request):
        diagnostic = self._growth_read(request.diagnostic_id, {"diagnostic"})
        return self._growth_save(
            "decision",
            {
                **request.model_dump(),
                "synthetic": diagnostic["synthetic"],
                "state": "proposed",
                "revision": 0,
                "previous_id": None,
                "benefit_estimate": None,
                "uncertainty": "Exploratory hypothesis; human review required",
                "external_action_executed": False,
            },
        )

    def transition_growth_decision(self, request):
        if (
            request.plan is not None
            and request.state != "planned"
            or request.results_id is not None
            and request.state != "evaluated"
        ):
            raise MMMError(
                "STATE_FIELDS",
                "Plan and results may only be supplied at their corresponding transitions",
            )
        previous = self._growth_read(request.artifact_id, {"decision"})
        transitions = {
            "proposed": {"approved", "rejected"},
            "approved": {"planned", "rejected"},
            "planned": {"evaluated"},
            "evaluated": {"learned"},
        }
        if request.state not in transitions.get(previous["state"], set()):
            raise MMMError("STATE_INVALID", "Invalid decision transition")
        if request.state == "planned":
            required = {
                "hypothesis",
                "unit",
                "window",
                "duration",
                "sample_assumptions",
                "control",
                "success",
                "stop",
                "guardrails",
            }
            if not request.plan or any(not request.plan.get(k) for k in required):
                raise MMMError(
                    "PLAN_INCOMPLETE",
                    "Specify hypothesis, unit, window, duration, sample assumptions, control, success, stop and guardrails",
                )
            if request.plan.get("experiment_plan_id"):
                experiment = self._growth_read(
                    request.plan["experiment_plan_id"], {"experiment_plan"}
                )
                if (
                    experiment["kpi"] != previous["kpi"]
                    or experiment["method"] != previous["method"]
                ):
                    raise MMMError(
                        "PLAN_INCOMPATIBLE", "Experiment KPI and method must match the decision"
                    )
        result = None
        if request.state == "evaluated":
            if not request.results_id:
                raise MMMError("RESULTS_REQUIRED", "Import results before evaluation")
            result = self._growth_read(
                request.results_id, {"source", "normalized", "experiment_result"}
            )
            linked_plan = previous["plan"].get("experiment_plan_id")
            if linked_plan and (
                result.get("plan_id") != linked_plan or result.get("kpi") != previous["kpi"]
            ):
                raise MMMError(
                    "RESULTS_INCOMPATIBLE",
                    "Use the statistical analysis for the experiment linked to this decision",
                )
            if result["artifact_type"] == "experiment_result" and not linked_plan:
                raise MMMError(
                    "PLAN_INCOMPATIBLE",
                    "Link an experiment plan before recording its statistical analysis",
                )
        revision = previous["revision"] + 1
        root = previous.get("root_id") or previous["artifact_id"]
        return self._growth_save(
            "decision",
            {
                **previous,
                "root_id": root,
                "revision": revision,
                "previous_id": previous["artifact_id"],
                "state": request.state,
                "actor_declaration": request.actor,
                "review_note": request.note,
                "approval_identity_verified": False,
                "plan": request.plan or previous.get("plan"),
                "results_id": request.results_id or previous.get("results_id"),
                "synthetic": previous["synthetic"] and (result["synthetic"] if result else True),
                "limitations": [
                    "Human approval is a recorded declaration, not identity verification; external execution is manual."
                ],
            },
            root + "-r" + str(revision),
        )
