from __future__ import annotations

from collections import Counter
from typing import Any

from academic_portfolio.resolver import PortfolioResolver
from academic_portfolio.view_records import resolved_records


def _tagged_publication_records(
    resolver: PortfolioResolver,
    file_path: str,
    group: str,
    publication_kind: str,
    *,
    reverse: bool,
) -> list[dict[str, Any]]:
    records = resolved_records(resolver, file_path, group, reverse=reverse)
    for record in records:
        record["publication_kind"] = publication_kind
    return records


def _publication_year_chart(
    journal_papers: list[dict[str, Any]],
    conference_papers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    journal_counts = _year_counts(journal_papers, "publication_date")
    conference_counts = _year_counts(conference_papers, "publication_date")
    years = sorted(set(journal_counts) | set(conference_counts), reverse=True)
    if not years:
        return []

    max_count = max(journal_counts[year] + conference_counts[year] for year in years)
    return [
        {
            "year": year,
            "journal_count": journal_counts[year],
            "conference_count": conference_counts[year],
            "total": journal_counts[year] + conference_counts[year],
            "height": round(((journal_counts[year] + conference_counts[year]) / max_count) * 100),
            "journal_share": round((journal_counts[year] / (journal_counts[year] + conference_counts[year])) * 100),
            "conference_share": round(
                (conference_counts[year] / (journal_counts[year] + conference_counts[year])) * 100
            ),
        }
        for year in years
    ]


def _publication_year_groups(publications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for publication in publications:
        year = _publication_year(publication)
        groups.setdefault(year, []).append(publication)

    return [
        {
            "year": year,
            "publications": groups[year],
            "count": len(groups[year]),
        }
        for year in sorted(groups, reverse=True)
    ]


def _publication_year(publication: dict[str, Any]) -> str:
    publication_date = str(publication.get("publication_date") or "")
    return publication_date[:4] if len(publication_date) >= 4 else "n.d."


def _year_counts(records: list[dict[str, Any]], date_field: str) -> Counter[str]:
    return Counter(
        str(record.get(date_field))[:4]
        for record in records
        if record.get(date_field)
    )
