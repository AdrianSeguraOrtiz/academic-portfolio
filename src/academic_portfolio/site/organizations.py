from __future__ import annotations

from collections import Counter
from typing import Any

from academic_portfolio.site.common import (
    _float_percentage,
    _month_span,
    _month_span_to_present,
)

ORGANIZATION_RELATIONSHIP_TYPES = [
    {"id": "education", "label": "Education", "short": "edu", "unit": "months"},
    {"id": "experience", "label": "Experience", "short": "exp", "unit": "months"},
    {"id": "stays", "label": "Research stays", "short": "stay", "unit": "months"},
    {"id": "publications", "label": "Publications", "short": "pub", "unit": "papers"},
    {"id": "teaching", "label": "Teaching", "short": "teach", "unit": "activities"},
]



def _organization_network_view(
    *,
    organizations: list[dict[str, Any]],
    degrees: list[dict[str, Any]],
    experience: list[dict[str, Any]],
    research_stays: list[dict[str, Any]],
    publications: list[dict[str, Any]],
    university_classes: list[dict[str, Any]],
    academic_supervision: list[dict[str, Any]],
) -> dict[str, Any]:
    organizations_by_id = {
        str(organization.get("id")): organization
        for organization in organizations
        if organization.get("id")
    }
    children_by_parent: dict[str | None, list[str]] = {}
    for organization in organizations:
        organization_id = str(organization.get("id") or "")
        parent_id = organization.get("parent_organization_id")
        parent_key = str(parent_id) if parent_id else None
        children_by_parent.setdefault(parent_key, []).append(organization_id)

    relationship_ids = [item["id"] for item in ORGANIZATION_RELATIONSHIP_TYPES]
    direct_values = {
        relationship_id: Counter(
            {organization_id: 0.0 for organization_id in organizations_by_id}
        )
        for relationship_id in relationship_ids
    }

    def add_duration(record: dict[str, Any], relationship_id: str, value: int) -> None:
        if value <= 0:
            return
        for organization_id in _specific_organization_ids(record, organizations_by_id):
            direct_values[relationship_id][organization_id] += float(value)

    for degree in degrees:
        add_duration(
            degree,
            "education",
            _month_span_to_present(degree.get("start_date"), degree.get("end_date")),
        )

    for position in experience:
        add_duration(
            position,
            "experience",
            _month_span_to_present(position.get("start_date"), position.get("end_date")),
        )

    for stay in research_stays:
        add_duration(
            stay,
            "stays",
            _month_span_to_present(stay.get("start_date"), stay.get("end_date")),
        )

    for publication in publications:
        organization_ids = _specific_organization_ids(publication, organizations_by_id)
        if not organization_ids:
            continue

        share = 1.0 / len(organization_ids)
        for organization_id in organization_ids:
            direct_values["publications"][organization_id] += share

    for course in university_classes:
        add_duration(
            course,
            "teaching",
            _month_span(course.get("start_date"), course.get("end_date")),
        )

    for supervision in academic_supervision:
        add_duration(supervision, "teaching", 1)

    aggregate_values: dict[str, dict[str, float]] = {
        relationship_id: {}
        for relationship_id in relationship_ids
    }

    def aggregate_for(relationship_id: str, organization_id: str) -> float:
        relationship_values = aggregate_values[relationship_id]
        if organization_id in relationship_values:
            return relationship_values[organization_id]

        value = float(direct_values[relationship_id].get(organization_id, 0.0))
        for child_id in children_by_parent.get(organization_id, []):
            value += aggregate_for(relationship_id, child_id)

        relationship_values[organization_id] = value
        return value

    for relationship_id in relationship_ids:
        for organization_id in organizations_by_id:
            aggregate_for(relationship_id, organization_id)

    root_ids = [
        organization_id
        for organization_id, organization in organizations_by_id.items()
        if not organization.get("parent_organization_id")
        or str(organization.get("parent_organization_id")) not in organizations_by_id
    ]

    rows = [
        _organization_relationship_row(
            relationship,
            root_ids,
            organizations_by_id,
            children_by_parent,
            aggregate_values[relationship["id"]],
        )
        for relationship in ORGANIZATION_RELATIONSHIP_TYPES
    ]
    rows = [row for row in rows if row["total"] > 0]
    if not rows:
        return {
            "rows": [],
            "cards": [],
            "relationship_types": ORGANIZATION_RELATIONSHIP_TYPES,
            "metrics": {"organizations": 0, "countries": 0, "cities": 0},
        }

    cards = _organization_card_groups(
        organizations_by_id,
        children_by_parent,
        aggregate_values,
        relationship_ids,
        root_ids,
    )
    visible_nodes = list(
        _flatten_organization_nodes(
            [
                node
                for row in rows
                for country in row["countries"]
                for node in country["nodes"]
            ]
        )
    )
    return {
        "rows": rows,
        "cards": cards,
        "relationship_types": ORGANIZATION_RELATIONSHIP_TYPES,
        "metrics": {
            "organizations": len({node["id"] for node in visible_nodes}),
            "countries": len({country["country"] for row in rows for country in row["countries"]}),
            "cities": len(
                {
                    node["city"]
                    for node in visible_nodes
                    if node.get("city")
                }
            ),
        },
    }



