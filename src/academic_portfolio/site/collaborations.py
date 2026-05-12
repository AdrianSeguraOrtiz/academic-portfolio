from __future__ import annotations

from math import sqrt
from typing import Any

from academic_portfolio.i18n import Translator, load_translator
from academic_portfolio.site.common import _month_span

def _collaboration_view(
    publications: list[dict[str, Any]],
    research_stays: list[dict[str, Any]],
    translator: Translator | None = None,
) -> dict[str, Any]:
    active_translator = translator or load_translator()
    publication_locations: dict[tuple[str, str], dict[str, Any]] = {}
    stay_locations: dict[tuple[str, str], dict[str, Any]] = {}
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

    max_publications = max(
        (len(location["publication_ids"]) for location in publication_locations.values()),
        default=1,
    )
    publication_nodes = [
        _publication_map_node(location, max_publications, active_translator)
        for location in publication_locations.values()
    ]
    stay_nodes = [
        _stay_map_node(location, active_translator)
        for location in stay_locations.values()
    ]

    city_rows = [
        _collaboration_city_row(
            key,
            publication_locations.get(key),
            stay_locations.get(key),
        )
        for key in sorted(set(publication_locations) | set(stay_locations))
    ]
    publication_countries = set().union(*publication_country_sets) if publication_country_sets else set()
    stay_countries = {location["country"] for location in stay_locations.values()}

    return {
        "publication_nodes": sorted(publication_nodes, key=lambda node: node["city"]),
        "stay_nodes": sorted(stay_nodes, key=lambda node: node["city"]),
        "cities": city_rows,
        "map_data": {
            "publication_nodes": sorted(publication_nodes, key=lambda node: node["city"]),
            "stay_nodes": sorted(stay_nodes, key=lambda node: node["city"]),
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
                    f"{translator.t('site.labels.month_short', count=stay['months'])}"
                    f" · {stay['year']}"
                ),
            }
            for stay in stays
        ],
    }


def _stay_year(stay: dict[str, Any]) -> str:
    date_value = stay.get("start_date") or stay.get("end_date") or ""
    return str(date_value)[:4] if len(str(date_value)) >= 4 else "n.d."


def _collaboration_city_row(
    key: tuple[str, str],
    publication_location: dict[str, Any] | None,
    stay_location: dict[str, Any] | None,
) -> dict[str, Any]:
    city, country = key
    publication_count = len(publication_location["publication_ids"]) if publication_location else 0
    stay_count = len(stay_location["stay_ids"]) if stay_location else 0
    stay_months = int(stay_location["months"]) if stay_location else 0
    if publication_count and stay_count:
        kind = "both"
    elif publication_count:
        kind = "publications"
    else:
        kind = "stays"

    return {
        "city": city,
        "country": country,
        "publication_count": publication_count,
        "stay_count": stay_count,
        "stay_months": stay_months,
        "kind": kind,
    }
