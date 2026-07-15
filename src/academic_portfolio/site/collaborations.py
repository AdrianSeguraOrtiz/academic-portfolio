from __future__ import annotations

from math import sqrt
from typing import Any

from academic_portfolio.i18n import Translator, load_translator
from academic_portfolio.site.common import _month_span


def _collaboration_view(
    publications: list[dict[str, Any]],
    research_stays: list[dict[str, Any]],
    experience: list[dict[str, Any]] | None = None,
    translator: Translator | None = None,
) -> dict[str, Any]:
    active_translator = translator or load_translator()
    positions_by_id = {str(position.get("id")): position for position in experience or []}
    publication_locations: dict[tuple[str, str], dict[str, Any]] = {}
    stay_locations: dict[tuple[str, str], dict[str, Any]] = {}
    work_locations: dict[tuple[str, str], dict[str, Any]] = {}
    stay_routes: list[dict[str, Any]] = []
    publication_country_sets: list[set[str]] = []

    for publication in publications:
        publication_seen_locations: set[tuple[str, str]] = set()
        publication_countries: set[str] = set()
        for organization in publication.get("resolved", {}).get("organization_ids", []):
            location = _organization_location(organization)
            if not location:
                continue

            publication_countries.add(location["country"])
            key = (location["city"], location["country"])
            item = publication_locations.setdefault(
                key,
                {
                    **location,
                    "publication_ids": set(),
                    "organization_names": set(),
                },
            )
            item["organization_names"].add(organization["name"])
            if key in publication_seen_locations:
                continue

            publication_seen_locations.add(key)
            item["publication_ids"].add(publication["id"])
        publication_country_sets.append(publication_countries)

    for stay in research_stays:
        location = _stay_location(stay)
        if not location:
            continue

        key = (location["city"], location["country"])
        item = stay_locations.setdefault(
            key,
            {
                **location,
                "stay_ids": set(),
                "stay_titles": [],
                "stays": [],
                "months": 0,
            },
        )
        months = _month_span(stay.get("start_date"), stay.get("end_date"))
        item["stay_ids"].add(stay["id"])
        item["stay_titles"].append(stay["title"])
        item["stays"].append(
            {
                "months": int(months),
                "year": _stay_year(stay),
            }
        )
        item["months"] += months
        for origin_position in _origin_positions_for_stay(stay, positions_by_id):
            origin_location = _position_location(origin_position)
            if not origin_location or _same_map_location(origin_location, location):
                continue
            stay_routes.append(_stay_route_node(stay, origin_position, origin_location, location))

    for position in experience or []:
        location = _position_location(position)
        if not location:
            continue

        key = (location["city"], location["country"])
        item = work_locations.setdefault(
            key,
            {
                **location,
                "appointments": {},
                "position_ids": set(),
                "position_periods": [],
            },
        )
        appointment_key = _position_appointment_key(position)
        appointment = item["appointments"].setdefault(
            appointment_key,
            {
                "label": _position_organization_label(position),
                "position_ids": set(),
                "titles": [],
                "start_dates": [],
                "end_dates": [],
                "has_current": False,
            },
        )
        appointment["position_ids"].add(position["id"])
        appointment["titles"].append(str(position.get("title") or ""))
        if position.get("start_date"):
            appointment["start_dates"].append(str(position.get("start_date")))
        if position.get("end_date"):
            appointment["end_dates"].append(str(position.get("end_date")))
        else:
            appointment["has_current"] = True
        item["position_ids"].add(position["id"])
        item["position_periods"].append(_position_year_interval(position))

    max_publications = max(
        (len(location["publication_ids"]) for location in publication_locations.values()),
        default=1,
    )
    publication_nodes = [
        _publication_map_node(location, max_publications, active_translator)
        for location in publication_locations.values()
    ]
    stay_nodes = [
        _stay_map_node(location, active_translator) for location in stay_locations.values()
    ]
    work_nodes = [
        _work_map_node(location, active_translator) for location in work_locations.values()
    ]

    city_rows = [
        _collaboration_city_row(
            key,
            publication_locations.get(key),
            stay_locations.get(key),
            work_locations.get(key),
        )
        for key in sorted(set(publication_locations) | set(stay_locations) | set(work_locations))
    ]
    publication_countries = (
        set().union(*publication_country_sets) if publication_country_sets else set()
    )
    stay_countries = {location["country"] for location in stay_locations.values()}
    work_countries = {location["country"] for location in work_locations.values()}
    work_appointments = [
        appointment
        for location in work_locations.values()
        for appointment in location["appointments"].values()
    ]

    return {
        "publication_nodes": sorted(publication_nodes, key=lambda node: node["city"]),
        "stay_nodes": sorted(stay_nodes, key=lambda node: node["city"]),
        "work_nodes": sorted(work_nodes, key=lambda node: node["city"]),
        "cities": city_rows,
        "map_data": {
            "publication_nodes": sorted(publication_nodes, key=lambda node: node["city"]),
            "stay_nodes": sorted(stay_nodes, key=lambda node: node["city"]),
            "work_nodes": sorted(work_nodes, key=lambda node: node["city"]),
            "route_nodes": sorted(
                stay_routes, key=lambda node: (node["destination_city"], node["year"])
            ),
        },
        "metrics": {
            "total_papers": len(publications),
            "international_papers": sum(
                1 for country_set in publication_country_sets if len(country_set) > 1
            ),
            "publication_countries": len(publication_countries),
            "publication_cities": len(publication_locations),
            "stay_cities": len(stay_locations),
            "stay_countries": len(stay_countries),
            "research_stays": sum(len(item["stay_ids"]) for item in stay_locations.values()),
            "stay_months": sum(item["months"] for item in stay_locations.values()),
            "work_cities": len(work_locations),
            "work_countries": len(work_countries),
            "work_appointments": len(work_appointments),
            "work_institutions": len(work_appointments),
            "active_work_institutions": sum(
                1 for appointment in work_appointments if appointment["has_current"]
            ),
        },
    }


