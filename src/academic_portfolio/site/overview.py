from __future__ import annotations

import unicodedata
from collections import Counter, defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date
from typing import Any

from markupsafe import escape

from academic_portfolio.i18n import Translator, format_duration, format_number, load_translator
from academic_portfolio.render import record_name
from academic_portfolio.site.common import (
    _month_number,
    _month_span_to_present,
    _organization_full_label,
    _organization_short_label,
)

_ACTIVE_TRANSLATOR: ContextVar[Translator | None] = ContextVar(
    "academic_portfolio_overview_translator",
    default=None,
)


@contextmanager
def _using_translator(translator: Translator) -> Any:
    token = _ACTIVE_TRANSLATOR.set(translator)
    try:
        yield
    finally:
        _ACTIVE_TRANSLATOR.reset(token)


def _current_translator() -> Translator:
    return _ACTIVE_TRANSLATOR.get() or load_translator()


def _overview_summary(
    *,
    degrees: list[dict[str, Any]],
    experience: list[dict[str, Any]],
    research_stays: list[dict[str, Any]],
    publications: list[dict[str, Any]],
    software_projects: list[dict[str, Any]],
    software_packages: list[dict[str, Any]],
    research_projects: list[dict[str, Any]],
    reviewing: list[dict[str, Any]],
    scientific_articles: list[dict[str, Any]],
    presentations: list[dict[str, Any]],
    press_items: list[dict[str, Any]],
    social_media_items: list[dict[str, Any]],
    tv_media_items: list[dict[str, Any]],
    university_classes: list[dict[str, Any]],
    academic_supervision: list[dict[str, Any]],
    teaching_innovation_projects: list[dict[str, Any]],
    honors: list[dict[str, Any]],
    grants: list[dict[str, Any]],
    organizations: list[dict[str, Any]],
    metrics: dict[str, int],
    translator: Translator | None = None,
) -> dict[str, Any]:
    active_translator = translator or load_translator()
    with _using_translator(active_translator):
        return _build_overview_summary(
            degrees=degrees,
            experience=experience,
            research_stays=research_stays,
            publications=publications,
            software_projects=software_projects,
            software_packages=software_packages,
            research_projects=research_projects,
            reviewing=reviewing,
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


def _build_overview_summary(
    *,
    degrees: list[dict[str, Any]],
    experience: list[dict[str, Any]],
    research_stays: list[dict[str, Any]],
    publications: list[dict[str, Any]],
    software_projects: list[dict[str, Any]],
    software_packages: list[dict[str, Any]],
    research_projects: list[dict[str, Any]],
    reviewing: list[dict[str, Any]],
    scientific_articles: list[dict[str, Any]],
    presentations: list[dict[str, Any]],
    press_items: list[dict[str, Any]],
    social_media_items: list[dict[str, Any]],
    tv_media_items: list[dict[str, Any]],
    university_classes: list[dict[str, Any]],
    academic_supervision: list[dict[str, Any]],
    teaching_innovation_projects: list[dict[str, Any]],
    honors: list[dict[str, Any]],
    grants: list[dict[str, Any]],
    organizations: list[dict[str, Any]],
    metrics: dict[str, int],
) -> dict[str, Any]:
    organizations_by_id = {str(organization.get("id")): organization for organization in organizations}
    collaboration_counts = _publication_collaboration_counts(publications)
    teaching_summary = _teaching_overview(
        university_classes,
        academic_supervision,
        teaching_innovation_projects,
    )
    dissemination_summary = _dissemination_overview(
        scientific_articles,
        presentations,
        press_items,
        social_media_items,
        tv_media_items,
    )
    software_summary = _software_overview(software_projects, software_packages)
    education_records = _sort_records_by_date(degrees, reverse=False)
    experience_by_institution = _duration_by_root_organization(
        experience,
        organizations_by_id,
    )
    stay_summaries = _stay_summaries(research_stays, organizations_by_id)
    return {
        "education": {
            "degrees": [_degree_summary(degree) for degree in education_records],
            "degrees_text": _join_semicolon_phrases(
                _degree_summary(degree) for degree in education_records
            ),
            "degrees_html": _join_semicolon_phrases(
                _degree_summary_html(degree) for degree in education_records
            ),
        },
        "experience": {
            "by_institution": experience_by_institution,
            "by_institution_text": _join_semicolon_phrases(
                item["summary"] for item in experience_by_institution
            ),
            "by_institution_html": _join_semicolon_phrases(
                item["summary_html"] for item in experience_by_institution
            ),
            "institution_count": len(
                _record_root_organization_ids(
                    [*experience, *research_stays],
                    organizations_by_id,
                )
            ),
        },
        "research": {
            "journal_papers": metrics["journal_papers"],
            "conference_papers": metrics["conference_papers"],
            "journal_papers_phrase": _count_phrase("journal paper", metrics["journal_papers"]),
            "conference_papers_phrase": _count_phrase(
                "conference paper",
                metrics["conference_papers"],
            ),
            "project_roles": _project_roles(research_projects),
            "project_roles_text": _join_phrases(_project_roles(research_projects)),
            "reviewed_manuscripts": sum(
                int(item.get("manuscripts_reviewed") or 0) for item in reviewing
            ),
        },
        "internationalization": {
            **collaboration_counts,
            "international_publications_phrase": _count_phrase(
                "paper in international collaboration",
                collaboration_counts["international_publications"],
            ),
            "national_multicity_publications_phrase": _count_phrase(
                "paper in national collaboration",
                collaboration_counts["national_multicity_publications"],
            ),
            "stays": stay_summaries,
            "stays_text": _join_semicolon_phrases(
                stay["summary"] for stay in stay_summaries
            ),
            "stays_html": _join_semicolon_phrases(
                stay["summary_html"] for stay in stay_summaries
            ),
            "total_stay_months": sum(
                _month_span_to_present(stay.get("start_date"), stay.get("end_date"))
                for stay in research_stays
            ),
        },
        "software": software_summary,
        "teaching": teaching_summary,
        "dissemination": dissemination_summary,
        "recognition": _recognition_overview(honors, grants, organizations_by_id),
    }


def _publication_collaboration_counts(publications: list[dict[str, Any]]) -> dict[str, int]:
    international = 0
    national_multi_city = 0

    for publication in publications:
        countries: set[str] = set()
        city_keys: set[tuple[str, str]] = set()
        for organization in publication.get("resolved", {}).get("organization_ids", []):
            location = organization.get("location", {})
            country = str(location.get("country") or "")
            city = str(location.get("city") or "")
            if country:
                countries.add(country)
            if country and city:
                city_keys.add((country, city))

        if len(countries) > 1:
            international += 1
        elif len(countries) == 1 and len(city_keys) > 1:
            national_multi_city += 1

    return {
        "international_publications": international,
        "national_multicity_publications": national_multi_city,
    }


def _teaching_overview(
    university_classes: list[dict[str, Any]],
    academic_supervision: list[dict[str, Any]],
    teaching_innovation_projects: list[dict[str, Any]],
) -> dict[str, Any]:
    total_hours = sum(float(course.get("workload_hours") or 0) for course in university_classes)
    academic_years = {
        str(course.get("academic_year"))
        for course in university_classes
        if course.get("academic_year")
    }
    degree_programs = {
        str(course.get("degree"))
        for course in university_classes
        if course.get("degree")
    }
    supervision_counts = _supervision_counts(academic_supervision)
    institution_years = _teaching_years_by_organization(university_classes)
    first_teaching_context = _first_teaching_context(university_classes)
    return {
        "institution_years": institution_years,
        "institution_years_text": _join_phrases(
            item["summary"] for item in institution_years
        ),
        "total_hours": total_hours,
        "total_hours_label": _format_number(total_hours),
        "academic_years": len(academic_years),
        "first_academic_year": first_teaching_context["academic_year"],
        "first_institution": first_teaching_context["institution"],
        "courses": len(university_classes),
        "degree_programs": len(degree_programs),
        "teaching_innovation_projects": len(teaching_innovation_projects),
        "teaching_innovation_projects_phrase": _count_phrase(
            "teaching innovation project",
            len(teaching_innovation_projects),
        ),
        "supervision_counts": supervision_counts,
        "supervision_text": _join_phrases(
            _supervision_phrase(label, count)
            for label, count in supervision_counts.items()
            if count > 0
        ),
    }


def _first_teaching_context(university_classes: list[dict[str, Any]]) -> dict[str, str]:
    for course in sorted(
        university_classes,
        key=lambda course: str(course.get("start_date") or course.get("academic_year") or ""),
    ):
        organizations = course.get("resolved", {}).get("organization_ids", [])
        if course.get("academic_year") and organizations:
            return {
                "academic_year": str(course.get("academic_year")),
                "institution": _organization_full_label(organizations[0]),
            }
    return {"academic_year": "", "institution": ""}


def _supervision_counts(academic_supervision: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "final degree project": 0,
        "final master project": 0,
        "doctoral thesis": 0,
        "external internship": 0,
    }
    for supervision in academic_supervision:
        supervision_type = _normalized_type_text(supervision.get("type"))
        if "internship" in supervision_type or "practica" in supervision_type:
            counts["external internship"] += 1
        elif "master" in supervision_type or "tfm" in supervision_type:
            counts["final master project"] += 1
        elif (
            "doctoral" in supervision_type
            or "thesis" in supervision_type
            or "tesis" in supervision_type
        ):
            counts["doctoral thesis"] += 1
        elif "degree" in supervision_type or "grado" in supervision_type or "tfg" in supervision_type:
            counts["final degree project"] += 1
    return counts


def _normalized_type_text(value: Any) -> str:
    text = str(value or "").lower()
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(character for character in normalized if not unicodedata.combining(character))


def _dissemination_overview(
    scientific_articles: list[dict[str, Any]],
    presentations: list[dict[str, Any]],
    press_items: list[dict[str, Any]],
    social_media_items: list[dict[str, Any]],
    tv_media_items: list[dict[str, Any]],
) -> dict[str, Any]:
    known_views = [
        int(item["views"])
        for item in social_media_items
        if item.get("views") not in (None, "")
    ]
    activity_counts = {
        "scientific dissemination article": len(scientific_articles),
        "presentation": len(presentations),
        "press item": len(press_items),
        "social media item": len(social_media_items),
        "TV media item": len(tv_media_items),
    }
    return {
        "activity_text": _join_phrases(
            _count_phrase(label, count)
            for label, count in activity_counts.items()
            if count > 0
        ),
        "press_outlets": len({item.get("outlet") for item in press_items if item.get("outlet")}),
        "known_social_views": sum(known_views),
        "known_social_views_label": _format_number(sum(known_views)),
        "highest_social_views": max(known_views, default=0),
        "highest_social_views_label": _format_number(max(known_views, default=0)),
    }


def _software_overview(
    software_projects: list[dict[str, Any]],
    software_packages: list[dict[str, Any]],
) -> dict[str, Any]:
    github_records = [project["github"] for project in software_projects if project.get("github")]
    package_downloads = sum(
        int(package.get("package_stats", {}).get("total_downloads") or 0)
        for package in software_packages
    )
    return {
        "software_projects": len(software_projects),
        "software_packages": len(software_packages),
        "repositories_with_stats": len(github_records),
        "total_stars": sum(int(stats.get("stargazers_count") or 0) for stats in github_records),
        "total_forks": sum(int(stats.get("forks_count") or 0) for stats in github_records),
        "package_downloads": package_downloads,
        "package_downloads_label": _format_number(package_downloads),
    }


def _recognition_overview(
    honors: list[dict[str, Any]],
    grants: list[dict[str, Any]],
    organizations_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "honors": [record_name(honor) for honor in honors],
        "grants": [_grant_summary(grant, organizations_by_id) for grant in grants],
        "honors_text": _join_semicolon_phrases(record_name(honor) for honor in honors),
        "honors_html": _join_semicolon_phrases(_strong(record_name(honor)) for honor in honors),
        "grants_text": _join_semicolon_phrases(
            _grant_summary(grant, organizations_by_id) for grant in grants
        ),
        "grants_html": _join_semicolon_phrases(
            _grant_summary_html(grant, organizations_by_id) for grant in grants
        ),
        "honors_phrase": _count_phrase("honor", len(honors)),
        "grants_phrase": _count_phrase("grant", len(grants)),
    }


def _duration_by_root_organization(
    records: list[dict[str, Any]],
    organizations_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    intervals_by_organization: defaultdict[str, list[tuple[int, int]]] = defaultdict(list)
    labels_by_organization: dict[str, str] = {}

    for record in records:
        interval = _record_month_interval(record)
        if interval is None:
            continue

        for organization in _root_organizations_for_record(record, organizations_by_id):
            organization_id = str(organization.get("id"))
            intervals_by_organization[organization_id].append(interval)
            labels_by_organization[organization_id] = _organization_full_label(organization)

    return [
        {
            "label": labels_by_organization[organization_id],
            "months": _merged_month_span(intervals),
            "duration": _format_duration(_merged_month_span(intervals)),
            "summary": _current_translator().t(
                "cv.summary_fragments.at",
                value=_format_duration(_merged_month_span(intervals)),
                organization=labels_by_organization[organization_id],
            ),
            "summary_html": _current_translator().t(
                "cv.summary_fragments.at",
                value=_html_escape(_format_duration(_merged_month_span(intervals))),
                organization=_strong(labels_by_organization[organization_id]),
            ),
            "latest_month": max(end for _, end in intervals),
        }
        for organization_id, intervals in sorted(
            intervals_by_organization.items(),
            key=lambda item: (
                -max(end for _, end in item[1]),
                labels_by_organization[item[0]],
            ),
        )
    ]


def _record_month_interval(record: dict[str, Any]) -> tuple[int, int] | None:
    start = _month_number(record.get("start_date"))
    end = _month_number(record.get("end_date") or date.today().strftime("%Y-%m"))
    if start is None and end is None:
        return None
    if start is None:
        start = end
    if end is None:
        end = start
    return (min(start, end), max(start, end))


def _merged_month_span(intervals: list[tuple[int, int]]) -> int:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
            continue
        merged[-1][1] = max(merged[-1][1], end)
    return sum((end - start + 1) for start, end in merged)


def _root_organizations_for_record(
    record: dict[str, Any],
    organizations_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    root_organizations: dict[str, dict[str, Any]] = {}
    for organization in record.get("resolved", {}).get("organization_ids", []):
        root = _root_organization(organization, organizations_by_id)
        organization_id = str(root.get("id"))
        root_organizations[organization_id] = root
    return list(root_organizations.values())


def _root_organization(
    organization: dict[str, Any],
    organizations_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    current = organization
    seen_ids: set[str] = set()
    while current.get("parent_organization_id"):
        current_id = str(current.get("id"))
        if current_id in seen_ids:
            break
        seen_ids.add(current_id)
        parent = organizations_by_id.get(str(current.get("parent_organization_id")))
        if not parent:
            break
        current = parent
    return current


def _record_root_organization_ids(
    records: list[dict[str, Any]],
    organizations_by_id: dict[str, dict[str, Any]],
) -> set[str]:
    return {
        str(organization.get("id"))
        for record in records
        for organization in _root_organizations_for_record(record, organizations_by_id)
        if organization.get("id")
    }


def _sort_records_by_date(
    records: list[dict[str, Any]],
    *,
    reverse: bool,
) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda record: str(
            record.get("date_awarded")
            or record.get("end_date")
            or record.get("start_date")
            or "",
        ),
        reverse=reverse,
    )


def _teaching_years_by_organization(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    years_by_organization: defaultdict[str, set[str]] = defaultdict(set)
    labels_by_organization: dict[str, str] = {}

    for record in records:
        academic_year = str(record.get("academic_year") or "")
        if not academic_year:
            continue
        for organization in record.get("resolved", {}).get("organization_ids", []):
            organization_id = str(organization.get("id"))
            years_by_organization[organization_id].add(academic_year)
            labels_by_organization[organization_id] = _organization_full_label(organization)

    return [
        {
            "label": labels_by_organization[organization_id],
            "years": len(years),
            "summary": _current_translator().t(
                "cv.summary_fragments.at",
                value=_count_phrase("academic year", len(years)),
                organization=labels_by_organization[organization_id],
            ),
        }
        for organization_id, years in sorted(
            years_by_organization.items(),
            key=lambda item: (-len(item[1]), labels_by_organization[item[0]]),
        )
    ]


def _stay_summaries(
    research_stays: list[dict[str, Any]],
    organizations_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    stays = []
    for stay in research_stays:
        months = _month_span_to_present(stay.get("start_date"), stay.get("end_date"))
        location = stay.get("location", {})
        city = str(location.get("city") or "")
        country = str(location.get("country") or "")
        place = ", ".join(part for part in (city, country) if part)
        organizations = stay.get("resolved", {}).get("organization_ids", [])
        organization_text = _organization_hierarchy_text(
            organizations,
            organizations_by_id,
        )
        label = (
            _current_translator().t(
                "cv.summary_fragments.located_in",
                organization=organization_text,
                place=place,
            )
            if organization_text and place
            else organization_text or place
        )
        if not label:
            label = record_name(stay, _current_translator())
        label_html = _stay_label_html(
            stay,
            organizations_by_id,
            place=place,
            fallback_label=label,
        )
        stays.append(
            {
                "label": label,
                "months": months,
                "summary": _current_translator().t(
                    "cv.summary_fragments.at",
                    value=_format_duration(months),
                    organization=label,
                ),
                "summary_html": _current_translator().t(
                    "cv.summary_fragments.at",
                    value=_html_escape(_format_duration(months)),
                    organization=label_html,
                ),
            }
        )
    return stays


def _organization_hierarchy_text(
    organizations: list[dict[str, Any]],
    organizations_by_id: dict[str, dict[str, Any]],
) -> str:
    chains = _deepest_organization_chains(organizations, organizations_by_id)
    return _join_semicolon_phrases(_organization_chain_text(chain) for chain in chains)


def _organization_hierarchy_html(
    organizations: list[dict[str, Any]],
    organizations_by_id: dict[str, dict[str, Any]],
) -> str:
    chains = _deepest_organization_chains(organizations, organizations_by_id)
    return _join_semicolon_phrases(
        _strong(_organization_chain_text(chain)) for chain in chains
    )


def _stay_label_html(
    stay: dict[str, Any],
    organizations_by_id: dict[str, dict[str, Any]],
    *,
    place: str,
    fallback_label: str,
) -> str:
    organizations = stay.get("resolved", {}).get("organization_ids", [])
    organization_html = _organization_hierarchy_html(organizations, organizations_by_id)
    if organization_html and place:
        return _current_translator().t(
            "cv.summary_fragments.located_in",
            organization=organization_html,
            place=_html_escape(place),
        )
    if organization_html:
        return organization_html
    return _html_escape(fallback_label)


def _deepest_organization_chains(
    organizations: list[dict[str, Any]],
    organizations_by_id: dict[str, dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    chains_by_id = {
        str(organization.get("id")): _organization_chain(organization, organizations_by_id)
        for organization in organizations
        if organization.get("id")
    }
    ancestor_ids = {
        str(ancestor.get("id"))
        for chain in chains_by_id.values()
        for ancestor in chain[1:]
        if ancestor.get("id")
    }
    deepest_chains = [
        chain
        for organization_id, chain in chains_by_id.items()
        if organization_id not in ancestor_ids
    ]
    return sorted(
        deepest_chains,
        key=lambda chain: (-len(chain), _organization_full_label(chain[0])),
    )


def _organization_chain(
    organization: dict[str, Any],
    organizations_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    chain = [organization]
    seen_ids = {str(organization.get("id"))}
    current = organization
    while current.get("parent_organization_id"):
        parent = organizations_by_id.get(str(current.get("parent_organization_id")))
        if not parent:
            break
        parent_id = str(parent.get("id"))
        if parent_id in seen_ids:
            break
        chain.append(parent)
        seen_ids.add(parent_id)
        current = parent
    return chain


def _organization_chain_text(chain: list[dict[str, Any]]) -> str:
    labels = [
        _organization_full_label(organization)
        if index == len(chain) - 1
        else _organization_short_label(organization)
        for index, organization in enumerate(chain)
    ]
    if not labels:
        return ""
    text = labels[0]
    for label in labels[1:]:
        text = _current_translator().t(
            "cv.summary_fragments.belonging_to",
            value=text,
            organization=label,
        )
    return text


def _project_roles(research_projects: list[dict[str, Any]]) -> list[str]:
    role_counts = Counter(
        str(project.get("participation") or "project member")
        for project in research_projects
    )
    return [
        _current_translator().t(
            "cv.summary_fragments.role_in_projects",
            role=_lower_initial(_localized_participation_label(role)),
            projects=_count_phrase("research project", count),
        )
        for role, count in sorted(role_counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _localized_participation_label(role: str) -> str:
    normalized = f" {role.lower().replace('/', ' ').replace('-', ' ').replace('.', ' ')} "
    translator = _current_translator()
    if (
        "principal investigator" in normalized
        or "investigador principal" in normalized
        or " co pi " in normalized
        or " co ip " in normalized
        or " pi " in normalized
        or " ip " in normalized
    ):
        return translator.t("cv.labels.pi_copi")
    if "research team" in normalized or "equipo de investigación" in normalized:
        return translator.t("cv.labels.research_team_member")
    if "working team" in normalized or "equipo de trabajo" in normalized:
        return translator.t("cv.labels.working_team_member")
    return f"{role[:1].lower()}{role[1:]}"


def _lower_initial(value: str) -> str:
    return f"{value[:1].lower()}{value[1:]}" if value else ""


def _degree_summary(degree: dict[str, Any]) -> str:
    organization_text = _join_semicolon_phrases(
        _organization_full_label(organization)
        for organization in degree.get("resolved", {}).get("organization_ids", [])
    )
    if not organization_text:
        return record_name(degree, _current_translator())
    return _current_translator().t(
        "cv.summary_fragments.degree_from",
        degree=record_name(degree, _current_translator()),
        organization=organization_text,
    )


def _degree_summary_html(degree: dict[str, Any]) -> str:
    organization_text = _join_semicolon_phrases(
        _organization_full_label(organization)
        for organization in degree.get("resolved", {}).get("organization_ids", [])
    )
    degree_name = record_name(degree, _current_translator())
    if not organization_text:
        return _strong(degree_name)
    return _current_translator().t(
        "cv.summary_fragments.degree_from",
        degree=_strong(degree_name),
        organization=_html_escape(organization_text),
    )


def _grant_summary(
    grant: dict[str, Any],
    organizations_by_id: dict[str, dict[str, Any]],
) -> str:
    covered_records = [
        *grant.get("resolved", {}).get("position_ids", []),
        *grant.get("resolved", {}).get("stay_ids", []),
        *grant.get("resolved", {}).get("degree_ids", []),
    ]
    covered_text = _join_phrases(
        _covered_record_summary(record, organizations_by_id) for record in covered_records
    )
    if not covered_text:
        return record_name(grant, _current_translator())
    return _current_translator().t(
        "cv.summary_fragments.covering",
        grant=record_name(grant, _current_translator()),
        records=covered_text,
    )


def _grant_summary_html(
    grant: dict[str, Any],
    organizations_by_id: dict[str, dict[str, Any]],
) -> str:
    covered_records = [
        *grant.get("resolved", {}).get("position_ids", []),
        *grant.get("resolved", {}).get("stay_ids", []),
        *grant.get("resolved", {}).get("degree_ids", []),
    ]
    covered_text = _join_phrases(
        _covered_record_summary(record, organizations_by_id) for record in covered_records
    )
    grant_name = record_name(grant, _current_translator())
    if not covered_text:
        return _strong(grant_name)
    return _current_translator().t(
        "cv.summary_fragments.covering",
        grant=_strong(grant_name),
        records=_html_escape(covered_text),
    )


def _covered_record_summary(
    record: dict[str, Any],
    organizations_by_id: dict[str, dict[str, Any]],
) -> str:
    organization_text = _root_organization_text_for_record(record, organizations_by_id)
    if not organization_text:
        return record_name(record, _current_translator())
    return _current_translator().t(
        "cv.summary_fragments.at",
        value=record_name(record, _current_translator()),
        organization=organization_text,
    )


def _html_escape(value: Any) -> str:
    return str(escape(str(value or "")))


def _strong(value: Any) -> str:
    return f"<strong>{_html_escape(value)}</strong>"


def _root_organization_text_for_record(
    record: dict[str, Any],
    organizations_by_id: dict[str, dict[str, Any]],
) -> str:
    roots: dict[str, dict[str, Any]] = {}
    for organization_id in record.get("organization_ids", []):
        organization = organizations_by_id.get(str(organization_id))
        if not organization:
            continue
        root = _root_organization(organization, organizations_by_id)
        roots[str(root.get("id"))] = root
    return _join_phrases(_organization_full_label(root) for root in roots.values())


def _count_phrase(label: str, count: int) -> str:
    label_key = label.replace(" ", "_").replace("/", "_").lower()
    phrase_key = f"cv.counts.{label_key}"
    text = _current_translator().plural(
        phrase_key,
        count,
        display_count=_format_number(count),
    )
    if text != phrase_key:
        return text
    suffix = "" if count == 1 else "s"
    return f"{_format_number(count)} {label}{suffix}"


def _supervision_phrase(label: str, count: int) -> str:
    return _count_phrase(label, count)


def _format_duration(months: int) -> str:
    return format_duration(months, _current_translator())


def _join_phrases(
    values: Any,
    *,
    delimiter: str = ", ",
    use_delimiter_for_two: bool = False,
) -> str:
    items = [str(value) for value in values if value]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    conjunction = _current_translator().t("lists.conjunction")
    if len(items) == 2:
        if use_delimiter_for_two:
            return f"{items[0]}{delimiter}{conjunction} {items[1]}"
        return f"{items[0]} {conjunction} {items[1]}"
    final_delimiter = delimiter
    if _current_translator().language == "es" and delimiter == ", ":
        final_delimiter = " "
    return f"{delimiter.join(items[:-1])}{final_delimiter}{conjunction} {items[-1]}"


def _join_semicolon_phrases(values: Any) -> str:
    return _join_phrases(values, delimiter="; ", use_delimiter_for_two=True)


def _format_number(value: Any) -> str:
    return format_number(value, _current_translator())