def _specific_organization_ids(
    record: dict[str, Any],
    organizations_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    organization_ids = [
        str(organization_id)
        for organization_id in record.get("organization_ids", [])
        if str(organization_id) in organizations_by_id
    ]
    if not organization_ids:
        return []

    return [
        organization_id
        for organization_id in organization_ids
        if not any(
            organization_id != other_id
            and _organization_is_ancestor(organization_id, other_id, organizations_by_id)
            for other_id in organization_ids
        )
    ]



def _organization_is_ancestor(
    possible_ancestor_id: str,
    organization_id: str,
    organizations_by_id: dict[str, dict[str, Any]],
) -> bool:
    parent_id = organizations_by_id.get(organization_id, {}).get("parent_organization_id")
    seen: set[str] = set()
    while parent_id:
        parent_text = str(parent_id)
        if parent_text in seen:
            return False
        if parent_text == possible_ancestor_id:
            return True
        seen.add(parent_text)
        parent_id = organizations_by_id.get(parent_text, {}).get("parent_organization_id")
    return False



def _organization_relationship_row(
    relationship: dict[str, str],
    root_ids: list[str],
    organizations_by_id: dict[str, dict[str, Any]],
    children_by_parent: dict[str | None, list[str]],
    values_by_organization: dict[str, float],
) -> dict[str, Any]:
    relationship_id = relationship["id"]
    root_nodes = [
        _organization_relationship_node(
            root_id,
            relationship,
            organizations_by_id,
            children_by_parent,
            values_by_organization,
            parent_value=0.0,
        )
        for root_id in root_ids
    ]
    root_nodes = [node for node in root_nodes if node]
    countries_by_name: dict[str, list[dict[str, Any]]] = {}
    for node in root_nodes:
        countries_by_name.setdefault(str(node["country"]), []).append(node)

    countries = []
    total = sum(float(node["value"]) for node in root_nodes)
    for country, nodes in countries_by_name.items():
        nodes = sorted(nodes, key=lambda node: (-float(node["value"]), str(node["label"])))
        country_total = sum(float(node["value"]) for node in nodes)
        for node in nodes:
            node["share"] = _float_percentage(float(node["value"]), country_total)

        country_share = _float_percentage(country_total, total)
        for node in nodes:
            _set_node_display_styles(node, country_share)
        countries.append(
            {
                "country": country,
                "value": country_total,
                "value_label": _organization_metric_value_label(relationship_id, country_total),
                "share": country_share,
                "global_share": country_share,
                "style": f"--country-share: {country_share}%;",
                "size_class": _relationship_segment_size_class(country_share),
                "children_style": _relationship_lane_stack_style(0),
                "nodes": nodes,
            }
        )
    countries = sorted(
        countries,
        key=lambda item: (-float(item["value"]), str(item["country"])),
    )
    max_country_label_lane = _assign_relationship_label_lanes(countries)
    _assign_relationship_tree_label_lanes(countries)

    return {
        **relationship,
        "total": total,
        "total_label": _organization_metric_value_label(relationship_id, total),
        "track_style": _relationship_lane_stack_style(max_country_label_lane),
        "countries": countries,
    }



def _organization_relationship_node(
    organization_id: str,
    relationship: dict[str, str],
    organizations_by_id: dict[str, dict[str, Any]],
    children_by_parent: dict[str | None, list[str]],
    values_by_organization: dict[str, float],
    *,
    parent_value: float,
    depth: int = 0,
    path: list[str] | None = None,
) -> dict[str, Any] | None:
    value = float(values_by_organization.get(organization_id, 0.0))
    if value <= 0:
        return None

    organization = organizations_by_id[organization_id]
    label = _organization_label(organization)
    location = organization.get("location", {}) or {}
    node_path = [*(path or []), label]
    child_nodes = [
        _organization_relationship_node(
            child_id,
            relationship,
            organizations_by_id,
            children_by_parent,
            values_by_organization,
            parent_value=value,
            depth=depth + 1,
            path=node_path,
        )
        for child_id in children_by_parent.get(organization_id, [])
    ]
    child_nodes = [node for node in child_nodes if node]
    return {
        "id": organization_id,
        "name": str(organization.get("name") or label),
        "label": label,
        "full_name": str(organization.get("full_name") or organization.get("name") or label),
        "type": str(organization.get("type") or ""),
        "website": str(organization.get("website") or ""),
        "country": str(location.get("country") or "Unknown"),
        "city": str(location.get("city") or ""),
        "depth": depth,
        "path": node_path,
        "path_label": " > ".join(node_path),
        "value": value,
        "value_label": _organization_metric_value_label(relationship["id"], value),
        "share": _float_percentage(value, parent_value) if parent_value else 0.0,
        "style": "",
        "tooltip": (
            f"{label}\n{relationship['label']}: "
            f"{_organization_metric_value_label(relationship['id'], value)}"
        ),
        "children": sorted(
            child_nodes,
            key=lambda child: (-float(child["value"]), str(child["label"])),
        ),
    }



def _set_node_display_styles(node: dict[str, Any], parent_global_share: float) -> None:
    node["global_share"] = parent_global_share * float(node.get("share") or 0.0) / 100.0
    node["style"] = f"--node-share: {node['share']}%;"
    node["size_class"] = _relationship_segment_size_class(float(node["share"]))
    parent_value = float(node["value"])
    for child in node.get("children", []):
        child["share"] = _float_percentage(float(child["value"]), parent_value)
        _set_node_display_styles(child, float(node["global_share"]))
    node["children_style"] = _relationship_lane_stack_style(0)



def _assign_relationship_tree_label_lanes(countries: list[dict[str, Any]]) -> None:
    max_lanes_by_depth: dict[int, int] = {}

    def assign_group(items: list[dict[str, Any]], depth: int) -> None:
        if not items:
            return
        max_lanes_by_depth[depth] = max(
            max_lanes_by_depth.get(depth, 0),
            _assign_relationship_label_lanes(items),
        )
        for item in items:
            assign_group(item.get("children", []), depth + 1)

    for country in countries:
        assign_group(country["nodes"], 0)

    for country in countries:
        country["children_style"] = _relationship_lane_stack_style(
            max_lanes_by_depth.get(0, 0)
        )
        for node in country["nodes"]:
            _set_relationship_tree_stack_style(node, max_lanes_by_depth)



def _set_relationship_tree_stack_style(
    node: dict[str, Any],
    max_lanes_by_depth: dict[int, int],
) -> None:
    node["children_style"] = _relationship_lane_stack_style(
        max_lanes_by_depth.get(int(node["depth"]) + 1, 0)
    )
    for child in node.get("children", []):
        _set_relationship_tree_stack_style(child, max_lanes_by_depth)



def _relationship_segment_size_class(share: float) -> str:
    if share < 9:
        return "is-tiny"
    if share < 18:
        return "is-small"
    return "is-regular"



def _assign_relationship_label_lanes(items: list[dict[str, Any]]) -> int:
    lane_ends: list[float] = []
    position = 0.0
    max_lane = 0
    container_global_share = sum(float(item.get("global_share") or 0.0) for item in items)
    if container_global_share <= 0:
        container_global_share = 100.0
    for item in items:
        share = float(item.get("share") or 0)
        start = position
        end = position + share
        label_text = " ".join(
            str(part)
            for part in (
                item.get("label") or item.get("country"),
                item.get("value_label"),
            )
            if part
        )
        label_width_global = min(38.0, max(12.0, len(label_text) * 0.72))
        label_width = min(
            96.0,
            max(12.0, (label_width_global / container_global_share) * 100.0),
        )
        if item.get("size_class") in {"is-small", "is-tiny"}:
            label_start = ((start + end) / 2) - (label_width / 2)
        else:
            label_start = start + 0.35
        label_start = max(0.0, min(label_start, max(0.0, 100.0 - label_width)))
        label_end = label_start + label_width

        lane = 0
        while lane < len(lane_ends) and label_start < lane_ends[lane] + 1.2:
            lane += 1
        if lane == len(lane_ends):
            lane_ends.append(label_end)
        else:
            lane_ends[lane] = label_end

        max_lane = max(max_lane, lane)
        item["label_lane"] = lane
        item["style"] = (
            f"{item.get('style', '')} "
            f"--label-lane: {lane}; --label-lane-offset: {lane * 34}px;"
        )
        position = end
    return max_lane



def _relationship_lane_stack_style(max_lane: int) -> str:
    return f"--max-label-lane: {max_lane}; --label-stack-offset: {max_lane * 34}px;"



def _organization_label(organization: dict[str, Any]) -> str:
    return str(organization.get("abbreviation") or organization.get("name") or organization.get("id") or "")



def _organization_metric_badges(metrics: dict[str, float]) -> list[dict[str, str]]:
    badges = []
    for relationship in ORGANIZATION_RELATIONSHIP_TYPES:
        relationship_id = relationship["id"]
        value = float(metrics.get(relationship_id, 0.0))
        if value <= 0:
            continue
        badges.append(
            {
                "id": relationship_id,
                "label": relationship["label"],
                "short": relationship["short"],
                "value": _organization_metric_compact_value(value),
                "value_label": _organization_metric_value_label(relationship_id, value),
            }
        )
    return badges



def _organization_metric_value_label(relationship_id: str, value: float) -> str:
    value_label = _organization_metric_compact_value(value)
    if relationship_id in {"education", "experience", "stays", "teaching"}:
        unit = "month" if value == 1 else "months"
        return f"{value_label} {unit}"
    if relationship_id == "publications":
        unit = "paper" if value == 1 else "papers"
        return f"{value_label} {unit}"
    return value_label



def _organization_metric_compact_value(value: float) -> str:
    if abs(value - round(value)) < 0.001:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")



def _flatten_organization_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for node in nodes:
        flattened.append(node)
        flattened.extend(_flatten_organization_nodes(node.get("children", [])))
    return flattened



def _organization_card_groups(
    organizations_by_id: dict[str, dict[str, Any]],
    children_by_parent: dict[str | None, list[str]],
    aggregate_values: dict[str, dict[str, float]],
    relationship_ids: list[str],
    root_ids: list[str],
) -> list[dict[str, Any]]:
    card_nodes = [
        _organization_card_node(
            root_id,
            organizations_by_id,
            children_by_parent,
            aggregate_values,
            relationship_ids,
        )
        for root_id in root_ids
    ]
    card_nodes = [node for node in card_nodes if node]
    city_groups_by_country: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for node in _flatten_organization_nodes(card_nodes):
        city_groups_by_country.setdefault(str(node["country"]), {}).setdefault(
            str(node.get("city") or "Unspecified"),
            [],
        ).append(node)

    return [
        {
            "country": country,
            "cities": [
                {
                    "city": city,
                    "organizations": sorted(
                        organizations,
                        key=lambda node: (int(node["depth"]), str(node["label"])),
                    ),
                }
                for city, organizations in sorted(city_groups.items())
            ],
        }
        for country, city_groups in sorted(city_groups_by_country.items())
    ]



def _organization_card_node(
    organization_id: str,
    organizations_by_id: dict[str, dict[str, Any]],
    children_by_parent: dict[str | None, list[str]],
    aggregate_values: dict[str, dict[str, float]],
    relationship_ids: list[str],
    *,
    depth: int = 0,
    path: list[str] | None = None,
) -> dict[str, Any] | None:
    metrics = {
        relationship_id: float(aggregate_values[relationship_id].get(organization_id, 0.0))
        for relationship_id in relationship_ids
    }
    child_nodes = [
        _organization_card_node(
            child_id,
            organizations_by_id,
            children_by_parent,
            aggregate_values,
            relationship_ids,
            depth=depth + 1,
            path=[*(path or []), _organization_label(organizations_by_id[organization_id])],
        )
        for child_id in children_by_parent.get(organization_id, [])
    ]
    child_nodes = [node for node in child_nodes if node]
    if not any(value > 0 for value in metrics.values()) and not child_nodes:
        return None

    organization = organizations_by_id[organization_id]
    label = _organization_label(organization)
    location = organization.get("location", {}) or {}
    node_path = [*(path or []), label]
    return {
        "id": organization_id,
        "name": str(organization.get("name") or label),
        "label": label,
        "full_name": str(organization.get("full_name") or organization.get("name") or label),
        "type": str(organization.get("type") or ""),
        "website": str(organization.get("website") or ""),
        "country": str(location.get("country") or "Unknown"),
        "city": str(location.get("city") or ""),
        "depth": depth,
        "path_label": " > ".join(node_path),
        "metrics": _organization_metric_badges(metrics),
        "children": sorted(child_nodes, key=lambda child: str(child["label"])),
    }
