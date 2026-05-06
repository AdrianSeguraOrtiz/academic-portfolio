from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from shutil import copy2
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from academic_portfolio.github import collect_github_project_stats
from academic_portfolio.loader import load_data
from academic_portfolio.packages import collect_package_stats
from academic_portfolio.render import date_range, record_name
from academic_portfolio.resolver import PortfolioResolver

LANGUAGE_COLORS = {
    "Dockerfile": "#384d54",
    "Go": "#00add8",
    "HTML": "#e34c26",
    "Java": "#b07219",
    "Julia": "#9558b2",
    "MATLAB": "#d85f2a",
    "Makefile": "#427819",
    "Perl": "#0298c3",
    "Python": "#3572a5",
    "R": "#198ce7",
    "Shell": "#89a65a",
}
OTHER_LANGUAGE_COLOR = "#66706d"


@dataclass(frozen=True)
class SiteOutput:
    output_path: Path
    asset_paths: list[Path]
    content: str


def build_site_view(
    resolver: PortfolioResolver,
    github_stats_by_url: dict[str, dict[str, Any]] | None = None,
    github_errors: dict[str, str] | None = None,
    package_stats_by_id: dict[str, dict[str, Any]] | None = None,
    package_errors: dict[str, str] | None = None,
) -> dict[str, Any]:
    profile = dict(resolver.loaded_data.documents["profile.yaml"])
    profile["current_positions"] = [
        _with_resolved_references(resolver, record)
        for record in resolver.resolve_many(profile.get("current_position_ids", []))
    ]
    profile["current_stays"] = [
        _with_resolved_references(resolver, record)
        for record in resolver.resolve_many(profile.get("current_stay_ids", []))
    ]

    journal_papers = _tagged_records(
        resolver,
        "research/publications.yaml",
        "journal_papers",
        "journal",
        reverse=True,
    )
    conference_papers = _tagged_records(
        resolver,
        "research/publications.yaml",
        "conference_papers",
        "conference",
        reverse=True,
    )
    publications = _sort_records_by_field(
        journal_papers + conference_papers,
        "publication_date",
        reverse=True,
    )
    software_projects = _records(
        resolver,
        "research/software_projects.yaml",
        "projects",
        reverse=True,
    )
    _attach_github_stats(software_projects, github_stats_by_url or {})
    software_packages = _records(
        resolver,
        "research/software_packages.yaml",
        "software_packages",
        reverse=False,
    )
    _attach_package_stats(software_packages, package_stats_by_id or {})
    press_items = _records(
        resolver,
        "activities/dissemination/press.yaml",
        "press_items",
        reverse=True,
    )
    social_media_items = _records(
        resolver,
        "activities/dissemination/social_media.yaml",
        "social_media_items",
        reverse=True,
    )
    reviewing = _records(
        resolver,
        "research/reviewing.yaml",
        "reviewing",
        reverse=True,
    )
    degrees = _records(resolver, "career/degrees.yaml", "degrees", reverse=True)
    experience = _records(resolver, "career/experience.yaml", "positions", reverse=True)
    research_stays = _records(resolver, "career/research_stays.yaml", "stays", reverse=True)
    certifications = _records(
        resolver,
        "career/certifications.yaml",
        "certifications",
        reverse=True,
    )
    honors = _records(resolver, "career/honors.yaml", "honors", reverse=True)
    grants = _records(resolver, "career/grants.yaml", "grants", reverse=True)
    research_projects = _records(
        resolver,
        "research/research_projects.yaml",
        "funded_projects",
        reverse=True,
    )
    scientific_articles = _records(
        resolver,
        "activities/dissemination/scientific_dissemination_articles.yaml",
        "scientific_dissemination_articles",
        reverse=True,
    )
    presentations = _records(
        resolver,
        "activities/dissemination/presentations.yaml",
        "presentations",
        reverse=True,
    )
    tv_media_items = _records(
        resolver,
        "activities/dissemination/tv_media.yaml",
        "tv_items",
        reverse=True,
    )
    university_classes = _records(
        resolver,
        "activities/teaching/university_classes.yaml",
        "university_classes",
        reverse=True,
    )
    academic_supervision = _records(
        resolver,
        "activities/teaching/academic_supervision.yaml",
        "academic_supervision",
        reverse=True,
    )
    teaching_innovation_projects = _records(
        resolver,
        "activities/teaching/teaching_innovation_projects.yaml",
        "teaching_innovation_projects",
        reverse=True,
    )
    organizations = _records(
        resolver,
        "entities/organizations.yaml",
        "organizations",
        reverse=False,
    )

    metrics = {
        "journal_papers": len(journal_papers),
        "conference_papers": len(conference_papers),
        "publications": len(publications),
        "software_projects": len(software_projects),
        "software_packages": len(software_packages),
        "research_projects": len(research_projects),
        "press_items": len(press_items),
        "press_outlets": len({item.get("outlet") for item in press_items if item.get("outlet")}),
        "scientific_dissemination_articles": len(scientific_articles),
        "presentations": len(presentations),
        "social_media_items": len(social_media_items),
        "tv_media_items": len(tv_media_items),
        "courses": len(university_classes),
        "supervisions": len(academic_supervision),
        "reviewed_manuscripts": sum(int(item.get("manuscripts_reviewed") or 0) for item in reviewing),
        "reviewing_journals": len(reviewing),
        "honors": len(honors),
        "grants": len(grants),
        "research_stays": len(research_stays),
    }

    return {
        "profile": profile,
        "metrics": metrics,
        "publications": publications,
        "software_projects": software_projects,
        "software_packages": software_packages,
        "career": {
            "degrees": degrees,
            "experience": experience,
            "research_stays": research_stays,
            "certifications": certifications,
            "honors": honors,
            "grants": grants,
        },
        "research_projects": research_projects,
        "reviewing": reviewing,
        "teaching": {
            "university_classes": university_classes,
            "academic_supervision": academic_supervision,
            "teaching_innovation_projects": teaching_innovation_projects,
        },
        "dissemination": {
            "scientific_articles": scientific_articles,
            "presentations": presentations,
            "press": press_items,
            "social_media": social_media_items,
            "tv_media": tv_media_items,
        },
        "organizations": organizations,
        "research_focus": profile.get("research_profile", {}).get("areas", []),
        "collaborations": _collaboration_view(publications, research_stays),
        "publication_chart": _publication_year_chart(journal_papers, conference_papers),
        "software_github": _software_github_summary(software_projects),
        "software_timeline": _software_timeline(software_projects),
        "software_language_chart": _software_language_chart(software_projects),
        "github_errors": github_errors or {},
        "package_errors": package_errors or {},
    }