def _organization_location(organization: dict[str, Any]) -> dict[str, Any] | None:
    location = organization.get("location", {})
    coordinates = location.get("coordinates") or {}
    city = location.get("city")
    country = location.get("country")
    latitude = coordinates.get("latitude")
    longitude = coordinates.get("longitude")
    if city is None or country is None or latitude is None or longitude is None:
        return None

    return _map_location(
        city=str(city),
        country=str(country),
        latitude=float(latitude),
        longitude=float(longitude),
    )


def _stay_location(stay: dict[str, Any]) -> dict[str, Any] | None:
    stay_location = stay.get("location", {})
    coordinates = stay_location.get("coordinates") or {}
    latitude = coordinates.get("latitude")
    longitude = coordinates.get("longitude")

    if latitude is None or longitude is None:
        for organization in stay.get("resolved", {}).get("organization_ids", []):
            organization_location = _organization_location(organization)
            if organization_location:
                latitude = organization_location["latitude"]
                longitude = organization_location["longitude"]
                break

    city = stay_location.get("city")
    country = stay_location.get("country")
    if city is None or country is None or latitude is None or longitude is None:
        return None

    return _map_location(
        city=str(city),
        country=str(country),
        latitude=float(latitude),
        longitude=float(longitude),
    )


def _position_location(position: dict[str, Any]) -> dict[str, Any] | None:
    for organization in position.get("resolved", {}).get("organization_ids", []):
        organization_location = _organization_location(organization)
        if organization_location:
            return organization_location
    return None


