"""Application boundary: authorization, diagnostics, tools and structured failures."""

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from uuid import uuid4

from pydantic import ValidationError
from threadpoolctl import threadpool_limits

from .config import Settings
from .datasets import generate, validate
from .errors import MMMError
from .growth import REQUESTS as GROWTH_REQUESTS
from .growth import GrowthMixin
from .modeling import train
from .schemas import (
    AnalysisRequest,
    AuditRequest,
    BackendPredictRequest,
    BackendRequest,
    CalibrationRequest,
    CapabilityRequest,
    CompareRequest,
    Contract,
    CSVImportRequest,
    EmptyRequest,
    ExportRequest,
    ForecastRequest,
    GenerateRequest,
    ImportRequest,
    ModelRequest,
    OptimizeRequest,
    PublicError,
    RenderRequest,
    RetentionRequest,
    SimulateRequest,
    ToolResponse,
    TrainRequest,
    TuneRequest,
    ValidateRequest,
)
from .simulation import check_model, simulate
from .storage import ArtifactStore, digest, reject_links

COMPUTE_GATE = threading.BoundedSemaphore(1)
COMPUTE_TOOLS = {
    "train_mmm",
    "tune_mmm",
    "optimize_budget",
    "train_backend",
    "predict_backend",
    "calibrate_experiment",
    "audit_model",
    "forecast_model",
}