def generate_site(
    output_dir: Path | str = "build/site",
    data_dir: Path | str = "data",
    template_dir: Path | str = "templates/site",
    static_dir: Path | str = "assets/site",
    refresh_github: bool = False,
    github_cache_path: Path | str = "build/cache/github_repositories.json",
    refresh_packages: bool = False,
    package_cache_path: Path | str = "build/cache/software_packages.json",
) -> SiteOutput:
    resolver = PortfolioResolver(load_data(data_dir))
    github_stats_by_url: dict[str, dict[str, Any]] = {}
    github_errors: dict[str, str] = {}
    package_stats_by_id: dict[str, dict[str, Any]] = {}
    package_errors: dict[str, str] = {}

    if refresh_github:
        github_result = collect_github_project_stats(
            list(resolver.records_in_group("research/software_projects.yaml", "projects")),
            cache_path=github_cache_path,
        )
        github_stats_by_url = github_result.stats_by_url
        github_errors = github_result.errors

    if refresh_packages:
        package_result = collect_package_stats(
            list(resolver.records_in_group("research/software_packages.yaml", "software_packages")),
            cache_path=package_cache_path,
        )
        package_stats_by_id = package_result.stats_by_id
        package_errors = package_result.errors

    view = build_site_view(
        resolver,
        github_stats_by_url=github_stats_by_url,
        github_errors=github_errors,
        package_stats_by_id=package_stats_by_id,
        package_errors=package_errors,
    )

    environment = _create_environment(template_dir)
    content = environment.get_template("index.html.j2").render(**view)

    output_path = Path(output_dir) / "index.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    asset_paths = _copy_static_assets(static_dir, output_path.parent / "assets")
    return SiteOutput(output_path=output_path, asset_paths=asset_paths, content=content)


def _create_environment(template_dir: Path | str) -> Environment:
    environment = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )
    environment.filters["date_range"] = date_range
    environment.filters["record_name"] = record_name
    environment.filters["number"] = _format_number
    return environment


