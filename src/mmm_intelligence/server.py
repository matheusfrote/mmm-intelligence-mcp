"""Official MCP SDK v2 adapter. Stdout is reserved for MCP frames in stdio mode."""

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .config import Settings
from .schemas import (
    DatasetRequest,
    GenerateRequest,
    ModelRequest,
    SimulateRequest,
    ToolResponse,
    TrainRequest,
    ValidateRequest,
)
from .service import MMMService


def create_server(
    settings: Settings | None = None, service_override=None
) -> tuple[MCPServer, MMMService]:
    service = service_override or MMMService(settings or Settings.from_env())
    mcp = MCPServer(
        "MMM Intelligence MCP",
        instructions="Local exploratory MMM. Call tools with a request object. Check ok/error and "
        "validate_dataset.data.valid. No causal attribution or real campaign operations.",
    )
    read_only = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
    creates = ToolAnnotations(
        read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
    )

    @mcp.resource("mmm://datasets/{dataset_id}", mime_type="application/json")
    def dataset_resource(dataset_id: str) -> str:
        """Read authorized tenant dataset rows; IDs only, never paths or URLs."""
        import json

        try:
            request = DatasetRequest(dataset_id=dataset_id)
            return json.dumps(service.load_dataset(request.dataset_id), allow_nan=False)
        except Exception:
            raise ValueError("Dataset unavailable or unauthorized") from None

    @mcp.tool(annotations=creates)
    def generate_demo_dataset(request: GenerateRequest) -> ToolResponse:
        """Create immutable synthetic daily/weekly data; optional ID, periods, seed and start date."""
        return service.call("generate_demo_dataset", request.model_dump(mode="json"))

    @mcp.tool(annotations=read_only)
    def validate_dataset(request: ValidateRequest) -> ToolResponse:
        """Inspect columns, finite/nonnegative values, ISO dates, duplicates, gaps and temporal split.

        Returns data.valid=false and issues for unsuitable datasets; never sorts or imputes silently.
        """
        return service.call("validate_dataset", request.model_dump(mode="json"))

    @mcp.tool(annotations=creates)
    def train_mmm(request: TrainRequest) -> ToolResponse:
        """Fit positive-media constrained ridge, geometric adstock and Hill, with chronological test.

        Shape parameters are fixed inputs; scaling and saturation use training data only.
        Persists parameters, MAE/WAPE/R2, holdout predictions and carryover state. Exploratory only.
        """
        return service.call("train_mmm", request.model_dump(mode="json"))

    @mcp.tool(annotations=read_only)
    def get_model(request: ModelRequest) -> ToolResponse:
        """Read a persisted model by ID, including parameters, split, metrics, predictions and warnings."""
        return service.call("get_model", request.model_dump(mode="json"))

    @mcp.tool(annotations=read_only)
    def simulate_budget(request: SimulateRequest) -> ToolResponse:
        """Compare a flat allocation to recent mean spending with historical carryover and future controls.

        total_budget covers the whole horizon (1..104 periods); allocation fractions sum to one.
        Point estimates are conditional, exploratory, without causal or uncertainty guarantees.
        """
        return service.call("simulate_budget", request.model_dump(mode="json"))

    descriptions = {
        "storage_inventory": "Inspect verified artifact IDs, hashes, sizes and lineage inside the current tenant; excludes logs and runtimes.",
        "retention_plan": "Prepare a retention review by age and dependencies; never deletes files.",
        "connector_status": "Report source connector readiness honestly; contracts and offline reconciliation are not live authenticated integrations.",
        "export_analysis": "Export canonical historical model evidence as JSON, safe numeric CSV or Markdown; no filesystem path input.",
        "forecast_model": "Project future dates with explicit time-varying media and controls in Ridge or native PyMC; preserves observed adstock history and reports interval semantics.",
        "get_analysis": "Normalize persisted evidence, test metrics, native diagnostics and capabilities without claiming engine equivalence.",
        "compare_models": "Compare the same dataset and KPI on exact or explicitly intersected holdout dates; no universal winner or causal ranking.",
        "model_capabilities": "Read operation availability and reasons per engine; unsupported operations never use a substitute engine.",
        "import_csv": "Import bounded inline CSV with explicit mapping, date/timezone, aggregation policies and preserved original provenance; never opens paths or URLs.",
        "data_quality": "Inspect completeness, missing periods, distributions, correlation and descriptive tracking screens without modifying data.",
        "backend_status": "List implemented capabilities and optional runtime presence without claiming statistical validity.",
        "import_dataset": "Import explicit inline rows with provenance and host authorization for real data.",
        "optimize_budget": "Optimize the exploratory Hill-one model with total and channel budget bounds.",
        "tune_mmm": "Select adstock/saturation on an inner temporal validation, reserving the outer test.",
        "calibrate_experiment": "Compare and reweight bootstrap draws with an explicitly declared lift experiment.",
        "render_dashboard": "Create an immutable standalone HTML dashboard, with local scenario controls.",
        "generate_report": "Generate an immutable local Markdown analytical report from persisted results.",
        "train_backend": "Train an actual external backend in its isolated configured runtime; no Ridge fallback.",
        "predict_backend": "Restore native backend state and evaluate a historical media scenario.",
        "get_backend_model": "Read external backend metadata, diagnostics and predictions without native binaries.",
        "audit_model": "Audit local model lineage, component reconciliation, rolling temporal backtests, shape sensitivity and evidence for abstaining from budget changes.",
    }
    for name, description in descriptions.items():

        def make_handler(tool_name, request_type):
            def handler(request):
                return service.call(tool_name, request.model_dump(mode="json"))

            handler.__annotations__ = {"request": request_type, "return": ToolResponse}
            return handler

        mcp.tool(
            name=name,
            description=description,
            annotations=(
                read_only
                if name
                in {
                    "optimize_budget",
                    "calibrate_experiment",
                    "predict_backend",
                    "get_backend_model",
                    "backend_status",
                    "audit_model",
                    "data_quality",
                    "get_analysis",
                    "compare_models",
                    "model_capabilities",
                    "forecast_model",
                    "export_analysis",
                    "storage_inventory",
                    "retention_plan",
                    "connector_status",
                }
                else creates
            ),
        )(make_handler(name, service.REQUESTS[name]))

    return mcp, service


def main():
    import json
    import os

    if os.environ.get("MMM_TRANSPORT", "stdio") == "streamable-http":
        import uvicorn

        from .http_transport import create_http_app

        users = json.loads(os.environ.get("MMM_USERS_JSON", "{}"))
        app = create_http_app(Settings.from_env(), users)
        uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("MMM_PORT", "8769")))
        return
    if os.environ.get("MMM_TRANSPORT", "stdio") != "stdio":
        raise ValueError("Unsupported MMM_TRANSPORT")
    mcp, service = create_server()
    try:
        mcp.run(transport="stdio")
    finally:
        service.close()


if __name__ == "__main__":
    main()
