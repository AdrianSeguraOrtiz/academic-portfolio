from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from academic_portfolio.render import date_range, record_name
from academic_portfolio.view_records import records_by_reference


def _career_details_view(
    degrees: list[dict[str, Any]],
    experience: list[dict[str, Any]],
    research_stays: list[dict[str, Any]],
    certifications: list[dict[str, Any]],
    honors: list[dict[str, Any]],
    grants: list[dict[str, Any]],
) -> dict[str, Any]:
    filters = [
        {"id": "education", "label": "Education", "count": len(degrees)},
        {"id": "experience", "label": "Experience", "count": len(experience)},
        {"id": "stay", "label": "Stays", "count": len(research_stays)},
        {"id": "certification", "label": "Certifications", "count": len(certifications)},
        {"id": "honor", "label": "Honors", "count": len(honors)},
        {"id": "grant", "label": "Grants", "count": len(grants)},
    ]
    items = [
        *(
            _career_detail_record_item("education", "Education", degree)
            for degree in degrees
        ),
        *_career_detail_organization_groups("experience", "Experience", experience),
        *_career_detail_organization_groups("stay", "Research stay", research_stays),
        *(
            _career_detail_record_item("certification", "Certification", certification)
            for certification in certifications
        ),
        *(
            _career_detail_record_item("honor", "Honor", honor)
            for honor in honors
        ),
        *(
            _career_detail_record_item("grant", "Grant", grant)
            for grant in grants
        ),
    ]
    return {
        "filters": filters,
        "items": sorted(
            items,
            key=lambda item: (item["sort_date"], item["category"], item["title"]),
            reverse=True,
        ),
    }