def _copy_static_assets(static_dir: Path | str, output_dir: Path) -> list[Path]:
    source_dir = Path(static_dir)
    if not source_dir.exists():
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    copied_paths: list[Path] = []
    for source_path in sorted(source_dir.rglob("*")):
        if not source_path.is_file():
            continue

        relative_path = source_path.relative_to(source_dir)
        target_path = output_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        copy2(source_path, target_path)
        copied_paths.append(target_path)

    return copied_paths


def _format_number(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def _records(
    resolver: PortfolioResolver,
    file_path: str,
    group: str,
    *,
    reverse: bool,
) -> list[dict[str, Any]]:
    records = [
        _with_resolved_references(resolver, record)
        for record in resolver.records_in_group(file_path, group)
    ]
    return list(reversed(records)) if reverse else records


def _tagged_records(
    resolver: PortfolioResolver,
    file_path: str,
    group: str,
    publication_kind: str,
    *,
    reverse: bool,
) -> list[dict[str, Any]]:
    records = _records(resolver, file_path, group, reverse=reverse)
    for record in records:
        record["publication_kind"] = publication_kind
    return records


def _with_resolved_references(
    resolver: PortfolioResolver,
    record: dict[str, Any],
) -> dict[str, Any]:
    item = dict(record)
    item["resolved"] = resolver.references_for(record)
    return item


def _sort_records_by_field(
    records: list[dict[str, Any]],
    field: str,
    *,
    reverse: bool,
) -> list[dict[str, Any]]:
    return sorted(records, key=lambda record: str(record.get(field) or ""), reverse=reverse)


def _attach_github_stats(
    projects: list[dict[str, Any]],
    github_stats_by_url: dict[str, dict[str, Any]],
) -> None:
    for project in projects:
        github_url = str(project.get("urls", {}).get("github") or "")
        if github_url in github_stats_by_url:
            project["github"] = github_stats_by_url[github_url]


def _attach_package_stats(
    packages: list[dict[str, Any]],
    package_stats_by_id: dict[str, dict[str, Any]],
) -> None:
    for package in packages:
        package_id = str(package.get("id"))
        if package_id in package_stats_by_id:
            package["package_stats"] = package_stats_by_id[package_id]


def _publication_year_chart(
    journal_papers: list[dict[str, Any]],
    conference_papers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    journal_counts = _year_counts(journal_papers, "publication_date")
    conference_counts = _year_counts(conference_papers, "publication_date")
    years = sorted(set(journal_counts) | set(conference_counts))
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


def _year_counts(records: list[dict[str, Any]], date_field: str) -> Counter[str]:
    return Counter(
        str(record.get(date_field))[:4]
        for record in records
        if record.get(date_field)
    )


def _collaboration_view(
    publications: list[dict[str, Any]],
    research_stays: list[dict[str, Any]],
) -> dict[str, Any]:
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
                "months": 0,
            },
        )
        item["stay_ids"].add(stay["id"])
        item["stay_titles"].append(stay["title"])
        item["months"] += _month_span(stay.get("start_date"), stay.get("end_date"))

    max_publications = max(
        (len(location["publication_ids"]) for location in publication_locations.values()),
        default=1,
    )
    publication_nodes = [
        _publication_map_node(location, max_publications)
        for location in publication_locations.values()
    ]
    stay_nodes = [
        _stay_map_node(location)
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


def _publication_map_node(location: dict[str, Any], max_publications: int) -> dict[str, Any]:
    publication_count = len(location["publication_ids"])
    radius = round(6 + (sqrt(publication_count / max_publications) * 12), 2)
    return {
        "city": location["city"],
        "country": location["country"],
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "publication_count": publication_count,
        "organization_count": len(location["organization_names"]),
        "radius": radius,
    }


def _stay_map_node(location: dict[str, Any]) -> dict[str, Any]:
    months = int(location["months"])
    return {
        "city": location["city"],
        "country": location["country"],
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "stay_count": len(location["stay_ids"]),
        "months": months,
    }


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


def _month_span(start_date: Any, end_date: Any) -> int:
    start = _month_number(start_date)
    end = _month_number(end_date)
    if start is None and end is None:
        return 0
    if start is None or end is None:
        return 1
    return max(end - start + 1, 1)


def _software_github_summary(projects: list[dict[str, Any]]) -> dict[str, Any]:
    github_records = [project["github"] for project in projects if project.get("github")]
    pushed_dates = [stats.get("pushed_at") for stats in github_records if stats.get("pushed_at")]
    return {
        "repositories_with_stats": len(github_records),
        "total_stars": sum(int(stats.get("stargazers_count") or 0) for stats in github_records),
        "total_forks": sum(int(stats.get("forks_count") or 0) for stats in github_records),
        "open_issues": sum(int(stats.get("open_issues_count") or 0) for stats in github_records),
        "active_repositories": sum(1 for stats in github_records if not stats.get("archived")),
        "last_push_date": max(pushed_dates)[:10] if pushed_dates else None,
    }


def _software_timeline(projects: list[dict[str, Any]]) -> dict[str, Any]:
    timeline_projects = []
    timeline_months: list[int] = []

    for project in projects:
        github = project.get("github", {})
        commit_months = _commit_month_counts(github)
        created_month = _month_number(github.get("created_at"))
        pushed_month = _month_number(github.get("pushed_at"))
        active_months = list(commit_months)

        if not active_months and created_month is None and pushed_month is None:
            continue

        timeline_months.extend(active_months)
        timeline_months.extend(
            month for month in (created_month, pushed_month) if month is not None
        )

        timeline_projects.append(
            {
                "project": project,
                "commit_months": commit_months,
                "created_month": created_month,
                "pushed_month": pushed_month,
                "language": project.get("github", {}).get("language"),
                "color": _language_color(project.get("github", {}).get("language")),
            }
        )

    if not timeline_months:
        return {"years": [], "rows": []}

    min_month = min(timeline_months)
    max_month = max(timeline_months)
    total_months = max(max_month - min_month + 1, 1)
    rows = []
    for item in sorted(timeline_projects, key=_timeline_sort_month):
        commit_months = item["commit_months"]
        max_commits = max(commit_months.values(), default=1)
        created = item["created_month"]
        pushed = item["pushed_month"]
        rows.append(
            {
                "project": item["project"],
                "language": item["language"],
                "color": item["color"],
                "months": [
                    {
                        "month": _month_label(month),
                        "count": count,
                        "left": _percentage(month - min_month, total_months),
                        "width": max(_percentage(1, total_months), 0.8),
                        "height": round(8 + ((count / max_commits) * 24), 2),
                    }
                    for month, count in sorted(commit_months.items())
                ],
                "created_left": _percentage(int(created) - min_month, total_months)
                if created is not None
                else None,
                "pushed_left": _percentage(int(pushed) - min_month + 1, total_months)
                if pushed is not None
                else None,
            }
        )

    return {
        "years": list(range(_year_from_month(min_month), _year_from_month(max_month) + 1)),
        "rows": rows,
    }


def _software_language_chart(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    language_totals: Counter[str] = Counter()
    for project in projects:
        languages = project.get("github", {}).get("languages", {})
        if isinstance(languages, dict):
            language_totals.update(
                {
                    str(language): int(byte_count)
                    for language, byte_count in languages.items()
                    if int(byte_count) > 0
                }
            )

    total_bytes = sum(language_totals.values())
    if total_bytes == 0:
        return []

    top_languages = language_totals.most_common(7)
    other_bytes = total_bytes - sum(byte_count for _language, byte_count in top_languages)
    chart = [
        {
            "name": language,
            "bytes": byte_count,
            "share": round((byte_count / total_bytes) * 100, 1),
            "color": _language_color(language),
        }
        for language, byte_count in top_languages
    ]
    if other_bytes:
        chart.append(
            {
                "name": "Other",
                "bytes": other_bytes,
                "share": round((other_bytes / total_bytes) * 100, 1),
                "color": OTHER_LANGUAGE_COLOR,
            }
        )

    return chart


def _commit_month_counts(github: dict[str, Any]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for item in github.get("commit_months", []):
        if not isinstance(item, dict):
            continue

        month = _month_number(item.get("month"))
        count = item.get("count")
        if month is None or count is None:
            continue

        counts[month] = int(count)

    return counts


def _timeline_sort_month(row: dict[str, Any]) -> int:
    commit_months = row["commit_months"]
    candidates = list(commit_months) + [
        month for month in (row["created_month"], row["pushed_month"]) if month is not None
    ]
    return min(candidates) if candidates else 0


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


def _language_color(language: str | None) -> str:
    if not language:
        return OTHER_LANGUAGE_COLOR
    return LANGUAGE_COLORS.get(language, OTHER_LANGUAGE_COLOR)
