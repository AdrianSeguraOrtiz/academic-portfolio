from __future__ import annotations

from typing import Any

from academic_portfolio.resolver import PortfolioResolver


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
    for record in records:
        record_id = record.get("id")
        record[target_field] = [
            related_record
            for related_record in related_records
            if record_id and record_id in related_record.get(reference_field, [])
        ]


def sort_records_by_field(
    records: list[dict[str, Any]],
    field: str,
    *,
    reverse: bool,
) -> list[dict[str, Any]]:
    return sorted(records, key=lambda record: str(record.get(field) or ""), reverse=reverse)
