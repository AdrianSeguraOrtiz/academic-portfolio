from pathlib import Path

from academic_portfolio.loader import load_data
from academic_portfolio.resolver import PortfolioResolver
from academic_portfolio.view_records import (
    attach_related_records,
    profile_with_current_activity,
    records_by_reference,
    reference_values,
)


def test_profile_with_current_activity_resolves_references() -> None:
    loaded_data = load_data(Path("data"))
    resolver = PortfolioResolver(loaded_data)
    source_profile = loaded_data.documents["profile.yaml"]

    profile = profile_with_current_activity(resolver)

    assert [position["id"] for position in profile["current_positions"]] == source_profile[
        "current_position_ids"
    ]
    assert [stay["id"] for stay in profile["current_stays"]] == source_profile["current_stay_ids"]
    assert profile["current_positions"][0]["resolved"]["organization_ids"]


def test_records_by_reference_indexes_many_to_many_relationships() -> None:
    records = [
        {"id": "grant_01", "position_ids": ["position_01", "position_02"]},
        {"id": "grant_02", "position_ids": ["position_02"]},
    ]

    indexed = records_by_reference(records, "position_ids")

    assert [record["id"] for record in indexed["position_01"]] == ["grant_01"]
    assert [record["id"] for record in indexed["position_02"]] == ["grant_01", "grant_02"]


def test_reference_values_accepts_list_scalar_and_empty_values() -> None:
    assert reference_values({"organization_ids": ["organization_01"]}, "organization_ids") == [
        "organization_01"
    ]
    assert reference_values({"parent_organization_id": "organization_01"}, "parent_organization_id") == [
        "organization_01"
    ]
    assert reference_values({"parent_organization_id": None}, "parent_organization_id") == []


def test_attach_related_records_uses_reference_index() -> None:
    records = [{"id": "degree_01"}, {"id": "degree_02"}]
    honors = [
        {"id": "award_01", "degree_ids": ["degree_02"]},
        {"id": "award_02", "degree_ids": ["degree_01"]},
    ]

    attach_related_records(records, honors, "degree_ids", "related_honors")

    assert [record["id"] for record in records[0]["related_honors"]] == ["award_02"]
    assert [record["id"] for record in records[1]["related_honors"]] == ["award_01"]
