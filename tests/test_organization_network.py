from typing import Any

from academic_portfolio.site.organizations import _organization_network_view


def _flatten_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for node in nodes:
        flattened.append(node)
        flattened.extend(_flatten_nodes(node.get("children", [])))
    return flattened


def _row_nodes(row: dict[str, Any]) -> list[dict[str, Any]]:
    return _flatten_nodes(
        [node for country in row["countries"] for node in country["nodes"]]
    )


def test_organization_network_aggregates_parent_child_relationships() -> None:
    organizations = [
        {
            "id": "organization_01",
            "name": "Root University",
            "abbreviation": "ROOT",
            "location": {"country": "Country A", "city": "City A"},
        },
        {
            "id": "organization_02",
            "name": "Child Institute",
            "abbreviation": "CHILD",
            "parent_organization_id": "organization_01",
            "location": {"country": "Country A", "city": "City A"},
        },
    ]

    view = _organization_network_view(
        organizations=organizations,
        degrees=[
            {
                "id": "degree_01",
                "organization_ids": ["organization_01"],
                "start_date": "2020-01-01",
                "end_date": "2020-12-31",
            }
        ],
        experience=[
            {
                "id": "position_01",
                "organization_ids": ["organization_02"],
                "start_date": "2021-01-01",
                "end_date": "2021-12-31",
            }
        ],
        research_stays=[],
        publications=[
            {
                "id": "publication_01",
                "organization_ids": ["organization_01", "organization_02"],
            }
        ],
        university_classes=[],
        academic_supervision=[],
    )

    rows = {row["id"]: row for row in view["rows"]}

    experience_nodes = {node["id"]: node for node in _row_nodes(rows["experience"])}
    assert experience_nodes["organization_01"]["value"] == 12
    assert experience_nodes["organization_02"]["value"] == 12
    assert experience_nodes["organization_02"]["path_label"] == "ROOT > CHILD"

    publication_nodes = {node["id"]: node for node in _row_nodes(rows["publications"])}
    assert rows["publications"]["total"] == 1
    assert publication_nodes["organization_01"]["value"] == 1
    assert publication_nodes["organization_02"]["value"] == 1
