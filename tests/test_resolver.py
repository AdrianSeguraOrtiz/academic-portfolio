from pathlib import Path

import pytest

from academic_portfolio.loader import LoadedData, load_data
from academic_portfolio.resolver import DuplicateRecordIdError, PortfolioResolver


def test_resolver_builds_id_index() -> None:
    resolver = PortfolioResolver(load_data(Path("data")))

    organization = resolver.resolve("organization_01")

    assert organization["name"] == "Universidad de Málaga"
    assert resolver.pointer("organization_01").file_path == "entities/organizations.yaml"


def test_resolver_resolves_profile_current_activity() -> None:
    loaded_data = load_data(Path("data"))
    resolver = PortfolioResolver(loaded_data)
    profile = loaded_data.documents["profile.yaml"]

    current_positions = resolver.resolve_many(profile["current_position_ids"])
    current_stays = resolver.resolve_many(profile["current_stay_ids"])

    assert [position["id"] for position in current_positions] == profile["current_position_ids"]
    assert [stay["id"] for stay in current_stays] == profile["current_stay_ids"]


def test_resolver_resolves_publication_relationships() -> None:
    resolver = PortfolioResolver(load_data(Path("data")))
    publication = resolver.resolve("publication_04")

    references = resolver.references_for(publication)

    assert [record["id"] for record in references["software_project_ids"]] == ["software_10"]
    assert [record["id"] for record in references["stay_ids"]] == ["stay_01"]
    assert [record["id"] for record in references["grant_ids"]] == ["grant_01", "grant_02"]
    assert "organization_11" in [record["id"] for record in references["organization_ids"]]


def test_resolver_resolves_parent_organization_relationships() -> None:
    resolver = PortfolioResolver(load_data(Path("data")))
    organization = resolver.resolve("organization_03")

    references = resolver.references_for(organization)

    assert [record["id"] for record in references["parent_organization_id"]] == ["organization_06"]


def test_resolver_resolves_research_stay_grants() -> None:
    resolver = PortfolioResolver(load_data(Path("data")))
    stay = resolver.resolve("stay_01")

    references = resolver.references_for(stay)

    assert [record["id"] for record in references["grant_ids"]] == ["grant_02"]
    assert [record["id"] for record in references["origin_position_ids"]] == ["position_04"]


def test_resolver_rejects_duplicate_ids() -> None:
    loaded_data = LoadedData(
        root=Path("data"),
        documents={
            "one.yaml": {"items": [{"id": "item_01"}]},
            "two.yaml": {"items": [{"id": "item_01"}]},
        },
    )

    with pytest.raises(DuplicateRecordIdError):
        PortfolioResolver(loaded_data)
