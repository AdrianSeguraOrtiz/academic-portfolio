from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from academic_portfolio.resolver import PortfolioResolver


def profile_with_current_activity(resolver: PortfolioResolver) -> dict[str, Any]:
    profile = dict(resolver.loaded_data.documents["profile.yaml"])
    profile["current_positions"] = resolved_reference_records(
        resolver,
        profile.get("current_position_ids", []),
    )
    profile["current_stays"] = resolved_reference_records(
        resolver,
        profile.get("current_stay_ids", []),
    )
    return profile


def resolved_reference_records(
    resolver: PortfolioResolver,
    record_ids: Sequence[str],
) -> list[dict[str, Any]]:
    return [
        with_resolved_references(resolver, record)
        for record in resolver.resolve_many(record_ids)
    ]


def resolved_records(
    resolver: PortfolioResolver,
    file_path: str,
    group: str,
    *,
    reverse: bool,
) -> list[dict[str, Any]]:
    records = [
        with_resolved_references(resolver, record)
        for record in resolver.records_in_group(file_path, group)
    ]
    return list(reversed(records)) if reverse else records


def with_resolved_references(
    resolver: PortfolioResolver,
    record: dict[str, Any],
) -> dict[str, Any]:
    item = dict(record)
    item["resolved"] = resolver.references_for(record)
    return item


def attach_related_records(
    records: list[dict[str, Any]],
    related_records: list[dict[str, Any]],
    reference_field: str,
    target_field: str,
) -> None:
    related_by_record_id = records_by_reference(related_records, reference_field)
    for record in records:
        record_id = record.get("id")
        record[target_field] = related_by_record_id.get(str(record_id), []) if record_id else []


def records_by_reference(
    records: list[dict[str, Any]],
    reference_field: str,
) -> dict[str, list[dict[str, Any]]]:
    by_reference: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        for record_id in reference_values(record, reference_field):
            by_reference.setdefault(str(record_id), []).append(record)
    return by_reference


def reference_values(record: dict[str, Any], reference_field: str) -> list[Any]:
    value = record.get(reference_field, [])
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return list(value)
    return [value]


def sort_records_by_field(
    records: list[dict[str, Any]],
    field: str,
    *,
    reverse: bool,
) -> list[dict[str, Any]]:
    return sorted(records, key=lambda record: str(record.get(field) or ""), reverse=reverse)
