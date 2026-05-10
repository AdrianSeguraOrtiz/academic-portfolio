from __future__ import annotations

from collections import defaultdict
from math import ceil
from typing import Any

from academic_portfolio.render import date_range, record_name
from academic_portfolio.site.common import _month_number, _year_from_month

TEACHING_ORGANIZATION_COLOR_PALETTE = [
    "#0f766e",
    "#2f7f9f",
    "#8a3342",
    "#a66f21",
    "#6d5fa3",
]


def _teaching_hours_chart(
    university_classes: list[dict[str, Any]],
    organization_legend: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    colors_by_organization_id = {
        str(organization["id"]): str(organization["color"])
        for organization in organization_legend or []
    }
    organizations = _teaching_chart_organizations(university_classes)
    _assign_missing_teaching_chart_colors(organizations, colors_by_organization_id)
    return {
        "legend": _teaching_chart_legend(organizations, colors_by_organization_id),
        "by_academic_year": _teaching_hours_rows(
            university_classes,
            key="academic_year",
            sort_by_value=False,
            colors_by_organization_id=colors_by_organization_id,
        ),
        "by_degree": _teaching_hours_rows(
            university_classes,
            key="degree",
            sort_by_value=True,
            colors_by_organization_id=colors_by_organization_id,
        ),
    }


def _teaching_chart_organizations(records: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    organizations = {}
    for record in records:
        organization = _primary_organization(record)
        organizations[organization["id"]] = organization
    return dict(
        sorted(
            organizations.items(),
            key=lambda item: (item[1]["label"], item[1]["name"], item[1]["id"]),
        )
    )


def _assign_missing_teaching_chart_colors(
    organizations: dict[str, dict[str, str]],
    colors_by_organization_id: dict[str, str],
) -> None:
    for index, organization_id in enumerate(organizations):
        colors_by_organization_id.setdefault(
            organization_id,
            TEACHING_ORGANIZATION_COLOR_PALETTE[
                index % len(TEACHING_ORGANIZATION_COLOR_PALETTE)
            ],
        )


def _teaching_chart_legend(
    organizations: dict[str, dict[str, str]],
    colors_by_organization_id: dict[str, str],
) -> list[dict[str, str]]:
    return [
        {
            "id": organization_id,
            "label": organization["label"],
            "name": organization["name"],
            "color": colors_by_organization_id[organization_id],
        }
        for organization_id, organization in organizations.items()
    ]


def _teaching_hours_rows(
    records: list[dict[str, Any]],
    *,
    key: str,
    sort_by_value: bool,
    colors_by_organization_id: dict[str, str],
) -> list[dict[str, Any]]:
    totals: defaultdict[str, float] = defaultdict(float)
    organization_totals: defaultdict[str, defaultdict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    organizations = _teaching_chart_organizations(records)
    for record in records:
        label = str(record.get(key) or "Unspecified")
        hours = float(record.get("workload_hours") or 0)
        organization_id = _primary_organization(record)["id"]
        totals[label] += hours
        organization_totals[label][organization_id] += hours

    max_hours = max(totals.values(), default=0)
    rows = [
        {
            "label": label,
            "hours": hours,
            "hours_label": _format_teaching_hours(hours),
            "share": round((hours / max_hours) * 100, 2) if max_hours else 0,
            "segments": _teaching_hours_segments(
                organization_totals[label],
                organizations,
                colors_by_organization_id,
                hours,
            ),
        }
        for label, hours in totals.items()
    ]
    if sort_by_value:
        return sorted(rows, key=lambda row: (-row["hours"], row["label"]))
    return sorted(rows, key=lambda row: row["label"])


def _format_teaching_hours(hours: float) -> str:
    if hours.is_integer():
        return f"{int(hours)} h"
    return f"{hours:.1f} h"


def _teaching_hours_segments(
    totals_by_organization_id: dict[str, float],
    organizations: dict[str, dict[str, str]],
    colors_by_organization_id: dict[str, str],
    total_hours: float,
) -> list[dict[str, Any]]:
    return [
        {
            "organization_id": organization_id,
            "label": organizations[organization_id]["label"],
            "hours": hours,
            "hours_label": _format_teaching_hours(hours),
            "share": round((hours / total_hours) * 100, 2) if total_hours else 0,
            "color": colors_by_organization_id[organization_id],
        }
        for organization_id, hours in sorted(
            totals_by_organization_id.items(),
            key=lambda item: organizations[item[0]]["label"],
        )
    ]


def _teaching_timeline_view(
    university_classes: list[dict[str, Any]],
    academic_supervision: list[dict[str, Any]],
) -> dict[str, Any]:
    records = [
        _teaching_event(
            record=course,
            event_type="class",
            type_label="University class",
            title=course.get("name"),
            subtitle=course.get("degree"),
            secondary=course.get("academic_year"),
            start_date=course.get("start_date"),
            end_date=course.get("end_date"),
        )
        for course in university_classes
    ]
    records.extend(
        _teaching_event(
            record=supervision,
            event_type="supervision",
            type_label=supervision.get("type") or "Academic supervision",
            title=supervision.get("title"),
            subtitle=supervision.get("degree"),
            secondary=None,
            start_date=supervision.get("date"),
            end_date=supervision.get("date"),
        )
        for supervision in academic_supervision
    )
    events = [event for event in records if event["start_month"] is not None]
    if not events:
        return {"events": [], "legend": [], "height": 0, "stage_width": 0, "axis_left": 0}

    _assign_teaching_organization_colors(events)

    month_min = min(int(event["start_month"]) for event in events)
    month_max = max(int(event["end_month"]) for event in events)
    month_span = max(month_max - month_min + 1, 1)
    pixels_per_month = 34
    top_padding = 42
    bottom_padding = 62
    lane_width = 232
    lane_gap = 12
    axis_gap = 48
    year_label_space = 28
    event_width = 220

    positioned = []
    for event in events:
        end_month = int(event["end_month"])
        start_month = int(event["start_month"])
        timeline_top = top_padding + ((month_max - end_month) * pixels_per_month)
        duration_height = max((end_month - start_month + 1) * pixels_per_month, 34)
        estimated_height = _teaching_event_height(event)
        height = max(duration_height, estimated_height)
        positioned.append(
            {
                **event,
                "top": timeline_top,
                "height": height,
                "bottom": timeline_top + height,
            }
        )

    positioned.sort(key=lambda event: (event["top"], event["type"], event["title"]))
    lane_ends = {"right": [], "left": []}
    previous_side = "left"
    for event in positioned:
        preferred_side = "right" if previous_side == "left" else "left"
        side, lane = _teaching_event_lane(event, preferred_side, lane_ends)
        lane_ends[side][lane] = event["bottom"]
        previous_side = side
        event["side"] = side
        event["lane"] = lane

    left_lanes = max(len(lane_ends["left"]), 1)
    right_lanes = max(len(lane_ends["right"]), 1)
    axis_left = left_lanes * (lane_width + lane_gap) + axis_gap + year_label_space
    stage_width = axis_left + axis_gap + right_lanes * (lane_width + lane_gap)
    height = top_padding + (month_span * pixels_per_month) + bottom_padding

    for event in positioned:
        side = event["side"]
        lane = int(event["lane"])
        lane_offset = lane * (lane_width + lane_gap)
        if side == "right":
            left = axis_left + axis_gap + lane_offset
            connector_left = axis_left
            connector_width = left - axis_left
        else:
            left = axis_left - axis_gap - event_width - lane_offset
            connector_left = left + event_width
            connector_width = axis_left - connector_left
        event["left"] = left
        event["width"] = event_width
        event["connector_width"] = connector_width
        event["style"] = (
            f"--org-color: {event['organization_color']}; "
            f"--item-top: {event['top']}px; "
            f"--item-left: {left}px; "
            f"--item-width: {event_width}px; "
            f"--item-height: {event['height']}px;"
        )
        event["connector_style"] = (
            f"--org-color: {event['organization_color']}; "
            f"--connector-top: {event['top'] + 24}px; "
            f"--connector-left: {connector_left}px; "
            f"--connector-width: {connector_width}px;"
        )

    legend = _teaching_organization_legend(positioned)
    return {
        "events": positioned,
        "legend": legend,
        "height": height,
        "stage_width": stage_width,
        "axis_left": axis_left,
        "axis_style": (
            f"--timeline-height: {height}px; "
            f"--stage-width: {stage_width}px; "
            f"--axis-left: {axis_left}px;"
        ),
        "year_ticks": _teaching_year_ticks(month_min, month_max, top_padding, pixels_per_month),
    }



def _teaching_event(
    *,
    record: dict[str, Any],
    event_type: str,
    type_label: Any,
    title: Any,
    subtitle: Any,
    secondary: Any,
    start_date: Any,
    end_date: Any,
) -> dict[str, Any]:
    start_month = _month_number(start_date)
    end_month = _month_number(end_date) if end_date else start_month
    if start_month is not None and end_month is not None and end_month < start_month:
        start_month, end_month = end_month, start_month
    organization = _primary_organization(record)
    detail_lines = _teaching_detail_lines(
        record=record,
        event_type=event_type,
        secondary=secondary,
    )
    return {
        "id": str(record.get("id") or ""),
        "type": event_type,
        "type_label": str(type_label or ""),
        "title": str(title or record_name(record)),
        "subtitle": str(subtitle or ""),
        "secondary": str(secondary or ""),
        "detail_lines": detail_lines,
        "date_label": date_range(start_date, end_date)
        if start_date != end_date
        else str(start_date or ""),
        "start_month": start_month,
        "end_month": end_month,
        "organization_id": organization["id"],
        "organization_name": organization["name"],
        "organization_label": organization["label"],
        "organization_color": "",
        "url": str(record.get("url") or ""),
        "repository_url": str(record.get("repository_url") or ""),
        "role": str(record.get("role") or ""),
        "workload_hours": record.get("workload_hours"),
        "department": str(record.get("department") or ""),
        "record": record,
    }



def _primary_organization(record: dict[str, Any]) -> dict[str, str]:
    organizations = record.get("resolved", {}).get("organization_ids", [])
    organization = organizations[0] if organizations else {}
    organization_id = str(organization.get("id") or "organization_unknown")
    return {
        "id": organization_id,
        "name": str(organization.get("name") or "Unknown organization"),
        "label": str(organization.get("abbreviation") or organization.get("name") or "Unknown"),
    }


def _assign_teaching_organization_colors(events: list[dict[str, Any]]) -> None:
    organizations = sorted(
        {
            (
                str(event.get("organization_label") or ""),
                str(event.get("organization_name") or ""),
                str(event.get("organization_id") or ""),
            )
            for event in events
        }
    )
    colors_by_id = {
        organization_id: TEACHING_ORGANIZATION_COLOR_PALETTE[
            index % len(TEACHING_ORGANIZATION_COLOR_PALETTE)
        ]
        for index, (_, _, organization_id) in enumerate(organizations)
    }
    for event in events:
        event["organization_color"] = colors_by_id[str(event.get("organization_id") or "")]



def _teaching_event_height(event: dict[str, Any]) -> int:
    line_count = 2
    line_count += _wrapped_line_count(event["title"], 32)
    line_count += _wrapped_line_count(event["subtitle"], 34)
    line_count += sum(_wrapped_line_count(line, 34) for line in event["detail_lines"])
    if event["repository_url"]:
        line_count += 1
    if event["type"] == "supervision":
        line_count += 1
    return max(line_count * 18 + 48, 118)



def _teaching_detail_lines(
    *,
    record: dict[str, Any],
    event_type: str,
    secondary: Any,
) -> list[str]:
    lines = [str(secondary)] if secondary else []
    if event_type == "class":
        if record.get("department"):
            lines.append(str(record["department"]))
        if record.get("workload_hours"):
            lines.append(f"{record['workload_hours']} hours")
    else:
        if record.get("role"):
            lines.append(str(record["role"]))
        if record.get("workload_hours"):
            lines.append(f"{record['workload_hours']} hours")
    return lines



def _wrapped_line_count(value: Any, characters_per_line: int) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    return max(ceil(len(text) / characters_per_line), 1)



def _teaching_event_lane(
    event: dict[str, Any],
    preferred_side: str,
    lane_ends: dict[str, list[float]],
) -> tuple[str, int]:
    alternate_side = "left" if preferred_side == "right" else "right"
    for side in (preferred_side, alternate_side):
        lane = _available_teaching_lane(event, lane_ends[side])
        if lane is not None:
            return side, lane

    lane_ends[preferred_side].append(float("-inf"))
    return preferred_side, len(lane_ends[preferred_side]) - 1



def _available_teaching_lane(event: dict[str, Any], lane_ends: list[float]) -> int | None:
    gap = 34
    for index, lane_end in enumerate(lane_ends):
        if event["top"] >= lane_end + gap:
            return index
    if not lane_ends:
        lane_ends.append(float("-inf"))
        return 0
    return None



def _teaching_organization_legend(events: list[dict[str, Any]]) -> list[dict[str, str]]:
    organizations = {}
    for event in events:
        organizations[event["organization_id"]] = {
            "id": event["organization_id"],
            "label": event["organization_label"],
            "name": event["organization_name"],
            "color": event["organization_color"],
        }
    return sorted(organizations.values(), key=lambda organization: organization["label"])



def _teaching_year_ticks(
    month_min: int,
    month_max: int,
    top_padding: int,
    pixels_per_month: int,
) -> list[dict[str, Any]]:
    years = range(_year_from_month(month_min), _year_from_month(month_max) + 1)
    return [
        {
            "year": year,
            "top": top_padding + ((month_max - (year * 12)) * pixels_per_month),
        }
        for year in years
    ]
