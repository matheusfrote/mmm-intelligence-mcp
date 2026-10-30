"""Join checks prevent multiplication of spend and retain explicit lineage."""

import pytest
from test_universal import call, source


def normalized(service, text):
    raw = source(service, text)
    header = text.splitlines()[0].split(",")
    return call(
        service,
        "map_dataset_schema",
        source_id=raw["artifact_id"],
        profile="website",
        mapping={c: c for c in header},
        units={c: "BRL" if c == "spend" else "count" for c in header if c != "date"},
        dimensions={"channel": "fixture", "strategy": "paid"},
    )


@pytest.mark.parametrize("how,expected", [("inner", 1), ("left", 2), ("right", 2), ("full", 3)])
def test_join_preview_confirmation_and_unmatched(service, how, expected):
    left = normalized(service, "date,spend\n2026-01-01,10\n2026-01-08,20\n")
    right = normalized(service, "date,sales\n2026-01-08,4\n2026-01-15,5\n")
    args = dict(
        left_id=left["artifact_id"],
        right_id=right["artifact_id"],
        keys={"date": "date"},
        how=how,
        cardinality="1:1",
    )
    preview = call(service, "join_datasets", **args)
    assert (
        preview["output_rows"] == expected
        and preview["unmatched_left"] == 1
        and preview["unmatched_right"] == 1
    )
    joined = call(service, "join_datasets", **args, confirm=True)
    assert len(joined["rows"]) == expected and joined["source_ids"] == [
        left["artifact_id"],
        right["artifact_id"],
    ]
    assert sum(r["spend"] for r in joined["rows"] if r["spend"] is not None) == (
        20 if how in {"inner", "right"} else 30
    )


def test_many_to_many_spend_duplication_is_blocked(service):
    left = normalized(service, "date,spend\n2026-01-01,10\n2026-01-01,20\n")
    right = normalized(service, "date,sales\n2026-01-01,1\n2026-01-01,2\n")
    args = dict(
        left_id=left["artifact_id"],
        right_id=right["artifact_id"],
        keys={"date": "date"},
        cardinality="m:m",
    )
    preview = call(service, "join_datasets", **args)
    assert preview["blocked"] and preview["output_rows"] == 4
    assert not service.call("join_datasets", args | {"confirm": True}).ok


def test_declared_preaggregation_removes_multiplication(service):
    left = normalized(service, "date,spend\n2026-01-01,10\n2026-01-01,20\n")
    right = normalized(service, "date,sales\n2026-01-01,2\n")
    joined = call(
        service,
        "join_datasets",
        left_id=left["artifact_id"],
        right_id=right["artifact_id"],
        keys={"date": "date"},
        cardinality="1:1",
        left_aggregations={"spend": "sum"},
        confirm=True,
    )
    assert joined["rows"] == [{"date": "2026-01-01", "spend": 30, "sales": 2}]


def test_join_keeps_nonconflicting_outcome_context(service):
    left = normalized(service, "date,spend\n2026-01-01,10\n")
    right = normalized(service, "date,sales\n2026-01-01,2\n")
    left["dimensions"]["kpi_definition"] = "confirmed commercial sales"
    # Create a new immutable source version with the additional declaration.
    left = service._growth_save("normalized", left)
    result = call(
        service,
        "join_datasets",
        left_id=left["artifact_id"],
        right_id=right["artifact_id"],
        keys={"date": "date"},
        confirm=True,
    )
    assert result["dimensions"]["kpi_definition"] == "confirmed commercial sales"


def test_joined_dataset_is_consumed_by_growth_builder_without_losing_parents(service):
    left = normalized(service, "date,spend\n2026-01-05,10\n2026-01-12,20\n")
    right = normalized(service, "date,sales\n2026-01-05,2\n2026-01-12,3\n")
    joined = call(
        service,
        "join_datasets",
        left_id=left["artifact_id"],
        right_id=right["artifact_id"],
        keys={"date": "date"},
        confirm=True,
    )
    result = call(
        service,
        "build_growth_dataset",
        artifact_ids=[joined["artifact_id"]],
        aggregations={"spend": "sum", "sales": "sum"},
    )
    assert result["source_ids"] == [joined["artifact_id"]]
    assert result["observations"][0]["source_ids"] == [left["artifact_id"], right["artifact_id"]]
    assert sum(row["values"]["spend"] for row in result["observations"]) == 30