def _origin_positions_for_stay(
    stay: dict[str, Any],
    positions_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    positions = []
    for position in stay.get("resolved", {}).get("origin_position_ids", []):
        position_id = str(position.get("id") or "")
        positions.append(positions_by_id.get(position_id, position))
    return positions


def _map_location(city: str, country: str, latitude: float, longitude: float) -> dict[str, Any]:
    return {
        "city": city,
        "country": country,
        "latitude": latitude,
        "longitude": longitude,
    }


def _publication_map_node(
    location: dict[str, Any],
    max_publications: int,
    translator: Translator,
) -> dict[str, Any]:
    publication_count = len(location["publication_ids"])
    radius = round(6 + (sqrt(publication_count / max_publications) * 12), 2)
    return {
        "city": location["city"],
        "country": location["country"],
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "publication_count": publication_count,
        "publication_label": translator.unit("publication", publication_count),
        "organization_count": len(location["organization_names"]),
        "radius": radius,
    }


def _stay_map_node(location: dict[str, Any], translator: Translator) -> dict[str, Any]:
    months = int(location["months"])
    stays = sorted(
        location["stays"],
        key=lambda stay: (str(stay["year"]), int(stay["months"])),
    )
    return {
        "city": location["city"],
        "country": location["country"],
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "stay_count": len(location["stay_ids"]),
        "months": months,
        "stays": [
            {
                **stay,
                "label": (
                    f"{translator.plural('site.labels.month_short', stay['months'])}"
                    f" · {stay['year']}"
                ),
            }
            for stay in stays
        ],
    }


def _stay_year(stay: dict[str, Any]) -> str:
    date_value = stay.get("start_date") or stay.get("end_date") or ""
    return str(date_value)[:4] if len(str(date_value)) >= 4 else "n.d."


def _stay_route_node(
    stay: dict[str, Any],
    origin_position: dict[str, Any],
    origin_location: dict[str, Any],
    destination_location: dict[str, Any],
) -> dict[str, Any]:
    year = _stay_year(stay)
    origin_title = str(origin_position.get("title") or origin_position.get("id") or "")
    return {
        "id": f"{origin_position.get('id', 'origin')}:{stay.get('id', 'stay')}",
        "stay_id": stay.get("id"),
        "origin_position_id": origin_position.get("id"),
        "origin_city": origin_location["city"],
        "origin_country": origin_location["country"],
        "origin_latitude": origin_location["latitude"],
        "origin_longitude": origin_location["longitude"],
        "destination_city": destination_location["city"],
        "destination_country": destination_location["country"],
        "destination_latitude": destination_location["latitude"],
        "destination_longitude": destination_location["longitude"],
        "year": year,
        "label": (
            f"{origin_location['city']} → {destination_location['city']} · {year} · {origin_title}"
        ),
    }


def _same_map_location(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return first["city"] == second["city"] and first["country"] == second["country"]


def _work_map_node(location: dict[str, Any], translator: Translator) -> dict[str, Any]:
    appointments = sorted(
        (
            _work_appointment_summary(appointment, translator)
            for appointment in location["appointments"].values()
        ),
        key=lambda appointment: appointment["sort_date"],
        reverse=True,
    )
    position_count = len(location["position_ids"])
    labels = [
        _work_period_label(location["position_periods"], translator),
        translator.unit("position", position_count),
    ]
    return {
        "city": location["city"],
        "country": location["country"],
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "appointment_count": len(appointments),
        "position_count": position_count,
        "labels": [label for label in labels if label],
        "appointments": appointments,
    }


def _work_appointment_summary(
    appointment: dict[str, Any], translator: Translator
) -> dict[str, Any]:
    start_dates = sorted(appointment["start_dates"])
    end_dates = sorted(appointment["end_dates"])
    start_year = _date_year(start_dates[0]) if start_dates else "n.d."
    end_year = (
        translator.t("labels.present")
        if appointment["has_current"]
        else _date_year(end_dates[-1])
        if end_dates
        else start_year
    )
    period = start_year if start_year == end_year else f"{start_year}-{end_year}"
    return {
        "label": f"{appointment['label']} · {period}",
        "organization": appointment["label"],
        "period": period,
        "titles": [title for title in appointment["titles"] if title],
        "position_count": len(appointment["position_ids"]),
        "is_current": appointment["has_current"],
        "sort_date": "9999-99"
        if appointment["has_current"]
        else end_dates[-1]
        if end_dates
        else start_year,
    }


def _position_appointment_key(position: dict[str, Any]) -> str:
    labels = _position_organization_labels(position)
    return " / ".join(labels) or str(position.get("id") or "")


def _position_organization_label(position: dict[str, Any]) -> str:
    return " / ".join(_position_organization_labels(position))


def _position_organization_labels(position: dict[str, Any]) -> list[str]:
    labels = []
    for organization in position.get("resolved", {}).get("organization_ids", []):
        labels.append(
            str(
                organization.get("abbreviation")
                or organization.get("name")
                or organization.get("full_name")
                or ""
            )
        )
    return [label for label in labels if label]


def _position_year_interval(position: dict[str, Any]) -> dict[str, int | None]:
    start_year = _year_number(position.get("start_date"))
    end_year = None if not position.get("end_date") else _year_number(position.get("end_date"))
    if start_year is None and end_year is not None:
        start_year = end_year
    return {"start": start_year, "end": end_year}


def _work_period_label(periods: list[dict[str, int | None]], translator: Translator) -> str:
    merged_periods = _merge_year_intervals(periods)
    return " · ".join(
        _format_year_interval(period["start"], period["end"], translator)
        for period in merged_periods
    )


def _merge_year_intervals(
    periods: list[dict[str, int | None]],
) -> list[dict[str, int | None]]:
    valid_periods = sorted(
        (period for period in periods if period["start"] is not None),
        key=lambda period: int(period["start"] or 0),
    )
    merged: list[dict[str, int | None]] = []
    for period in valid_periods:
        start = int(period["start"] or 0)
        end = period["end"]
        if not merged:
            merged.append({"start": start, "end": end})
            continue

        previous = merged[-1]
        previous_end = previous["end"]
        if previous_end is None:
            continue
        if start <= previous_end + 1:
            previous["end"] = None if end is None else max(previous_end, end)
            continue

        merged.append({"start": start, "end": end})
    return merged


def _format_year_interval(start: int | None, end: int | None, translator: Translator) -> str:
    if start is None:
        return ""
    if end is None:
        return f"{start}-{translator.t('labels.present')}"
    if start == end:
        return str(start)
    return f"{start}-{end}"


def _year_number(value: Any) -> int | None:
    year_text = str(value or "")[:4]
    return int(year_text) if year_text.isdigit() else None


def _date_year(value: str) -> str:
    return value[:4] if len(value) >= 4 else "n.d."


def _collaboration_city_row(
    key: tuple[str, str],
    publication_location: dict[str, Any] | None,
    stay_location: dict[str, Any] | None,
    work_location: dict[str, Any] | None,
) -> dict[str, Any]:
    city, country = key
    publication_count = len(publication_location["publication_ids"]) if publication_location else 0
    stay_count = len(stay_location["stay_ids"]) if stay_location else 0
    stay_months = int(stay_location["months"]) if stay_location else 0
    appointment_count = len(work_location["appointments"]) if work_location else 0
    kinds = []
    if publication_count:
        kinds.append("publications")
    if stay_count:
        kinds.append("stays")
    if appointment_count:
        kinds.append("work")

    return {
        "city": city,
        "country": country,
        "publication_count": publication_count,
        "stay_count": stay_count,
        "stay_months": stay_months,
        "appointment_count": appointment_count,
        "kind": "+".join(kinds) if kinds else "none",
    }