class MMMService(GrowthMixin):
    REQUESTS: dict[str, type[Contract]] = {
        **GROWTH_REQUESTS,
        "generate_demo_dataset": GenerateRequest,
        "validate_dataset": ValidateRequest,
        "train_mmm": TrainRequest,
        "get_model": ModelRequest,
        "simulate_budget": SimulateRequest,
        "import_dataset": ImportRequest,
        "optimize_budget": OptimizeRequest,
        "tune_mmm": TuneRequest,
        "calibrate_experiment": CalibrationRequest,
        "render_dashboard": RenderRequest,
        "generate_report": RenderRequest,
        "train_backend": BackendRequest,
        "predict_backend": BackendPredictRequest,
        "get_backend_model": ModelRequest,
        "backend_status": EmptyRequest,
        "audit_model": AuditRequest,
        "import_csv": CSVImportRequest,
        "data_quality": ValidateRequest,
        "get_analysis": AnalysisRequest,
        "compare_models": CompareRequest,
        "model_capabilities": CapabilityRequest,
        "forecast_model": ForecastRequest,
        "export_analysis": ExportRequest,
        "storage_inventory": EmptyRequest,
        "retention_plan": RetentionRequest,
        "connector_status": EmptyRequest,
    }

    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = ArtifactStore(settings)
        self.log = logging.getLogger(f"mmm_intelligence.{uuid4().hex}")
        self.log.setLevel(settings.log_level)
        self.log.propagate = False
        log_path = self.store.root / "logs" / "server.log"
        reject_links(log_path)
        if log_path.exists() and log_path.stat().st_nlink > 1:
            raise MMMError("UNSAFE_PATH", "Log must not be a hard link")
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        for handler in (
            RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ):
            handler.setFormatter(formatter)
            self.log.addHandler(handler)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def close(self):
        for handler in self.log.handlers[:]:
            handler.close()
            self.log.removeHandler(handler)

    def authorize(self, artifact: dict):
        if artifact.get("synthetic") is not True and not self.settings.allow_real_data:
            raise MMMError(
                "REAL_DATA_DISABLED", "Host authorization is required for nonsynthetic data"
            )

    def call(self, tool: str, arguments: dict) -> ToolResponse:
        event_id = uuid4().hex
        try:
            if tool not in self.REQUESTS:
                raise MMMError("UNKNOWN_TOOL", "Unknown tool")
            try:
                request = self.REQUESTS[tool].model_validate(arguments)
            except ValidationError as exc:
                locations = [".".join(str(p) for p in e["loc"]) for e in exc.errors()]
                raise MMMError("INPUT_INVALID", "Invalid fields: " + ", ".join(locations)) from exc
            if tool in COMPUTE_TOOLS:
                if not COMPUTE_GATE.acquire(blocking=False):
                    raise MMMError("BUSY", "Another compute job is running; retry later")
                try:
                    with threadpool_limits(limits=1):
                        data = getattr(self, tool)(request)
                finally:
                    COMPUTE_GATE.release()
            else:
                data = getattr(self, tool)(request)
            warnings = data.get("warnings", [])
            response = ToolResponse(ok=True, data=data, warnings=warnings)
            self.log.info("event=%s tool=%s status=ok", event_id, tool)
            return response
        except ValidationError:
            code, message = "INTERNAL_ERROR", "Invalid internal result; check local diagnostics"
        except MMMError as exc:
            code, message = exc.code, str(exc)
        except (ValueError, OverflowError):
            code, message = "INVALID_DATA", "Invalid or excessive data values or date range"
        except OSError:
            code, message = (
                "STORAGE_ERROR",
                "Local storage operation failed; check host permissions",
            )
        except Exception:
            code, message = "INTERNAL_ERROR", "Unexpected failure; check local diagnostics"
        self.log.error("event=%s tool=%s status=error code=%s", event_id, tool, code)
        return ToolResponse(ok=False, error=PublicError(code=code, message=message))

    def generate_demo_dataset(self, request: GenerateRequest) -> dict:
        if request.periods > self.settings.max_rows:
            raise MMMError("ROW_LIMIT", "Requested periods exceed the configured row limit")
        dataset_id = request.dataset_id or "demo-" + uuid4().hex
        payload = generate(request)
        checksum = self.store.write("datasets", dataset_id, payload)
        return {
            "dataset_id": dataset_id,
            "rows": request.periods,
            "synthetic": True,
            "frequency": request.frequency,
            "sha256": checksum,
            "columns": list(payload["rows"][0]),
            "units": payload["units"],
        }

    def load_dataset(self, dataset_id):
        dataset = self.store.read("datasets", dataset_id)
        self.authorize(dataset)
        return dataset

    def validate_dataset(self, request: ValidateRequest) -> dict:
        dataset = self.load_dataset(request.dataset_id)
        return {
            "dataset_id": request.dataset_id,
            **validate(dataset, request, self.settings.max_rows),
        }

    def train_mmm(self, request: TrainRequest) -> dict:
        dataset = self.load_dataset(request.dataset_id)
        report = validate(dataset, request, self.settings.max_rows)
        if not report["valid"]:
            raise MMMError("DATASET_INVALID", "; ".join(report["issues"]))
        model_id = request.model_id or "model-" + uuid4().hex
        model = train(dataset, request, model_id, report)
        checksum = self.store.write("models", model_id, model)
        return {
            "model_id": model_id,
            "sha256": checksum,
            "metrics": model["metrics"],
            "split": model["split"],
            "coefficients": model["coefficients"],
            "synthetic": model["synthetic"],
            "warnings": model["warnings"],
        }

    def get_model(self, request: ModelRequest) -> dict:
        model = self.store.read("models", request.model_id)
        self.authorize(model)
        check_model(model)
        return model

    def simulate_budget(self, request: SimulateRequest) -> dict:
        model = self.get_model(ModelRequest(model_id=request.model_id))
        return simulate(model, request)

    def import_dataset(self, request: ImportRequest) -> dict:
        dataset_id = request.dataset_id or "import-" + uuid4().hex
        payload = {
            "schema_version": 1,
            "synthetic": request.synthetic,
            "source": "explicit-inline-import",
            "target_type": request.target_type,
            "data_context": request.data_context,
            "authorization_reference": request.authorization_reference,
            "frequency": request.frequency,
            "units": request.units,
            "rows": request.rows,
            "column_spec": {
                k: getattr(request, k)
                for k in ("media_columns", "control_columns", "target_column", "date_column")
            },
        }
        self.authorize(payload)
        spec = ValidateRequest(
            dataset_id=dataset_id,
            media_columns=request.media_columns,
            control_columns=request.control_columns,
            target_column=request.target_column,
            date_column=request.date_column,
        )
        report = validate(payload, spec, self.settings.max_rows)
        if not report["valid"]:
            raise MMMError("DATASET_INVALID", "; ".join(report["issues"]))
        checksum = self.store.write("datasets", dataset_id, payload)
        return {
            "dataset_id": dataset_id,
            "sha256": checksum,
            "validation": report,
            "synthetic": request.synthetic,
        }

    def import_csv(self, request: CSVImportRequest) -> dict:
        from .ingestion import parse_csv

        self.authorize({"synthetic": request.synthetic})
        parsed = parse_csv(
            request, max_rows=self.settings.max_rows, max_bytes=self.settings.max_file_bytes
        )
        dataset_id = request.dataset_id or "csv-" + uuid4().hex
        spec = ValidateRequest(
            dataset_id=dataset_id,
            **{
                k: getattr(request, k)
                for k in ("media_columns", "control_columns", "target_column", "date_column")
            },
        )
        payload = {
            "schema_version": 1,
            "synthetic": request.synthetic,
            "source": "explicit-inline-csv",
            "target_type": request.target_type,
            "data_context": request.data_context,
            "frequency": request.frequency,
            "units": request.units,
            "authorization_reference": request.authorization_reference,
            "column_spec": {
                k: getattr(request, k)
                for k in ("media_columns", "control_columns", "target_column", "date_column")
            },
            **parsed,
        }
        report = validate(payload, spec, self.settings.max_rows)
        if not report["valid"]:
            raise MMMError("DATASET_INVALID", "; ".join(report["issues"]))
        checksum = self.store.write("datasets", dataset_id, payload)
        return {
            "dataset_id": dataset_id,
            "sha256": checksum,
            "validation": report,
            "synthetic": request.synthetic,
            "transformations": parsed["provenance"]["transformations"],
        }

    def data_quality(self, request: ValidateRequest) -> dict:
        from .quality import assess

        return {
            "dataset_id": request.dataset_id,
            **assess(self.load_dataset(request.dataset_id), request, self.settings.max_rows),
        }

    def get_analysis(self, request: AnalysisRequest) -> dict:
        from .canonical import bundle

        if request.backend == "ridge":
            model = self.get_model(ModelRequest(model_id=request.model_id))
            dataset = self.load_dataset(model["dataset_id"])
        else:
            model = self.store.read("backend_models", request.model_id)
            self.authorize(model)
            dataset = model["dataset"]
            self.authorize(dataset)
        return bundle(model, dataset, request)

    def storage_inventory(self, request: EmptyRequest) -> dict:
        from .lifecycle import inventory

        result = inventory(self.store)
        for artifact in result["artifacts"]:
            self.authorize(artifact)
        return result

    def retention_plan(self, request: RetentionRequest) -> dict:
        from .lifecycle import retention_plan

        self.storage_inventory(EmptyRequest())
        return retention_plan(self.store, request.older_than_days)

    def connector_status(self, request: EmptyRequest) -> dict:
        from .connectors import connector_status

        return {"sources": connector_status(), "network_requests": 0}

    def compare_models(self, request: CompareRequest) -> dict:
        from .canonical import compare

        return compare([self.get_analysis(r) for r in request.models], request.window_policy)

    def export_analysis(self, request: ExportRequest) -> dict:
        from .exporting import export

        return export(self.get_analysis(request), request.format)

    def model_capabilities(self, request: CapabilityRequest) -> dict:
        from .canonical import capabilities

        return capabilities(request.backend)

    def forecast_model(self, request: ForecastRequest) -> dict:
        from .canonical import capabilities
        from .forecasting import decision, prepare, ridge_forecast
        from .integrations.bridge import execute

        if not capabilities(request.backend)["future_projection"]["available"]:
            raise MMMError(
                "OPERATION_UNAVAILABLE",
                capabilities(request.backend)["future_projection"]["reason"],
            )
        if request.backend == "ridge":
            model = self.get_model(ModelRequest(model_id=request.model_id))
        else:
            model = self.store.read("backend_models", request.model_id)
            self.authorize(model)
            self.authorize(model["dataset"])
            if digest(model["dataset"]) != model["dataset_sha256"]:
                raise MMMError("LINEAGE_MISMATCH", "Native dataset differs from model lineage")
        rows, assumptions = prepare(model, request)
        if request.backend == "ridge":
            prediction = ridge_forecast(model, request, rows)
        else:
            native = execute(
                self.store,
                request.backend,
                {"operation": "forecast", "model": model, "future_rows": rows},
            )
            prediction = native["prediction"]
        warnings = assumptions.pop("warnings")
        if any(v < 0 for v in prediction["mean"]):
            warnings.append("NEGATIVE_PREDICTIONS: no clipping applied; review model suitability")
        return {
            "model_id": request.model_id,
            "backend": request.backend,
            "scope": "future_conditional_projection",
            "synthetic": model["synthetic"],
            "assumptions": assumptions,
            "prediction": prediction,
            "diagnostics": model.get("diagnostics", {}),
            "decision_support": decision(),
            "warnings": warnings,
            "exploratory": True,
        }

    def optimize_budget(self, request: OptimizeRequest) -> dict:
        from .canonical import require_operation
        from .optimization import optimize

        require_operation(request.backend, "optimization")
        return optimize(self.get_model(ModelRequest(model_id=request.model_id)), request)

    def tune_mmm(self, request: TuneRequest) -> dict:
        from .analysis import tune

        dataset = self.load_dataset(request.dataset_id)
        model_id = request.model_id or "tuned-" + uuid4().hex
        model = tune(dataset, request, model_id, self.settings.max_rows)
        checksum = self.store.write("models", model_id, model)
        return {
            "model_id": model_id,
            "sha256": checksum,
            "metrics": model["metrics"],
            "shape_selection": model["shape_selection"],
            "warnings": model["warnings"],
        }

    def calibrate_experiment(self, request: CalibrationRequest) -> dict:
        from .analysis import calibrate

        self.authorize({"synthetic": request.synthetic})
        return calibrate(self.get_model(ModelRequest(model_id=request.model_id)), request)

    def render_dashboard(self, request: RenderRequest) -> dict:
        from .quality import assess
        from .rendering import dashboard
        from .scientific import decomposition

        model = self.get_model(ModelRequest(model_id=request.model_id))
        dataset = self.load_dataset(model["dataset_id"])
        if digest(dataset) != model["dataset_sha256"]:
            raise MMMError("LINEAGE_MISMATCH", "Dashboard dataset differs from fitted lineage")
        context = {
            "quality": assess(
                dataset, TrainRequest.model_validate(model["request"]), self.settings.max_rows
            ),
            "decomposition": decomposition(dataset, model),
        }
        artifact_id = request.artifact_id or "dashboard-" + uuid4().hex
        payload = {
            "model_id": request.model_id,
            "synthetic": model["synthetic"],
            "format": "html",
            "content": dashboard(model, context),
        }
        checksum = self.store.write("dashboards", artifact_id, payload)
        return {"artifact_id": artifact_id, "kind": "dashboards", "sha256": checksum, **payload}

    def generate_report(self, request: RenderRequest) -> dict:
        from .rendering import report

        model = self.get_model(ModelRequest(model_id=request.model_id))
        artifact_id = request.artifact_id or "report-" + uuid4().hex
        payload = {
            "model_id": request.model_id,
            "synthetic": model["synthetic"],
            "format": "markdown",
            "content": report(model),
        }
        checksum = self.store.write("reports", artifact_id, payload)
        return {"artifact_id": artifact_id, "kind": "reports", "sha256": checksum, **payload}

    def train_backend(self, request: BackendRequest) -> dict:
        from .integrations.bridge import execute

        dataset = self.load_dataset(request.dataset_id)
        report = validate(dataset, request, self.settings.max_rows)
        if not report["valid"]:
            raise MMMError("DATASET_INVALID", "; ".join(report["issues"]))
        model_id = request.model_id or request.backend + "-" + uuid4().hex
        model = execute(
            self.store,
            request.backend,
            {"operation": "train", "dataset": dataset, "request": request.model_dump(mode="json")},
        )
        model.update(
            model_id=model_id,
            dataset_id=request.dataset_id,
            synthetic=dataset["synthetic"],
            exploratory=True,
            dataset_sha256=digest(dataset),
        )
        checksum = self.store.write("backend_models", model_id, model)
        return {
            "model_id": model_id,
            "sha256": checksum,
            **{k: v for k, v in model.items() if k not in {"native_base64", "dataset"}},
        }

    def get_backend_model(self, request: ModelRequest) -> dict:
        model = self.store.read("backend_models", request.model_id)
        self.authorize(model)
        return {k: v for k, v in model.items() if k not in {"native_base64", "dataset"}}

    def predict_backend(self, request: BackendPredictRequest) -> dict:
        from .integrations.bridge import execute

        model = self.store.read("backend_models", request.model_id)
        self.authorize(model)
        return execute(
            self.store,
            model["backend"],
            {"operation": "predict", "model": model, "request": request.model_dump(mode="json")},
        )

    def backend_status(self, request: EmptyRequest) -> dict:
        from .integrations import CAPABILITIES
        from .integrations.bridge import executable

        return {
            "capabilities": CAPABILITIES,
            "runtimes": {
                name: {
                    "configured_executable_present": executable(name).is_file(),
                    "verification": "Run native train/reload/scenario verification in the configured runtime",
                }
                for name in ("google_meridian", "pymc_marketing", "meta_robyn")
            },
            "warnings": [
                "Installed executable does not prove installed library or statistical convergence"
            ],
        }

    def audit_model(self, request: AuditRequest) -> dict:
        from .scientific import audit

        model = self.get_model(ModelRequest(model_id=request.model_id))
        dataset = self.load_dataset(model["dataset_id"])
        return audit(dataset, model, request, self.settings.max_rows)
