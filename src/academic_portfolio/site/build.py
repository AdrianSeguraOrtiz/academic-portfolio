from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import copy2
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from academic_portfolio.github import collect_github_project_stats
from academic_portfolio.loader import load_data
from academic_portfolio.packages import collect_package_stats
from academic_portfolio.render import date_range, record_name
from academic_portfolio.resolver import PortfolioResolver
from academic_portfolio.site.career import _career_details_view, _career_timeline_view
from academic_portfolio.site.collaborations import _collaboration_view
from academic_portfolio.site.dissemination import _dissemination_view
from academic_portfolio.site.organizations import _organization_network_view
from academic_portfolio.site.overview import _format_number, _overview_summary
from academic_portfolio.site.projects import _project_records
from academic_portfolio.site.publications import (
    _publication_year_chart,
    _publication_year_groups,
    _tagged_publication_records,
)
from academic_portfolio.site.software import (
    _attach_github_stats,
    _attach_package_stats,
    _software_github_summary,
    _software_language_chart,
    _software_timeline,
)
from academic_portfolio.site.teaching import _teaching_hours_chart, _teaching_timeline_view
from academic_portfolio.view_records import (
    profile_with_current_activity,
    resolved_records,
    sort_records_by_field,
)


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
    profile = profile_with_current_activity(resolver)

    journal_papers = _tagged_publication_records(
        resolver,
        "research/publications.yaml",
        "journal_papers",
        "journal",
        reverse=True,
    )
    conference_papers = _tagged_publication_records(
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
    teaching_hours_chart = _teaching_hours_chart(
        university_classes,
        teaching_timeline["legend"],
    )
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
    overview = _overview_summary(
        degrees=degrees,
        experience=experience,
        research_stays=research_stays,
        publications=publications,
        software_projects=software_projects,
        software_packages=software_packages,
        research_projects=research_projects,
        reviewing=resolved_records(
            resolver,
            "research/reviewing.yaml",
            "reviewing",
            reverse=True,
        ),
        scientific_articles=scientific_articles,
        presentations=presentations,
        press_items=press_items,
        social_media_items=social_media_items,
        tv_media_items=tv_media_items,
        university_classes=university_classes,
        academic_supervision=academic_supervision,
        teaching_innovation_projects=teaching_innovation_projects,
        honors=honors,
        grants=grants,
        organizations=organizations,
        metrics=metrics,
    )
    metrics.update(
        {
            "package_downloads": overview["software"]["package_downloads"],
            "known_social_views": overview["dissemination"]["known_social_views"],
            "teaching_hours": overview["teaching"]["total_hours"],
            "work_institutions": overview["experience"]["institution_count"],
            "reviewed_manuscripts": overview["research"]["reviewed_manuscripts"],
        }
    )

    return {
        "profile": profile,
        "metrics": metrics,
        "overview": overview,
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
        "career_details": _career_details_view(
            degrees,
            experience,
            research_stays,
            certifications,
            honors,
            grants,
        ),
        "projects": projects,
        "research_projects": research_projects,
        "teaching": {
            "university_classes": university_classes,
            "academic_supervision": academic_supervision,
            "teaching_innovation_projects": teaching_innovation_projects,
        },
        "teaching_hours_chart": teaching_hours_chart,
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
        "publication_groups": _publication_year_groups(publications),
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


