from __future__ import annotations

from datetime import date
from typing import Any

from academic_portfolio.render import date_range, record_name
from academic_portfolio.view_records import records_by_reference

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
