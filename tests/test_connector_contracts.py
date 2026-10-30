import pytest


def test_source_contract_reconciles_without_network_or_credentials():
    from mmm_intelligence.connectors import SourceBatch, reconcile_batches

    batch = SourceBatch(
        source="sales",
        source_version="1",
        currency="BRL",
        timezone="UTC",
        grain=["date", "channel"],
        watermark="2026-01-03",
        records=[
            {"date": "2026-01-01", "channel": "search", "spend": 10.0},
            {"date": "2026-01-02", "channel": "search", "spend": 20.0},
        ],
        reported_totals={"spend": 30.0},
        authorization_reference="synthetic-test",
        synthetic=True,
    )
    result = reconcile_batches([batch])
    assert result["totals"]["spend"] == 30.0
    assert result["record_count"] == 2
    assert result["source_authenticated"] is False
    assert result["receipt_sha256"]
    with pytest.raises(ValueError, match="Duplicate"):
        reconcile_batches([batch, batch])
    with pytest.raises(ValueError, match="reconcile"):
        reconcile_batches([batch.model_copy(update={"reported_totals": {"spend": 40.0}})])
    with pytest.raises(ValueError, match="currency"):
        reconcile_batches([batch, batch.model_copy(update={"currency": "USD"})])


def test_connector_registry_does_not_advertise_live_integrations():
    from mmm_intelligence.connectors import connector_status

    status = connector_status()
    assert len(status) == 10
    assert all(v["live_verified"] is False for v in status.values())
