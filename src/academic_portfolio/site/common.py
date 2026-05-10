from __future__ import annotations

from datetime import date
from typing import Any


def _organization_full_label(organization: dict[str, Any]) -> str:
    return str(
        organization.get("full_name")
        or organization.get("name")
        or organization.get("abbreviation")
        or "Unknown organization"
    )


def _organization_short_label(organization: dict[str, Any]) -> str:
    return str(
        organization.get("abbreviation")
        or organization.get("name")
        or organization.get("full_name")
        or organization.get("id")
        or "Unknown organization"
    )


def _month_span_to_present(start_date: Any, end_date: Any) -> int:
    effective_end = end_date or date.today().strftime("%Y-%m")
    return _month_span(start_date, effective_end)


def _float_percentage(value: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return round((value / total) * 100, 2)


def _month_span(start_date: Any, end_date: Any) -> int:
    start = _month_number(start_date)
    end = _month_number(end_date)
    if start is None and end is None:
        return 0
    if start is None or end is None:
        return 1
    return max(end - start + 1, 1)


def _month_number(value: Any) -> int | None:
    if value in (None, ""):
        return None

    text = str(value)
    if len(text) < 4:
        return None

    try:
        year = int(text[:4])
        month = int(text[5:7]) if len(text) >= 7 and text[4] == "-" else 1
    except ValueError:
        return None

    return (year * 12) + month - 1


def _year_from_month(month_number: int) -> int:
    return month_number // 12


def _month_label(month_number: int) -> str:
    year = _year_from_month(month_number)
    month = (month_number % 12) + 1
    return f"{year}-{month:02d}"


def _percentage(value: int, total: int) -> float:
    return round((value / total) * 100, 2)
