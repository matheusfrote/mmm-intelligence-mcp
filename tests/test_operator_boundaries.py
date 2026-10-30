"""Operator failures remain local and offline reconciliation refuses ambiguous batches."""

import json
from importlib.metadata import PackageNotFoundError

import pytest

from mmm_intelligence import cli
from mmm_intelligence.config import Settings
from mmm_intelligence.connectors import SourceBatch, reconcile_batches


@pytest.mark.parametrize(
    "changes",
    [
        {"max_rows": 51},
        {"max_rows": 100001},
        {"max_file_bytes": 1023},
        {"max_file_bytes": 104857601},
        {"log_level": "TRACE"},
    ],
)
def test_host_configuration_limits_cannot_be_bypassed(tmp_path, changes):
    with pytest.raises(ValueError):
        Settings(tmp_path, **changes)


def test_doctor_missing_package_is_explicit_and_returns_failure(monkeypatch, capsys):
    original = cli.version

    def version(name):
        if name == "numpy":
            raise PackageNotFoundError(name)
        return original(name)

    monkeypatch.setattr(cli, "version", version)
    assert cli.main(["doctor"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["dependencies"]["numpy"] is None
    assert report["base_runtime_ok"] is False


@pytest.mark.parametrize(
    "arguments", [["dashboard", "--port", "0"], ["dashboard", "--port", "65536"]]
)
def test_cli_refuses_invalid_listener_port(arguments):
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    assert error.value.code == 2


def test_cli_delete_needs_existing_explicit_root(tmp_path):
    with pytest.raises(SystemExit) as error:
        cli.main(
            [
                "delete-artifact",
                "--data-dir",
                str(tmp_path / "absent"),
                "--kind",
                "reports",
                "--id",
                "test",
                "--sha256",
                "0" * 64,
            ]
        )
    assert error.value.code == 2 and not (tmp_path / "absent").exists()


def batch(**changes):
    return SourceBatch(
        **{
            "source": "sales",
            "source_version": "1",
            "currency": "BRL",
            "timezone": "UTC",
            "grain": ["id"],
            "watermark": "2026-01-01",
            "records": [{"id": "one", "sales": 10}],
            "reported_totals": {"sales": 10},
            "authorization_reference": "synthetic fixture",
            "synthetic": True,
            **changes,
        }
    )


@pytest.mark.parametrize(
    "batches,tolerance", [([], 1e-6), ([batch()] * 101, 1e-6), ([batch()], -0.1), ([batch()], 0.1)]
)
def test_reconciliation_size_and_tolerance_are_bounded(batches, tolerance):
    with pytest.raises(ValueError):
        reconcile_batches(batches, tolerance)


@pytest.mark.parametrize(
    "change",
    [
        {"currency": "USD"},
        {"timezone": "-03:00"},
        {"grain": ["id", "region"]},
        {"synthetic": False},
        {"reported_totals": {"spend": 10}},
    ],
)
def test_mixed_batch_scopes_never_issue_receipt(change):
    with pytest.raises(ValueError):
        reconcile_batches([batch(), batch(**change)])


@pytest.mark.parametrize(
    "change",
    [
        {"grain": ["id", "id"]},
        {"records": [{"id": True, "sales": 10}]},
        {"records": [{"sales": 10}]},
        {"records": [{"id": "one", "sales": True}]},
        {"records": [{"id": "one", "sales": float("nan")}]},
        {"records": [{"id": "one", "sales": 1e13}]},
        {"reported_totals": {"sales": 11}},
    ],
)
def test_invalid_grain_or_unreconciled_metrics_fail_closed(change):
    with pytest.raises(ValueError):
        reconcile_batches([batch(**change)])


def test_reconciliation_global_limit_spans_pages():
    first = batch(
        records=[{"id": str(i), "sales": 1} for i in range(10000)], reported_totals={"sales": 10000}
    )
    second = batch(records=[{"id": "next", "sales": 1}], reported_totals={"sales": 1})
    with pytest.raises(ValueError, match="row limit"):
        reconcile_batches([first, second])
