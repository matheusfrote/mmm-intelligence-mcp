import csv
import io
import json


def test_exported_canonical_numbers_match_model(service, trained):
    out = service.call("export_analysis", {"backend": "ridge", "model_id": "fit", "format": "json"})
    assert out.ok, out.error
    analysis = json.loads(out.data["content"])
    assert analysis["metrics"]["mae"] == trained["metrics"]["test"]["mae"]
    out = service.call("export_analysis", {"backend": "ridge", "model_id": "fit", "format": "csv"})
    rows = list(csv.DictReader(io.StringIO(out.data["content"])))
    test = [p for p in trained["predictions"] if p["split"] == "test"]
    assert len(rows) == len(test)
    assert float(rows[-1]["predicted"]) == test[-1]["predicted"]
    out = service.call(
        "export_analysis", {"backend": "ridge", "model_id": "fit", "format": "markdown"}
    )
    assert out.ok and "causal" in out.data["content"]


def test_dashboard_contains_real_quality_components_and_navigation(service, trained):
    out = service.call("render_dashboard", {"model_id": "fit"})
    assert out.ok, out.error
    text = out.data["content"]
    for marker in (
        'id="overview"',
        'id="quality"',
        'id="residuals"',
        'id="decomposition"',
        'id="response-curves"',
        'id="exports"',
        "download-json",
        "download-csv",
    ):
        assert marker in text
    assert "maximum_reconciliation_error" in text
    assert "script-src 'sha256-" in text
    assert "script-src 'unsafe-inline'" not in text
    assert "Nenhum treinamento é executado pelo HTML" in text
