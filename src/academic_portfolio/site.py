from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from math import ceil, sqrt
from pathlib import Path
from shutil import copy2
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from academic_portfolio.github import collect_github_project_stats
from academic_portfolio.loader import load_data
from academic_portfolio.packages import collect_package_stats
from academic_portfolio.render import date_range, record_name
from academic_portfolio.resolver import PortfolioResolver
from academic_portfolio.view_records import (
    resolved_records,
    sort_records_by_field,
    with_resolved_references,
)

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

DISSEMINATION_CATEGORIES = [
    {"id": "articles", "label": "Scientific articles", "singular": "Scientific article"},
    {"id": "presentations", "label": "Presentations", "singular": "Presentation"},
    {"id": "press", "label": "Press", "singular": "Press"},
    {"id": "social", "label": "Social media", "singular": "Social media"},
    {"id": "tv", "label": "TV media", "singular": "TV media"},
]

ORGANIZATION_RELATIONSHIP_TYPES = [
    {"id": "education", "label": "Education", "short": "edu", "unit": "months"},
    {"id": "experience", "label": "Experience", "short": "exp", "unit": "months"},
    {"id": "stays", "label": "Research stays", "short": "stay", "unit": "months"},
    {"id": "publications", "label": "Publications", "short": "pub", "unit": "papers"},
    {"id": "teaching", "label": "Teaching", "short": "teach", "unit": "activities"},
]


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
        with_resolved_references(resolver, record)
        for record in resolver.resolve_many(profile.get("current_position_ids", []))
    ]
    profile["current_stays"] = [
        with_resolved_references(resolver, record)
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
    publications = sort_records_by_field(
        journal_papers + conference_papers,
        "publication_date",
        reverse=True,
    )
    software_projects = resolved_records(
        resolver,
        "research/software_projects.yaml",
        "projects",
        reverse=True,
    )
    _attach_github_stats(software_projects, github_stats_by_url or {})
    software_packages = resolved_records(
        resolver,
        "research/software_packages.yaml",
        "software_packages",
        reverse=False,
    )
    _attach_package_stats(software_packages, package_stats_by_id or {})
    press_items = resolved_records(
        resolver,
        "activities/dissemination/press.yaml",
        "press_items",
        reverse=True,
    )
    social_media_items = resolved_records(
        resolver,
        "activities/dissemination/social_media.yaml",
        "social_media_items",
        reverse=True,
    )
    degrees = resolved_records(resolver, "career/degrees.yaml", "degrees", reverse=True)
    experience = resolved_records(resolver, "career/experience.yaml", "positions", reverse=True)
    research_stays = resolved_records(resolver, "career/research_stays.yaml", "stays", reverse=True)
    certifications = resolved_records(
        resolver,
        "career/certifications.yaml",
        "certifications",
        reverse=True,
    )
    honors = resolved_records(resolver, "career/honors.yaml", "honors", reverse=True)
    grants = resolved_records(resolver, "career/grants.yaml", "grants", reverse=True)
    research_projects = resolved_records(
        resolver,
        "research/research_projects.yaml",
        "funded_projects",
        reverse=True,
    )
    scientific_articles = resolved_records(
        resolver,
        "activities/dissemination/scientific_dissemination_articles.yaml",
        "scientific_dissemination_articles",
        reverse=True,
    )
    presentations = resolved_records(
        resolver,
        "activities/dissemination/presentations.yaml",
        "presentations",
        reverse=True,
    )
    tv_media_items = resolved_records(
        resolver,
        "activities/dissemination/tv_media.yaml",
        "tv_items",
        reverse=True,
    )
    university_classes = resolved_records(
        resolver,
        "activities/teaching/university_classes.yaml",
        "university_classes",
        reverse=True,
    )
    academic_supervision = resolved_records(
        resolver,
        "activities/teaching/academic_supervision.yaml",
        "academic_supervision",
        reverse=True,
    )
    teaching_innovation_projects = resolved_records(
        resolver,
        "activities/teaching/teaching_innovation_projects.yaml",
        "teaching_innovation_projects",
        reverse=True,
    )
    projects = _project_records(research_projects, teaching_innovation_projects)
    teaching_timeline = _teaching_timeline_view(university_classes, academic_supervision)
    dissemination_hub = _dissemination_view(
        scientific_articles,
        presentations,
        press_items,
        social_media_items,
        tv_media_items,
    )
    organizations = resolved_records(
        resolver,
        "entities/organizations.yaml",
        "organizations",
        reverse=False,
    )
    organization_network = _organization_network_view(
        organizations=organizations,
        degrees=degrees,
        experience=experience,
        research_stays=research_stays,
        publications=publications,
        university_classes=university_classes,
        academic_supervision=academic_supervision,
    )

    metrics = {
        "journal_papers": len(journal_papers),
        "conference_papers": len(conference_papers),
        "publications": len(publications),
        "projects": len(projects),
        "software_projects": len(software_projects),
        "software_packages": len(software_packages),
        "research_projects": len(research_projects),
        "teaching_innovation_projects": len(teaching_innovation_projects),
        "press_items": len(press_items),
        "press_outlets": len({item.get("outlet") for item in press_items if item.get("outlet")}),
        "scientific_dissemination_articles": len(scientific_articles),
        "presentations": len(presentations),
        "social_media_items": len(social_media_items),
        "tv_media_items": len(tv_media_items),
        "courses": len(university_classes),
        "supervisions": len(academic_supervision),
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
        "projects": projects,
        "research_projects": research_projects,
        "teaching": {
            "university_classes": university_classes,
            "academic_supervision": academic_supervision,
            "teaching_innovation_projects": teaching_innovation_projects,
        },
        "teaching_timeline": teaching_timeline,
        "dissemination": {
            "scientific_articles": scientific_articles,
            "presentations": presentations,
            "press": press_items,
            "social_media": social_media_items,
            "tv_media": tv_media_items,
        },
        "dissemination_hub": dissemination_hub,
        "organizations": organizations,
        "organization_network": organization_network,
        "research_focus": profile.get("research_profile", {}).get("areas", []),
        "career_timeline": _career_timeline_view(
            degrees,
            experience,
            research_stays,
            certifications,
            honors,
            grants,
        ),
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


def _tagged_records(
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


def _project_records(
    research_projects: list[dict[str, Any]],
    teaching_projects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    projects = [
        _project_record(
            project,
            project_type="research",
            project_type_label="Research project",
            display_title=_research_project_title(project),
            project_funders=project.get("funders", []),
        )
        for project in research_projects
    ]
    projects.extend(
        _project_record(
            project,
            project_type="teaching",
            project_type_label="Teaching innovation project",
            display_title=project.get("title"),
            project_funders=[project["funding_entity"]] if project.get("funding_entity") else [],
        )
        for project in teaching_projects
    )
    return sorted(projects, key=_project_sort_key, reverse=True)


def _project_record(
    project: dict[str, Any],
    *,
    project_type: str,
    project_type_label: str,
    display_title: Any,
    project_funders: list[Any],
) -> dict[str, Any]:
    item = dict(project)
    item["project_type"] = project_type
    item["project_type_label"] = project_type_label
    item["display_title"] = str(display_title or record_name(project))
    item["project_funders"] = [str(funder) for funder in project_funders if funder]
    item["participation_class"] = _project_participation_class(project.get("participation"))
    return item


def _research_project_title(project: dict[str, Any]) -> str:
    title = str(project.get("title") or record_name(project))
    acronym = str(project.get("acronym") or "").strip()
    return f"{acronym}: {title}" if acronym else title


def _project_participation_class(participation: Any) -> str:
    role_text = str(participation or "").lower()
    normalized_role = f" {role_text.replace('/', ' ').replace('-', ' ').replace('.', ' ')} "
    if (
        "principal investigator" in role_text
        or "investigador principal" in role_text
        or " co pi " in normalized_role
        or " co ip " in normalized_role
        or " pi " in normalized_role
        or " ip " in normalized_role
    ):
        return "lead"
    if "research team" in role_text or "researcher" in role_text:
        return "research"
    return "working"


def _project_sort_key(project: dict[str, Any]) -> tuple[str, str, str]:
    date_value = str(
        project.get("end_date")
        or project.get("start_date")
        or project.get("issue_date")
        or "",
    )
    return (date_value, str(project.get("project_type") or ""), str(project.get("display_title") or ""))


def _dissemination_view(
    scientific_articles: list[dict[str, Any]],
    presentations: list[dict[str, Any]],
    press_items: list[dict[str, Any]],
    social_media_items: list[dict[str, Any]],
    tv_media_items: list[dict[str, Any]],
) -> dict[str, Any]:
    items = [
        *[
            _dissemination_item(
                record=article,
                category="articles",
                type_label="Scientific article",
                title=article.get("title"),
                url=article.get("url"),
                date=article.get("date"),
                date_label=str(article.get("date") or ""),
                source=article.get("outlet"),
                detail_lines=[f"Issue {article['issue']}"] if article.get("issue") else [],
            )
            for article in scientific_articles
        ],
        *[
            _dissemination_item(
                record=presentation,
                category="presentations",
                type_label=str(presentation.get("type") or "Presentation"),
                title=presentation.get("title"),
                url=presentation.get("url"),
                date=presentation.get("start_date"),
                date_label=date_range(presentation.get("start_date"), presentation.get("end_date")),
                source=presentation.get("event"),
                detail_lines=[
                    line
                    for line in (
                        presentation.get("location"),
                        ", ".join(presentation.get("authors", [])) if presentation.get("authors") else "",
                    )
                    if line
                ],
            )
            for presentation in presentations
        ],
        *[
            _dissemination_item(
                record=item,
                category="press",
                type_label="Press",
                title=item.get("title"),
                url=item.get("url"),
                date=item.get("date"),
                date_label=str(item.get("date") or ""),
                source=item.get("outlet"),
                detail_lines=[line for line in (item.get("language"), item.get("country")) if line],
            )
            for item in press_items
        ],
        *[
            _dissemination_item(
                record=item,
                category="social",
                type_label=str(item.get("platform") or "Social media"),
                title=_social_media_title(item),
                url=item.get("url"),
                date=item.get("date"),
                date_label=str(item.get("date") or ""),
                source=", ".join(_social_account_labels(item.get("accounts", []))),
                detail_lines=[f"{item['views']} views"] if item.get("views") else [],
                description=item.get("description"),
            )
            for item in social_media_items
        ],
        *[
            _dissemination_item(
                record=item,
                category="tv",
                type_label="TV media",
                title=item.get("program"),
                url=item.get("url"),
                date=item.get("date"),
                date_label=str(item.get("date") or ""),
                source=item.get("channel"),
                detail_lines=[],
                description=item.get("description"),
            )
            for item in tv_media_items
        ],
    ]
    items.sort(key=lambda item: item["date"], reverse=True)
    counts = Counter(item["category"] for item in items)
    max_count = max(counts.values(), default=1)
    categories = [
        {
            **category,
            "count": counts[category["id"]],
            "share": _percentage(counts[category["id"]], max_count),
        }
        for category in DISSEMINATION_CATEGORIES
    ]
    return {
        "items": items,
        "categories": categories,
        "total": len(items),
        "publication_groups": _dissemination_publication_groups(items),
    }


def _dissemination_item(
    *,
    record: dict[str, Any],
    category: str,
    type_label: str,
    title: Any,
    url: Any,
    date: Any,
    date_label: str,
    source: Any,
    detail_lines: list[str],
    description: Any = None,
) -> dict[str, Any]:
    item = dict(record)
    item["category"] = category
    item["category_label"] = _dissemination_category_label(category)
    item["type_label"] = type_label
    item["display_title"] = str(title or record_name(record))
    item["url"] = str(url or "")
    item["date"] = str(date or "")
    item["date_label"] = date_label
    item["source"] = str(source or "")
    item["detail_lines"] = [str(line) for line in detail_lines if line]
    item["description"] = str(description or "")
    item["publication_count"] = len(item.get("resolved", {}).get("publication_ids", []))
    item["software_package_count"] = len(item.get("resolved", {}).get("software_package_ids", []))
    return item


def _dissemination_category_label(category_id: str) -> str:
    for category in DISSEMINATION_CATEGORIES:
        if category["id"] == category_id:
            return category["label"]
    return category_id


def _social_media_title(item: dict[str, Any]) -> str:
    platform = str(item.get("platform") or "Social media")
    description = str(item.get("description") or "").strip()
    if description:
        return description
    return f"{platform} item"


def _social_account_labels(accounts: list[Any]) -> list[str]:
    labels = []
    for account in accounts:
        text = str(account or "").strip()
        if not text:
            continue
        if "instagram.com/" in text:
            handle = text.split("instagram.com/", 1)[1].split("?", 1)[0].strip("/")
            labels.append(f"@{handle}" if handle else text)
        else:
            labels.append(text)
    return labels


def _dissemination_publication_groups(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for item in items:
        for publication in item.get("resolved", {}).get("publication_ids", []):
            publication_id = str(publication.get("id") or "")
            group = groups.setdefault(
                publication_id,
                {
                    "publication": publication,
                    "total": 0,
                    "counts": Counter(),
                },
            )
            group["total"] += 1
            group["counts"][item["category"]] += 1

    publication_groups = []
    for group in groups.values():
        badges = [
            {
                "category": category["id"],
                "label": category["label"],
                "count": group["counts"][category["id"]],
            }
            for category in DISSEMINATION_CATEGORIES
            if group["counts"][category["id"]]
        ]
        publication_groups.append(
            {
                "publication": group["publication"],
                "total": group["total"],
                "badges": badges,
            }
        )
    return sorted(
        publication_groups,
        key=lambda group: (
            str(group["publication"].get("publication_date") or ""),
            record_name(group["publication"]),
        ),
        reverse=True,
    )


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
        "organization_color": organization["color"],
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
        "color": _organization_color(organization_id),
    }


def _organization_color(organization_id: str) -> str:
    palette = {
        "organization_01": "#0f766e",
        "organization_02": "#2f7f9f",
        "organization_03": "#8a3342",
        "organization_04": "#a66f21",
    }
    fallback = ["#0f766e", "#2f7f9f", "#8a3342", "#a66f21", "#6d5fa3"]
    if organization_id in palette:
        return palette[organization_id]
    index = sum(ord(character) for character in organization_id) % len(fallback)
    return fallback[index]


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


def _career_timeline_view(
    degrees: list[dict[str, Any]],
    experience: list[dict[str, Any]],
    research_stays: list[dict[str, Any]],
    certifications: list[dict[str, Any]],
    honors: list[dict[str, Any]],
    grants: list[dict[str, Any]],
) -> dict[str, Any]:
    current_month = date.today().strftime("%Y-%m")
    position_grants = _grants_by_reference(grants, "position_ids")
    stay_grants = _grants_by_reference(grants, "stay_ids")
    degree_honors = _honors_by_degree(honors)
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


def _grants_by_reference(
    grants: list[dict[str, Any]],
    reference_field: str,
) -> dict[str, list[dict[str, Any]]]:
    by_reference: dict[str, list[dict[str, Any]]] = {}
    for grant in grants:
        for record_id in grant.get(reference_field, []):
            by_reference.setdefault(str(record_id), []).append(grant)
    return by_reference


def _honors_by_degree(honors: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_degree: dict[str, list[dict[str, Any]]] = {}
    for honor in honors:
        for degree_id in honor.get("degree_ids", []):
            by_degree.setdefault(str(degree_id), []).append(honor)
    return by_degree


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


def _organization_network_view(
    *,
    organizations: list[dict[str, Any]],
    degrees: list[dict[str, Any]],
    experience: list[dict[str, Any]],
    research_stays: list[dict[str, Any]],
    publications: list[dict[str, Any]],
    university_classes: list[dict[str, Any]],
    academic_supervision: list[dict[str, Any]],
) -> dict[str, Any]:
    organizations_by_id = {
        str(organization.get("id")): organization
        for organization in organizations
        if organization.get("id")
    }
    children_by_parent: dict[str | None, list[str]] = {}
    for organization in organizations:
        organization_id = str(organization.get("id") or "")
        parent_id = organization.get("parent_organization_id")
        parent_key = str(parent_id) if parent_id else None
        children_by_parent.setdefault(parent_key, []).append(organization_id)

    relationship_ids = [item["id"] for item in ORGANIZATION_RELATIONSHIP_TYPES]
    direct_values = {
        relationship_id: Counter(
            {organization_id: 0.0 for organization_id in organizations_by_id}
        )
        for relationship_id in relationship_ids
    }

    def add_duration(record: dict[str, Any], relationship_id: str, value: int) -> None:
        if value <= 0:
            return
        for organization_id in _specific_organization_ids(record, organizations_by_id):
            direct_values[relationship_id][organization_id] += float(value)

    for degree in degrees:
        add_duration(
            degree,
            "education",
            _month_span_to_present(degree.get("start_date"), degree.get("end_date")),
        )

    for position in experience:
        add_duration(
            position,
            "experience",
            _month_span_to_present(position.get("start_date"), position.get("end_date")),
        )

    for stay in research_stays:
        add_duration(
            stay,
            "stays",
            _month_span_to_present(stay.get("start_date"), stay.get("end_date")),
        )

    for publication in publications:
        organization_ids = _specific_organization_ids(publication, organizations_by_id)
        if not organization_ids:
            continue

        share = 1.0 / len(organization_ids)
        for organization_id in organization_ids:
            direct_values["publications"][organization_id] += share

    for course in university_classes:
        add_duration(
            course,
            "teaching",
            _month_span(course.get("start_date"), course.get("end_date")),
        )

    for supervision in academic_supervision:
        add_duration(supervision, "teaching", 1)

    aggregate_values: dict[str, dict[str, float]] = {
        relationship_id: {}
        for relationship_id in relationship_ids
    }

    def aggregate_for(relationship_id: str, organization_id: str) -> float:
        relationship_values = aggregate_values[relationship_id]
        if organization_id in relationship_values:
            return relationship_values[organization_id]

        value = float(direct_values[relationship_id].get(organization_id, 0.0))
        for child_id in children_by_parent.get(organization_id, []):
            value += aggregate_for(relationship_id, child_id)

        relationship_values[organization_id] = value
        return value

    for relationship_id in relationship_ids:
        for organization_id in organizations_by_id:
            aggregate_for(relationship_id, organization_id)

    root_ids = [
        organization_id
        for organization_id, organization in organizations_by_id.items()
        if not organization.get("parent_organization_id")
        or str(organization.get("parent_organization_id")) not in organizations_by_id
    ]

    rows = [
        _organization_relationship_row(
            relationship,
            root_ids,
            organizations_by_id,
            children_by_parent,
            aggregate_values[relationship["id"]],
        )
        for relationship in ORGANIZATION_RELATIONSHIP_TYPES
    ]
    rows = [row for row in rows if row["total"] > 0]
    if not rows:
        return {
            "rows": [],
            "cards": [],
            "relationship_types": ORGANIZATION_RELATIONSHIP_TYPES,
            "metrics": {"organizations": 0, "countries": 0, "cities": 0},
        }

    cards = _organization_card_groups(
        organizations_by_id,
        children_by_parent,
        aggregate_values,
        relationship_ids,
        root_ids,
    )
    visible_nodes = list(
        _flatten_organization_nodes(
            [
                node
                for row in rows
                for country in row["countries"]
                for node in country["nodes"]
            ]
        )
    )
    return {
        "rows": rows,
        "cards": cards,
        "relationship_types": ORGANIZATION_RELATIONSHIP_TYPES,
        "metrics": {
            "organizations": len({node["id"] for node in visible_nodes}),
            "countries": len({country["country"] for row in rows for country in row["countries"]}),
            "cities": len(
                {
                    node["city"]
                    for node in visible_nodes
                    if node.get("city")
                }
            ),
        },
    }


def _specific_organization_ids(
    record: dict[str, Any],
    organizations_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    organization_ids = [
        str(organization_id)
        for organization_id in record.get("organization_ids", [])
        if str(organization_id) in organizations_by_id
    ]
    if not organization_ids:
        return []

    return [
        organization_id
        for organization_id in organization_ids
        if not any(
            organization_id != other_id
            and _organization_is_ancestor(organization_id, other_id, organizations_by_id)
            for other_id in organization_ids
        )
    ]


def _organization_is_ancestor(
    possible_ancestor_id: str,
    organization_id: str,
    organizations_by_id: dict[str, dict[str, Any]],
) -> bool:
    parent_id = organizations_by_id.get(organization_id, {}).get("parent_organization_id")
    seen: set[str] = set()
    while parent_id:
        parent_text = str(parent_id)
        if parent_text in seen:
            return False
        if parent_text == possible_ancestor_id:
            return True
        seen.add(parent_text)
        parent_id = organizations_by_id.get(parent_text, {}).get("parent_organization_id")
    return False


def _organization_relationship_row(
    relationship: dict[str, str],
    root_ids: list[str],
    organizations_by_id: dict[str, dict[str, Any]],
    children_by_parent: dict[str | None, list[str]],
    values_by_organization: dict[str, float],
) -> dict[str, Any]:
    relationship_id = relationship["id"]
    root_nodes = [
        _organization_relationship_node(
            root_id,
            relationship,
            organizations_by_id,
            children_by_parent,
            values_by_organization,
            parent_value=0.0,
        )
        for root_id in root_ids
    ]
    root_nodes = [node for node in root_nodes if node]
    countries_by_name: dict[str, list[dict[str, Any]]] = {}
    for node in root_nodes:
        countries_by_name.setdefault(str(node["country"]), []).append(node)

    countries = []
    total = sum(float(node["value"]) for node in root_nodes)
    for country, nodes in countries_by_name.items():
        nodes = sorted(nodes, key=lambda node: (-float(node["value"]), str(node["label"])))
        country_total = sum(float(node["value"]) for node in nodes)
        for node in nodes:
            node["share"] = _float_percentage(float(node["value"]), country_total)

        country_share = _float_percentage(country_total, total)
        for node in nodes:
            _set_node_display_styles(node, country_share)
        countries.append(
            {
                "country": country,
                "value": country_total,
                "value_label": _organization_metric_value_label(relationship_id, country_total),
                "share": country_share,
                "global_share": country_share,
                "style": f"--country-share: {country_share}%;",
                "size_class": _relationship_segment_size_class(country_share),
                "children_style": _relationship_lane_stack_style(0),
                "nodes": nodes,
            }
        )
    countries = sorted(
        countries,
        key=lambda item: (-float(item["value"]), str(item["country"])),
    )
    max_country_label_lane = _assign_relationship_label_lanes(countries)
    _assign_relationship_tree_label_lanes(countries)

    return {
        **relationship,
        "total": total,
        "total_label": _organization_metric_value_label(relationship_id, total),
        "track_style": _relationship_lane_stack_style(max_country_label_lane),
        "countries": countries,
    }


def _organization_relationship_node(
    organization_id: str,
    relationship: dict[str, str],
    organizations_by_id: dict[str, dict[str, Any]],
    children_by_parent: dict[str | None, list[str]],
    values_by_organization: dict[str, float],
    *,
    parent_value: float,
    depth: int = 0,
    path: list[str] | None = None,
) -> dict[str, Any] | None:
    value = float(values_by_organization.get(organization_id, 0.0))
    if value <= 0:
        return None

    organization = organizations_by_id[organization_id]
    label = _organization_label(organization)
    location = organization.get("location", {}) or {}
    node_path = [*(path or []), label]
    child_nodes = [
        _organization_relationship_node(
            child_id,
            relationship,
            organizations_by_id,
            children_by_parent,
            values_by_organization,
            parent_value=value,
            depth=depth + 1,
            path=node_path,
        )
        for child_id in children_by_parent.get(organization_id, [])
    ]
    child_nodes = [node for node in child_nodes if node]
    return {
        "id": organization_id,
        "name": str(organization.get("name") or label),
        "label": label,
        "full_name": str(organization.get("full_name") or organization.get("name") or label),
        "type": str(organization.get("type") or ""),
        "website": str(organization.get("website") or ""),
        "country": str(location.get("country") or "Unknown"),
        "city": str(location.get("city") or ""),
        "depth": depth,
        "path": node_path,
        "path_label": " > ".join(node_path),
        "value": value,
        "value_label": _organization_metric_value_label(relationship["id"], value),
        "share": _float_percentage(value, parent_value) if parent_value else 0.0,
        "style": "",
        "tooltip": (
            f"{label}\n{relationship['label']}: "
            f"{_organization_metric_value_label(relationship['id'], value)}"
        ),
        "children": sorted(
            child_nodes,
            key=lambda child: (-float(child["value"]), str(child["label"])),
        ),
    }


def _set_node_display_styles(node: dict[str, Any], parent_global_share: float) -> None:
    node["global_share"] = parent_global_share * float(node.get("share") or 0.0) / 100.0
    node["style"] = f"--node-share: {node['share']}%;"
    node["size_class"] = _relationship_segment_size_class(float(node["share"]))
    parent_value = float(node["value"])
    for child in node.get("children", []):
        child["share"] = _float_percentage(float(child["value"]), parent_value)
        _set_node_display_styles(child, float(node["global_share"]))
    node["children_style"] = _relationship_lane_stack_style(0)


def _assign_relationship_tree_label_lanes(countries: list[dict[str, Any]]) -> None:
    max_lanes_by_depth: dict[int, int] = {}

    def assign_group(items: list[dict[str, Any]], depth: int) -> None:
        if not items:
            return
        max_lanes_by_depth[depth] = max(
            max_lanes_by_depth.get(depth, 0),
            _assign_relationship_label_lanes(items),
        )
        for item in items:
            assign_group(item.get("children", []), depth + 1)

    for country in countries:
        assign_group(country["nodes"], 0)

    for country in countries:
        country["children_style"] = _relationship_lane_stack_style(
            max_lanes_by_depth.get(0, 0)
        )
        for node in country["nodes"]:
            _set_relationship_tree_stack_style(node, max_lanes_by_depth)


def _set_relationship_tree_stack_style(
    node: dict[str, Any],
    max_lanes_by_depth: dict[int, int],
) -> None:
    node["children_style"] = _relationship_lane_stack_style(
        max_lanes_by_depth.get(int(node["depth"]) + 1, 0)
    )
    for child in node.get("children", []):
        _set_relationship_tree_stack_style(child, max_lanes_by_depth)


def _relationship_segment_size_class(share: float) -> str:
    if share < 9:
        return "is-tiny"
    if share < 18:
        return "is-small"
    return "is-regular"


def _assign_relationship_label_lanes(items: list[dict[str, Any]]) -> int:
    lane_ends: list[float] = []
    position = 0.0
    max_lane = 0
    container_global_share = sum(float(item.get("global_share") or 0.0) for item in items)
    if container_global_share <= 0:
        container_global_share = 100.0
    for item in items:
        share = float(item.get("share") or 0)
        start = position
        end = position + share
        label_text = " ".join(
            str(part)
            for part in (
                item.get("label") or item.get("country"),
                item.get("value_label"),
            )
            if part
        )
        label_width_global = min(38.0, max(12.0, len(label_text) * 0.72))
        label_width = min(
            96.0,
            max(12.0, (label_width_global / container_global_share) * 100.0),
        )
        if item.get("size_class") in {"is-small", "is-tiny"}:
            label_start = ((start + end) / 2) - (label_width / 2)
        else:
            label_start = start + 0.35
        label_start = max(0.0, min(label_start, max(0.0, 100.0 - label_width)))
        label_end = label_start + label_width

        lane = 0
        while lane < len(lane_ends) and label_start < lane_ends[lane] + 1.2:
            lane += 1
        if lane == len(lane_ends):
            lane_ends.append(label_end)
        else:
            lane_ends[lane] = label_end

        max_lane = max(max_lane, lane)
        item["label_lane"] = lane
        item["style"] = (
            f"{item.get('style', '')} "
            f"--label-lane: {lane}; --label-lane-offset: {lane * 34}px;"
        )
        position = end
    return max_lane


def _relationship_lane_stack_style(max_lane: int) -> str:
    return f"--max-label-lane: {max_lane}; --label-stack-offset: {max_lane * 34}px;"


def _organization_label(organization: dict[str, Any]) -> str:
    return str(organization.get("abbreviation") or organization.get("name") or organization.get("id") or "")


def _organization_metric_badges(metrics: dict[str, float]) -> list[dict[str, str]]:
    badges = []
    for relationship in ORGANIZATION_RELATIONSHIP_TYPES:
        relationship_id = relationship["id"]
        value = float(metrics.get(relationship_id, 0.0))
        if value <= 0:
            continue
        badges.append(
            {
                "id": relationship_id,
                "label": relationship["label"],
                "short": relationship["short"],
                "value": _organization_metric_compact_value(value),
                "value_label": _organization_metric_value_label(relationship_id, value),
            }
        )
    return badges


def _organization_metric_value_label(relationship_id: str, value: float) -> str:
    value_label = _organization_metric_compact_value(value)
    if relationship_id in {"education", "experience", "stays", "teaching"}:
        unit = "month" if value == 1 else "months"
        return f"{value_label} {unit}"
    if relationship_id == "publications":
        unit = "paper" if value == 1 else "papers"
        return f"{value_label} {unit}"
    return value_label


def _organization_metric_compact_value(value: float) -> str:
    if abs(value - round(value)) < 0.001:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _flatten_organization_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for node in nodes:
        flattened.append(node)
        flattened.extend(_flatten_organization_nodes(node.get("children", [])))
    return flattened


def _organization_card_groups(
    organizations_by_id: dict[str, dict[str, Any]],
    children_by_parent: dict[str | None, list[str]],
    aggregate_values: dict[str, dict[str, float]],
    relationship_ids: list[str],
    root_ids: list[str],
) -> list[dict[str, Any]]:
    card_nodes = [
        _organization_card_node(
            root_id,
            organizations_by_id,
            children_by_parent,
            aggregate_values,
            relationship_ids,
        )
        for root_id in root_ids
    ]
    card_nodes = [node for node in card_nodes if node]
    city_groups_by_country: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for node in _flatten_organization_nodes(card_nodes):
        city_groups_by_country.setdefault(str(node["country"]), {}).setdefault(
            str(node.get("city") or "Unspecified"),
            [],
        ).append(node)

    return [
        {
            "country": country,
            "cities": [
                {
                    "city": city,
                    "organizations": sorted(
                        organizations,
                        key=lambda node: (int(node["depth"]), str(node["label"])),
                    ),
                }
                for city, organizations in sorted(city_groups.items())
            ],
        }
        for country, city_groups in sorted(city_groups_by_country.items())
    ]


def _organization_card_node(
    organization_id: str,
    organizations_by_id: dict[str, dict[str, Any]],
    children_by_parent: dict[str | None, list[str]],
    aggregate_values: dict[str, dict[str, float]],
    relationship_ids: list[str],
    *,
    depth: int = 0,
    path: list[str] | None = None,
) -> dict[str, Any] | None:
    metrics = {
        relationship_id: float(aggregate_values[relationship_id].get(organization_id, 0.0))
        for relationship_id in relationship_ids
    }
    child_nodes = [
        _organization_card_node(
            child_id,
            organizations_by_id,
            children_by_parent,
            aggregate_values,
            relationship_ids,
            depth=depth + 1,
            path=[*(path or []), _organization_label(organizations_by_id[organization_id])],
        )
        for child_id in children_by_parent.get(organization_id, [])
    ]
    child_nodes = [node for node in child_nodes if node]
    if not any(value > 0 for value in metrics.values()) and not child_nodes:
        return None

    organization = organizations_by_id[organization_id]
    label = _organization_label(organization)
    location = organization.get("location", {}) or {}
    node_path = [*(path or []), label]
    return {
        "id": organization_id,
        "name": str(organization.get("name") or label),
        "label": label,
        "full_name": str(organization.get("full_name") or organization.get("name") or label),
        "type": str(organization.get("type") or ""),
        "website": str(organization.get("website") or ""),
        "country": str(location.get("country") or "Unknown"),
        "city": str(location.get("city") or ""),
        "depth": depth,
        "path_label": " > ".join(node_path),
        "metrics": _organization_metric_badges(metrics),
        "children": sorted(child_nodes, key=lambda child: str(child["label"])),
    }


def _month_span_to_present(start_date: Any, end_date: Any) -> int:
    effective_end = end_date or date.today().strftime("%Y-%m")
    return _month_span(start_date, effective_end)


def _float_percentage(value: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return round((value / total) * 100, 2)


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
    for item in sorted(timeline_projects, key=_timeline_recent_sort_month, reverse=True):
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


def _timeline_recent_sort_month(row: dict[str, Any]) -> int:
    commit_months = row["commit_months"]
    candidates = [
        _month_number(row["project"].get("github", {}).get("last_commit_at")),
        *list(commit_months),
        *(
            month
            for month in (row["created_month"], row["pushed_month"])
            if month is not None
        ),
    ]
    return max((month for month in candidates if month is not None), default=0)


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