def _career_detail_record_item(
    category: str,
    category_label: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    return {
        "kind": "record",
        "category": category,
        "category_label": category_label,
        "title": record_name(record),
        "sort_date": _career_detail_sort_date(record),
        "record": record,
    }


def _career_detail_organization_groups(
    category: str,
    category_label: str,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped_records: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    organizations_by_key: dict[str, dict[str, Any]] = {}

    for record in records:
        organization = _career_detail_primary_organization(record)
        organization_key = str(organization.get("id") or "unknown")
        grouped_records[organization_key].append(record)
        organizations_by_key[organization_key] = organization

    groups = []
    for organization_key, group_records in grouped_records.items():
        sorted_records = sorted(
            group_records,
            key=lambda record: _career_detail_sort_date(record),
            reverse=True,
        )
        organization = organizations_by_key[organization_key]
        groups.append(
            {
                "kind": "organization_group",
                "category": category,
                "category_label": category_label,
                "title": _career_detail_organization_label(organization),
                "sort_date": _career_detail_sort_date(sorted_records[0]),
                "organization": organization,
                "records": sorted_records,
                "period": _career_detail_group_period(sorted_records),
                "location": _career_detail_group_location(sorted_records, organization),
                "progression": " <- ".join(record_name(record) for record in sorted_records),
            }
        )
    return groups


def _career_detail_primary_organization(record: dict[str, Any]) -> dict[str, Any]:
    organizations = record.get("resolved", {}).get("organization_ids", [])
    if not organizations:
        return {"id": "unknown", "name": "Unspecified organization"}
    return organizations[-1]


def _career_detail_organization_label(organization: dict[str, Any]) -> str:
    return str(
        organization.get("name")
        or organization.get("full_name")
        or organization.get("abbreviation")
        or "Unspecified organization"
    )


def _career_detail_group_period(records: list[dict[str, Any]]) -> str:
    start_dates = [record.get("start_date") for record in records if record.get("start_date")]
    end_dates = [record.get("end_date") for record in records if record.get("end_date")]
    start_date = min(start_dates) if start_dates else None
    end_date = None if any(not record.get("end_date") for record in records) else max(end_dates, default=None)
    return date_range(start_date, end_date)


def _career_detail_group_location(
    records: list[dict[str, Any]],
    organization: dict[str, Any],
) -> str:
    for record in records:
        location = record.get("location")
        if isinstance(location, str) and location:
            return location
        if isinstance(location, dict):
            location_label = ", ".join(
                str(part)
                for part in (location.get("city"), location.get("country"))
                if part
            )
            if location_label:
                return location_label

    location = organization.get("location", {})
    return ", ".join(
        str(part)
        for part in (location.get("city"), location.get("country"))
        if part
    )


def _career_detail_sort_date(record: dict[str, Any]) -> str:
    return _timeline_date(
        record.get("end_date")
        or record.get("issue_date")
        or record.get("start_date")
        or record.get("date")
    )

def _career_timeline_view(
    degrees: list[dict[str, Any]],
    experience: list[dict[str, Any]],
    research_stays: list[dict[str, Any]],
    certifications: list[dict[str, Any]],
    honors: list[dict[str, Any]],
    grants: list[dict[str, Any]],
) -> dict[str, Any]:
    current_month = date.today().strftime("%Y-%m")
    position_grants = records_by_reference(grants, "position_ids")
    stay_grants = records_by_reference(grants, "stay_ids")
    degree_honors = records_by_reference(honors, "degree_ids")
    items = []
    markers = []
    grants_by_id = {str(grant.get("id")): grant for grant in grants}

    for degree in degrees:
        degree_grants = [
            grants_by_id[str(grant_id)]
            for grant_id in degree.get("grant_ids", [])
            if str(grant_id) in grants_by_id
        ]
        items.append(
            _timeline_duration_item(
                record=degree,
                item_type="education",
                title=degree.get("title"),
                subtitle=", ".join(_timeline_organization_names(degree)),
                start_date=degree.get("start_date"),
                end_date=degree.get("end_date"),
                current_month=current_month,
                grants=degree_grants,
                honors=degree_honors.get(str(degree.get("id")), []),
            )
        )

    for position in experience:
        items.append(
            _timeline_duration_item(
                record=position,
                item_type="experience",
                title=position.get("title"),
                subtitle=", ".join(_timeline_organization_names(position)),
                start_date=position.get("start_date"),
                end_date=position.get("end_date"),
                current_month=current_month,
                grants=position_grants.get(str(position.get("id")), []),
                honors=[],
            )
        )

    for stay in research_stays:
        location = stay.get("location", {})
        location_label = ", ".join(
            part
            for part in (location.get("city"), location.get("country"))
            if part
        )
        organization_label = ", ".join(_timeline_organization_names(stay))
        items.append(
            _timeline_duration_item(
                record=stay,
                item_type="stay",
                title=stay.get("title"),
                subtitle=", ".join(
                    part for part in (organization_label, location_label) if part
                ),
                start_date=stay.get("start_date"),
                end_date=stay.get("end_date"),
                current_month=current_month,
                grants=stay_grants.get(str(stay.get("id")), []),
                honors=[],
            )
        )

    for certification in certifications:
        markers.append(
            _timeline_marker_item(
                record=certification,
                item_type="certification",
                title=certification.get("title"),
                subtitle=", ".join(_timeline_organization_names(certification)),
                marker_date=certification.get("issue_date"),
            )
        )

    for honor in honors:
        markers.append(
            _timeline_marker_item(
                record=honor,
                item_type="honor",
                title=honor.get("title"),
                subtitle=", ".join(honor.get("awarding_entities", [])),
                marker_date=honor.get("issue_date"),
            )
        )

    all_dates = [
        value
        for item in items
        for value in (item["start"], item["end"])
    ] + [marker["date"] for marker in markers]
    return {
        "items": sorted(items, key=lambda item: (item["start"], item["type"], item["title"])),
        "markers": sorted(markers, key=lambda marker: (marker["date"], marker["type"], marker["title"])),
        "range": {
            "start": min(all_dates) if all_dates else _timeline_date(current_month),
            "end": max(all_dates) if all_dates else _timeline_date(current_month),
        },
        "filters": [
            {"id": "education", "label": "Education"},
            {"id": "experience", "label": "Experience"},
            {"id": "stay", "label": "Stays"},
            {"id": "certification", "label": "Certifications"},
            {"id": "honor", "label": "Honors"},
        ],
    }



def _timeline_duration_item(
    *,
    record: dict[str, Any],
    item_type: str,
    title: Any,
    subtitle: str,
    start_date: Any,
    end_date: Any,
    current_month: str,
    grants: list[dict[str, Any]],
    honors: list[dict[str, Any]],
) -> dict[str, Any]:
    visible_end_date = end_date or current_month
    return {
        "id": str(record.get("id") or ""),
        "type": item_type,
        "title": str(title or record_name(record)),
        "subtitle": subtitle,
        "start": _timeline_date(start_date),
        "end": _timeline_date(visible_end_date),
        "start_label": str(start_date or ""),
        "end_label": str(end_date or "Present"),
        "date_label": date_range(start_date, end_date),
        "is_current": end_date in (None, ""),
        "grants": [_timeline_grant(grant) for grant in grants],
        "honors": [_timeline_honor(honor) for honor in honors],
    }



def _timeline_marker_item(
    *,
    record: dict[str, Any],
    item_type: str,
    title: Any,
    subtitle: str,
    marker_date: Any,
) -> dict[str, Any]:
    return {
        "id": str(record.get("id") or ""),
        "type": item_type,
        "title": str(title or record_name(record)),
        "subtitle": subtitle,
        "date": _timeline_date(marker_date),
        "date_label": str(marker_date or ""),
    }



def _timeline_grant(grant: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(grant.get("id") or ""),
        "title": str(grant.get("name") or record_name(grant)),
        "subtitle": str(grant.get("awarding_entity") or ""),
        "date_label": date_range(grant.get("start_date"), grant.get("end_date")),
    }



def _timeline_honor(honor: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(honor.get("id") or ""),
        "title": str(honor.get("title") or record_name(honor)),
        "date_label": str(honor.get("issue_date") or ""),
    }



def _timeline_organization_names(record: dict[str, Any]) -> list[str]:
    return [
        str(organization.get("abbreviation") or organization.get("name"))
        for organization in record.get("resolved", {}).get("organization_ids", [])
        if organization.get("abbreviation") or organization.get("name")
    ]



def _timeline_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return date.today().replace(day=1).isoformat()
    if len(text) == 4:
        return f"{text}-01-01"
    if len(text) == 7:
        return f"{text}-01"
    return text[:10]
