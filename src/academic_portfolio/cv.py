from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
import json
from pathlib import Path
from shutil import copy2
from typing import Any
import re
import tomllib

from academic_portfolio.loader import load_data
from academic_portfolio.render import render_template
from academic_portfolio.resolver import PortfolioResolver
from academic_portfolio.site.common import _month_number, _month_span_to_present
from academic_portfolio.view_records import (
    attach_related_records,
    profile_with_current_activity,
    resolved_records,
    sort_records_by_field,
)

SECTION_DETAIL_LEVELS = {"hidden", "aggregate", "micro", "compact", "standard", "full"}
SECTION_DETAIL_RANKS = {
    "hidden": 0,
    "aggregate": 1,
    "micro": 2,
    "compact": 3,
    "standard": 4,
    "full": 5,
}
CV_STYLES = {"rich", "sober"}
CV_DENSITIES = {"normal", "compact", "micro"}
CV_FONT_SCALES = {"normal", "small", "xsmall"}
CV_SECTIONS = {
    "profile",
    "current_positions",
    "degrees",
    "certifications",
    "experience",
    "research_stays",
    "honors",
    "grants",
    "publications",
    "software_projects",
    "software_packages",
    "research_projects",
    "teaching",
    "dissemination",
    "reviewing",
}
NUCLEAR_SECTIONS = {
    "degrees",
    "experience",
    "research_stays",
    "honors",
    "grants",
    "publications",
    "research_projects",
}
AGGREGABLE_LIMITS = {
    "max_certifications",
    "max_software_projects",
    "max_software_packages",
    "max_reviewing",
    "max_university_classes",
    "max_academic_supervision",
    "max_teaching_innovation_projects",
    "max_scientific_articles",
    "max_presentations",
    "max_press",
    "max_social_media",
    "max_tv_media",
}
AGGREGABLE_SECTIONS = {
    "certifications",
    "software_projects",
    "software_packages",
    "teaching",
    "dissemination",
    "reviewing",
}
PDF_PAGE_PATTERN = re.compile(rb"/Type\s*/Page\b")


@dataclass(frozen=True)
class CVModel:
    name: str
    title: str
    language: str
    template: str
    style: str
    page_limit: int | None
    sections: dict[str, str]
    layout: dict[str, Any]
    limits: dict[str, Any]

    @property
    def reverse_chronological(self) -> bool:
        return bool(self.layout.get("reverse_chronological", True))

    @property
    def template_name(self) -> str:
        return self.template

    @property
    def density(self) -> str:
        return str(self.layout.get("density", "normal"))

    @property
    def font_scale(self) -> str:
        return str(self.layout.get("font_scale", "normal"))

    def includes_section(self, section: str) -> bool:
        return self.sections.get(section, "hidden") != "hidden"

    def section_detail(self, section: str) -> str:
        return self.sections.get(section, "hidden")

    def section_detail_at_least(self, section: str, detail: str) -> bool:
        return SECTION_DETAIL_RANKS[self.section_detail(section)] >= SECTION_DETAIL_RANKS[detail]


@dataclass(frozen=True)
class CVOutput:
    model: CVModel
    output_path: Path
    html_path: Path
    content: str
    asset_paths: list[Path]
    page_count: int | None = None
    page_limit: int | None = None
    fit_status: str = "not_checked"


@dataclass(frozen=True)
class CVRecordSet:
    profile: dict[str, Any]
    degrees: list[dict[str, Any]]
    certifications: list[dict[str, Any]]
    experience: list[dict[str, Any]]
    research_stays: list[dict[str, Any]]
    honors: list[dict[str, Any]]
    grants: list[dict[str, Any]]
    journal_papers: list[dict[str, Any]]
    conference_papers: list[dict[str, Any]]
    publications: list[dict[str, Any]]
    software_projects: list[dict[str, Any]]
    software_packages: list[dict[str, Any]]
    research_projects: list[dict[str, Any]]
    reviewing: list[dict[str, Any]]
    university_classes: list[dict[str, Any]]
    academic_supervision: list[dict[str, Any]]
    teaching_innovation_projects: list[dict[str, Any]]
    scientific_articles: list[dict[str, Any]]
    presentations: list[dict[str, Any]]
    press: list[dict[str, Any]]
    social_media: list[dict[str, Any]]
    tv_media: list[dict[str, Any]]


def load_cv_model(model_path: Path | str) -> CVModel:
    path = Path(model_path)
    with path.open("rb") as handle:
        raw_model = tomllib.load(handle)

    _validate_model_shape(path, raw_model)

    name = str(raw_model["name"])
    style = str(raw_model.get("style", "sober"))
    page_limit = _parse_page_limit(raw_model.get("page_limit"))
    sections = {str(section): str(detail) for section, detail in raw_model["sections"].items()}
    layout = dict(raw_model.get("layout", {}))
    limits = dict(raw_model.get("limits", {}))

    _validate_model_values(
        path=path,
        style=style,
        page_limit=page_limit,
        sections=sections,
        layout=layout,
        limits=limits,
    )

    return CVModel(
        name=name,
        title=str(raw_model["title"]),
        language=str(raw_model.get("language", "en")),
        template=str(raw_model.get("template", f"{name}.html.j2")),
        style=style,
        page_limit=page_limit,
        sections=sections,
        layout=layout,
        limits=limits,
    )


def _validate_model_shape(path: Path, raw_model: dict[str, Any]) -> None:
    allowed_fields = {
        "name",
        "title",
        "language",
        "template",
        "style",
        "page_limit",
        "sections",
        "layout",
        "limits",
    }
    unknown_fields = sorted(set(raw_model) - allowed_fields)
    if unknown_fields:
        raise ValueError(f"{path} defines unknown CV model fields: {unknown_fields}")

    required_fields = {"name", "title", "sections"}
    missing_fields = sorted(required_fields - set(raw_model))
    if missing_fields:
        raise ValueError(f"{path} is missing required CV model fields: {missing_fields}")

    if not isinstance(raw_model["sections"], dict):
        raise ValueError(f"{path} must define [sections] as a table of detail levels.")

    if "layout" in raw_model and not isinstance(raw_model["layout"], dict):
        raise ValueError(f"{path} must define [layout] as a TOML table.")

    if "limits" in raw_model and not isinstance(raw_model["limits"], dict):
        raise ValueError(f"{path} must define [limits] as a TOML table.")


def _validate_model_values(
    *,
    path: Path,
    style: str,
    page_limit: int | None,
    sections: dict[str, str],
    layout: dict[str, Any],
    limits: dict[str, Any],
) -> None:
    if style not in CV_STYLES:
        raise ValueError(f"{path} has unsupported CV style: {style}")

    if page_limit is not None and page_limit <= 0:
        raise ValueError(f"{path} page_limit must be a positive integer when defined.")

    unknown_sections = sorted(set(sections) - CV_SECTIONS)
    if unknown_sections:
        raise ValueError(f"{path} defines unknown CV sections: {unknown_sections}")

    invalid_details = {
        section: detail
        for section, detail in sections.items()
        if detail not in SECTION_DETAIL_LEVELS
    }
    if invalid_details:
        raise ValueError(f"{path} defines invalid section detail levels: {invalid_details}")

    missing_nuclear_sections = sorted(NUCLEAR_SECTIONS - set(sections))
    if missing_nuclear_sections:
        raise ValueError(
            f"{path} must explicitly include nuclear CV sections: {missing_nuclear_sections}"
        )

    hidden_nuclear_sections = sorted(
        section
        for section in NUCLEAR_SECTIONS
        if sections.get(section) == "hidden"
    )
    if hidden_nuclear_sections:
        raise ValueError(f"{path} cannot hide nuclear CV sections: {hidden_nuclear_sections}")

    density = str(layout.get("density", "normal"))
    if density not in CV_DENSITIES:
        raise ValueError(f"{path} has unsupported CV density: {density}")

    font_scale = str(layout.get("font_scale", "normal"))
    if font_scale not in CV_FONT_SCALES:
        raise ValueError(f"{path} has unsupported CV font_scale: {font_scale}")

    unknown_limits = sorted(set(limits) - AGGREGABLE_LIMITS)
    if unknown_limits:
        raise ValueError(f"{path} defines unsupported CV limits: {unknown_limits}")

    for name, value in limits.items():
        try:
            parsed_limit = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{path} limit {name} must be an integer: {value}") from exc
        if parsed_limit < 0:
            raise ValueError(f"{path} limit {name} must be non-negative: {value}")


def _parse_page_limit(value: Any) -> int | None:
    if value is None:
        return None

    parsed_limit = int(value)
    if parsed_limit <= 0:
        raise ValueError(f"CV page_limit must be a positive integer: {value}")
    return parsed_limit


def model_path_for(model: str, model_dir: Path | str = "cv_models") -> Path:
    path = Path(model)
    if path.suffix:
        return path
    return Path(model_dir) / f"{model}.toml"


def build_cv_view(model: CVModel, resolver: PortfolioResolver) -> dict[str, Any]:
    source_records = _load_cv_records(model, resolver)
    aggregate_records = _aggregate_record_mapping(source_records)
    records = _records_for_model(model, source_records)
    record_mapping = _record_mapping(records)
    site_view = _cv_site_view(resolver)
    core = _core_view(model, record_mapping)
    aggregates = _aggregate_view(model, record_mapping, aggregate_records)

    view: dict[str, Any] = {
        "model": model,
        "sections": _active_sections(model),
        "section_details": model.sections,
        "layout": model.layout,
        "render_options": _render_options_for_model(model),
        "core": core,
        "aggregates": aggregates,
        "summary": _cv_summary_view(model, site_view, source_records.profile),
    }

    if model.style == "rich":
        view["rich_view"] = _rich_cv_view(site_view)
    else:
        view["sober_view"] = _sober_cv_view(core, aggregates)

    return view


def _load_cv_records(model: CVModel, resolver: PortfolioResolver) -> CVRecordSet:
    profile = profile_with_current_activity(resolver)

    degrees = resolved_records(
        resolver,
        "career/degrees.yaml",
        "degrees",
        reverse=model.reverse_chronological,
    )
    experience = resolved_records(
        resolver,
        "career/experience.yaml",
        "positions",
        reverse=model.reverse_chronological,
    )
    research_stays = resolved_records(
        resolver,
        "career/research_stays.yaml",
        "stays",
        reverse=model.reverse_chronological,
    )
    honors = resolved_records(
        resolver,
        "career/honors.yaml",
        "honors",
        reverse=model.reverse_chronological,
    )
    grants = resolved_records(
        resolver,
        "career/grants.yaml",
        "grants",
        reverse=model.reverse_chronological,
    )
    journal_papers = resolved_records(
        resolver,
        "research/publications.yaml",
        "journal_papers",
        reverse=model.reverse_chronological,
    )
    conference_papers = resolved_records(
        resolver,
        "research/publications.yaml",
        "conference_papers",
        reverse=model.reverse_chronological,
    )
    certifications = resolved_records(
        resolver,
        "career/certifications.yaml",
        "certifications",
        reverse=model.reverse_chronological,
    )
    software_projects = resolved_records(
        resolver,
        "research/software_projects.yaml",
        "projects",
        reverse=model.reverse_chronological,
    )
    software_packages = resolved_records(
        resolver,
        "research/software_packages.yaml",
        "software_packages",
        reverse=False,
    )
    _attach_cached_package_stats(software_packages)
    funded_projects = resolved_records(
        resolver,
        "research/research_projects.yaml",
        "funded_projects",
        reverse=model.reverse_chronological,
    )
    reviewing = resolved_records(
        resolver,
        "research/reviewing.yaml",
        "reviewing",
        reverse=model.reverse_chronological,
    )
    university_classes = resolved_records(
        resolver,
        "activities/teaching/university_classes.yaml",
        "university_classes",
        reverse=model.reverse_chronological,
    )
    academic_supervision = resolved_records(
        resolver,
        "activities/teaching/academic_supervision.yaml",
        "academic_supervision",
        reverse=model.reverse_chronological,
    )
    teaching_innovation_projects = resolved_records(
        resolver,
        "activities/teaching/teaching_innovation_projects.yaml",
        "teaching_innovation_projects",
        reverse=model.reverse_chronological,
    )
    scientific_articles = resolved_records(
        resolver,
        "activities/dissemination/scientific_dissemination_articles.yaml",
        "scientific_dissemination_articles",
        reverse=model.reverse_chronological,
    )
    presentations = resolved_records(
        resolver,
        "activities/dissemination/presentations.yaml",
        "presentations",
        reverse=model.reverse_chronological,
    )
    press = resolved_records(
        resolver,
        "activities/dissemination/press.yaml",
        "press_items",
        reverse=model.reverse_chronological,
    )
    social_media = resolved_records(
        resolver,
        "activities/dissemination/social_media.yaml",
        "social_media_items",
        reverse=model.reverse_chronological,
    )
    tv_media = resolved_records(
        resolver,
        "activities/dissemination/tv_media.yaml",
        "tv_items",
        reverse=model.reverse_chronological,
    )
    attach_related_records(degrees, honors, "degree_ids", "related_honors")
    attach_related_records(experience, grants, "position_ids", "related_grants")
    attach_related_records(research_stays, grants, "stay_ids", "related_grants")
    journal_papers, conference_papers, publications = _publication_records_for_model(
        model,
        journal_papers,
        conference_papers,
    )

    return CVRecordSet(
        profile=profile,
        degrees=degrees,
        certifications=certifications,
        experience=experience,
        research_stays=research_stays,
        honors=honors,
        grants=grants,
        journal_papers=journal_papers,
        conference_papers=conference_papers,
        publications=publications,
        software_projects=software_projects,
        software_packages=software_packages,
        research_projects=funded_projects,
        reviewing=reviewing,
        university_classes=university_classes,
        academic_supervision=academic_supervision,
        teaching_innovation_projects=teaching_innovation_projects,
        scientific_articles=scientific_articles,
        presentations=presentations,
        press=press,
        social_media=social_media,
        tv_media=tv_media,
    )


def _records_for_model(model: CVModel, records: CVRecordSet) -> CVRecordSet:
    return replace(
        records,
        certifications=_limit_by_model(model, records.certifications, "max_certifications"),
        software_projects=_limit_by_model(
            model,
            records.software_projects,
            "max_software_projects",
        ),
        software_packages=_limit_by_model(
            model,
            records.software_packages,
            "max_software_packages",
        ),
        reviewing=_limit_by_model(model, records.reviewing, "max_reviewing"),
        university_classes=_limit_by_model(
            model,
            records.university_classes,
            "max_university_classes",
        ),
        academic_supervision=_limit_by_model(
            model,
            records.academic_supervision,
            "max_academic_supervision",
        ),
        teaching_innovation_projects=_limit_by_model(
            model,
            records.teaching_innovation_projects,
            "max_teaching_innovation_projects",
        ),
        scientific_articles=_limit_by_model(
            model,
            records.scientific_articles,
            "max_scientific_articles",
        ),
        presentations=_limit_by_model(model, records.presentations, "max_presentations"),
        press=_limit_by_model(model, records.press, "max_press"),
        social_media=_limit_by_model(model, records.social_media, "max_social_media"),
        tv_media=_limit_by_model(model, records.tv_media, "max_tv_media"),
    )


def _record_mapping(records: CVRecordSet) -> dict[str, Any]:
    return {
        "profile": records.profile,
        "degrees": records.degrees,
        "certifications": records.certifications,
        "experience": records.experience,
        "research_stays": records.research_stays,
        "honors": records.honors,
        "grants": records.grants,
        "journal_papers": records.journal_papers,
        "conference_papers": records.conference_papers,
        "publications": records.publications,
        "software_projects": records.software_projects,
        "software_packages": records.software_packages,
        "research_projects": records.research_projects,
        "reviewing": records.reviewing,
        "university_classes": records.university_classes,
        "academic_supervision": records.academic_supervision,
        "teaching_innovation_projects": records.teaching_innovation_projects,
        "scientific_articles": records.scientific_articles,
        "presentations": records.presentations,
        "press": records.press,
        "social_media": records.social_media,
        "tv_media": records.tv_media,
    }


def _aggregate_record_mapping(records: CVRecordSet) -> dict[str, Any]:
    return {
        "certifications": records.certifications,
        "software_projects": records.software_projects,
        "software_packages": records.software_packages,
        "reviewing": records.reviewing,
        "university_classes": records.university_classes,
        "academic_supervision": records.academic_supervision,
        "teaching_innovation_projects": records.teaching_innovation_projects,
        "scientific_articles": records.scientific_articles,
        "presentations": records.presentations,
        "press": records.press,
        "social_media": records.social_media,
        "tv_media": records.tv_media,
    }


def _active_sections(model: CVModel) -> list[str]:
    return [section for section, detail in model.sections.items() if detail != "hidden"]


def _rich_cv_view(site_view: dict[str, Any]) -> dict[str, Any]:
    return {
        "site": site_view,
        "snapshots": {
            "overview": site_view.get("overview", {}),
            "collaborations": site_view.get("collaborations", {}),
            "publications": {
                "chart": site_view.get("publication_chart", []),
                "groups": site_view.get("publication_groups", []),
            },
            "software": {
                "github": site_view.get("software_github", {}),
                "timeline": site_view.get("software_timeline", {}),
                "languages": site_view.get("software_language_chart", []),
            },
            "career": {
                "timeline": site_view.get("career_timeline", {}),
                "details": site_view.get("career_details", {}),
            },
            "teaching": {
                "hours_chart": site_view.get("teaching_hours_chart", {}),
                "timeline": site_view.get("teaching_timeline", {}),
            },
            "dissemination": site_view.get("dissemination_hub", {}),
            "organizations": site_view.get("organization_network", {}),
        },
    }


def _sober_cv_view(core: dict[str, Any], aggregates: dict[str, Any]) -> dict[str, Any]:
    return {
        "atomic_sections": {
            "degrees": core["education"]["items"],
            "experience": core["experience"]["items"],
            "research_stays": core["research_stays"]["items"],
            "honors": core["honors"]["items"],
            "grants": core["grants"]["items"],
            "publications": core["publications"]["items"],
            "research_projects": core["research_projects"]["items"],
        },
        "experience_groups": core["experience"]["groups"],
        "aggregate_sections": {
            "certifications": aggregates["certifications"]["items"],
            "software_projects": aggregates["software"]["projects"]["items"],
            "software_packages": aggregates["software"]["packages"]["items"],
            "teaching_classes": aggregates["teaching"]["classes"]["items"],
            "teaching_supervision": aggregates["teaching"]["supervision"]["items"],
            "teaching_innovation_projects": aggregates["teaching"]["innovation_projects"]["items"],
            "dissemination": {
                "scientific_articles": aggregates["dissemination"]["scientific_articles"]["items"],
                "presentations": aggregates["dissemination"]["presentations"]["items"],
                "press": aggregates["dissemination"]["press"]["items"],
                "social_media": aggregates["dissemination"]["social_media"]["items"],
                "tv_media": aggregates["dissemination"]["tv_media"]["items"],
            },
            "reviewing": aggregates["reviewing"]["items"],
        },
    }


def _cv_site_view(resolver: PortfolioResolver) -> dict[str, Any]:
    from academic_portfolio.site.build import build_site_view

    return build_site_view(
        resolver,
        github_stats_by_url=_cached_github_stats(),
        package_stats_by_id=_cached_package_stats(),
    )


def _cv_summary_view(
    model: CVModel,
    site_view: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    full = _summary_level(
        level="full",
        paragraphs=_summary_full(site_view, profile),
    )
    compact = _summary_level(
        level="compact",
        paragraphs=_summary_compact(site_view, profile),
    )
    micro = _summary_level(
        level="micro",
        paragraphs=_summary_micro(site_view, profile),
    )
    levels = {
        "full": full,
        "compact": compact,
        "micro": micro,
    }
    active_level = _summary_level_for_model(model)
    return {
        "active_level": active_level,
        "active": levels[active_level],
        "levels": levels,
        "summary_full": full,
        "summary_compact": compact,
        "summary_micro": micro,
    }


def _summary_level(level: str, paragraphs: list[str]) -> dict[str, Any]:
    clean_paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    return {
        "level": level,
        "paragraphs": clean_paragraphs,
        "text": "\n\n".join(clean_paragraphs),
    }


def _summary_level_for_model(model: CVModel) -> str:
    if model.style == "rich" or model.page_limit is None:
        return "full"
    if model.page_limit <= 3:
        return "micro"
    if model.page_limit <= 4:
        return "compact"
    return "full"


def _summary_full(site_view: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    overview = site_view.get("overview", {})
    metrics = site_view.get("metrics", {})
    education = overview.get("education", {})
    experience = overview.get("experience", {})
    internationalization = overview.get("internationalization", {})
    research = overview.get("research", {})
    software = overview.get("software", {})
    teaching = overview.get("teaching", {})
    dissemination = overview.get("dissemination", {})
    recognition = overview.get("recognition", {})

    return [
        _summary_intro(profile),
        _summary_paragraph(
            _sentence(
                "My academic background comprises",
                education.get("degrees_text"),
            ),
            _sentence(
                "My professional experience spans",
                experience.get("by_institution_text"),
            ),
            _stay_sentence(internationalization),
        ),
        _summary_paragraph(
            _research_output_sentence(research),
            _collaboration_sentence(internationalization),
            _sentence(
                "Within funded research projects, my roles include",
                research.get("project_roles_text"),
            ),
            _count_sentence(
                "I have reviewed",
                metrics.get("reviewed_manuscripts"),
                "manuscript",
                "for scientific journals",
            ),
        ),
        _summary_paragraph(
            _software_output_sentence(metrics),
            _github_sentence(software),
            _downloads_sentence(metrics, software),
        ),
        _summary_paragraph(
            _teaching_sentence(teaching),
            _sentence(
                "It also includes",
                teaching.get("teaching_innovation_projects_phrase"),
            ),
            _sentence(
                "Academic supervision includes",
                teaching.get("supervision_text"),
            ),
        ),
        _summary_paragraph(
            _sentence(
                "Scientific dissemination activity covers",
                dissemination.get("activity_text"),
            ),
            _count_sentence(
                "Press coverage spans",
                dissemination.get("press_outlets"),
                "outlet",
            ),
            _social_views_sentence(metrics, dissemination),
        ),
        _recognition_sentence(recognition),
    ]


def _summary_compact(site_view: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    overview = site_view.get("overview", {})
    metrics = site_view.get("metrics", {})
    education = overview.get("education", {})
    experience = overview.get("experience", {})
    internationalization = overview.get("internationalization", {})
    research = overview.get("research", {})
    software = overview.get("software", {})
    teaching = overview.get("teaching", {})
    dissemination = overview.get("dissemination", {})
    recognition = overview.get("recognition", {})

    return [
        _summary_paragraph(
            _summary_intro(profile),
            _sentence("My academic background comprises", education.get("degrees_text")),
            _sentence("My professional experience spans", experience.get("by_institution_text")),
            _stay_sentence(internationalization),
        ),
        _summary_paragraph(
            _research_output_sentence(research),
            _collaboration_sentence(internationalization),
            _sentence("Research project roles include", research.get("project_roles_text")),
            _software_output_sentence(metrics),
            _downloads_sentence(metrics, software),
        ),
        _summary_paragraph(
            _teaching_sentence(teaching),
            _sentence("Dissemination covers", dissemination.get("activity_text")),
            _social_views_sentence(metrics, dissemination),
            _recognition_sentence(recognition),
        ),
    ]


def _summary_micro(site_view: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    overview = site_view.get("overview", {})
    metrics = site_view.get("metrics", {})
    research = overview.get("research", {})
    software = overview.get("software", {})
    teaching = overview.get("teaching", {})
    recognition = overview.get("recognition", {})

    return [
        _summary_paragraph(
            _summary_intro(profile),
            _research_output_sentence(research),
            _software_output_sentence(metrics),
            _downloads_sentence(metrics, software),
            _teaching_micro_sentence(teaching),
            _recognition_counts_sentence(recognition),
        )
    ]


def _summary_intro(profile: dict[str, Any]) -> str:
    profile_summary = str(profile.get("research_profile", {}).get("summary") or "")
    generated_intro = (
        "I am a computer scientist and researcher in artificial intelligence applied "
        "to bioinformatics, working at the intersection of computational methods, "
        "biomedical data analysis, evolutionary computation, and reproducible "
        "scientific software."
    )
    if profile_summary:
        return f"{profile_summary} {generated_intro}"
    return generated_intro


def _summary_paragraph(*sentences: str) -> str:
    return " ".join(sentence for sentence in sentences if sentence)


def _sentence(prefix: str, value: Any) -> str:
    value_text = str(value or "")
    if not value_text:
        return ""
    return f"{prefix} {value_text}."


def _count_sentence(
    prefix: str,
    count: Any,
    singular_label: str,
    suffix: str = "",
) -> str:
    try:
        parsed_count = int(count)
    except (TypeError, ValueError):
        return ""
    label = singular_label if parsed_count == 1 else f"{singular_label}s"
    suffix_text = f" {suffix}" if suffix else ""
    return f"{prefix} {_format_number(parsed_count)} {label}{suffix_text}."


def _research_output_sentence(research: dict[str, Any]) -> str:
    journal_phrase = research.get("journal_papers_phrase")
    conference_phrase = research.get("conference_papers_phrase")
    if journal_phrase and conference_phrase:
        return f"My research output includes {journal_phrase} and {conference_phrase}."
    return _sentence("My research output includes", journal_phrase or conference_phrase)


def _collaboration_sentence(internationalization: dict[str, Any]) -> str:
    phrases = [
        internationalization.get("international_publications_phrase")
        if internationalization.get("international_publications")
        else "",
        internationalization.get("national_multicity_publications_phrase")
        if internationalization.get("national_multicity_publications")
        else "",
    ]
    collaboration_text = _join_summary_phrases(phrases)
    if not collaboration_text:
        return ""
    return f"The publication record includes {collaboration_text}."


def _stay_sentence(internationalization: dict[str, Any]) -> str:
    stays_text = str(internationalization.get("stays_text") or "")
    total_months = int(internationalization.get("total_stay_months") or 0)
    if not stays_text and not total_months:
        return ""
    if stays_text and total_months:
        return (
            f"This is complemented by research stays of {stays_text}, "
            f"for a total of {_format_number(total_months)} months abroad."
        )
    return _sentence("This is complemented by research stays of", stays_text)


def _software_output_sentence(metrics: dict[str, Any]) -> str:
    project_count = int(metrics.get("software_projects") or 0)
    package_count = int(metrics.get("software_packages") or 0)
    phrases = [
        _count_phrase("software project", project_count) if project_count else "",
        _count_phrase("published package", package_count) if package_count else "",
    ]
    output_text = _join_summary_phrases(phrases)
    if not output_text:
        return ""
    return f"The software portfolio includes {output_text}."


def _github_sentence(software: dict[str, Any]) -> str:
    repositories = int(software.get("repositories_with_stats") or 0)
    if not repositories:
        return ""
    return (
        f"The public software portfolio spans {_format_number(repositories)} repositories, "
        f"with {_format_number(software.get('total_stars') or 0)} stars and "
        f"{_format_number(software.get('total_forks') or 0)} forks."
    )


def _downloads_sentence(metrics: dict[str, Any], software: dict[str, Any]) -> str:
    downloads = int(metrics.get("package_downloads") or 0)
    if not downloads:
        return ""
    return (
        "Package usage records "
        f"{software.get('package_downloads_label') or _format_number(downloads)} "
        "recorded downloads."
    )


def _teaching_sentence(teaching: dict[str, Any]) -> str:
    institution_years = str(teaching.get("institution_years_text") or "")
    total_hours = str(teaching.get("total_hours_label") or "")
    academic_years = int(teaching.get("academic_years") or 0)
    courses = int(teaching.get("courses") or 0)
    degree_programs = int(teaching.get("degree_programs") or 0)
    if not total_hours and not courses:
        return ""
    context = f" includes {institution_years}" if institution_years else ""
    parts = [
        f"{total_hours} classroom hours" if total_hours else "",
        _count_phrase("academic year", academic_years) if academic_years else "",
        _count_phrase("course", courses) if courses else "",
        _count_phrase("degree programme", degree_programs) if degree_programs else "",
    ]
    return f"My teaching activity{context}, amounting to {_join_summary_phrases(parts)}."


def _teaching_micro_sentence(teaching: dict[str, Any]) -> str:
    total_hours = str(teaching.get("total_hours_label") or "")
    courses = int(teaching.get("courses") or 0)
    if not total_hours and not courses:
        return ""
    parts = [
        f"{total_hours} classroom hours" if total_hours else "",
        _count_phrase("course", courses) if courses else "",
    ]
    return f"Teaching activity totals {_join_summary_phrases(parts)}."


def _social_views_sentence(metrics: dict[str, Any], dissemination: dict[str, Any]) -> str:
    known_views = int(metrics.get("known_social_views") or 0)
    if not known_views:
        return ""
    sentence = (
        "Social media items with available metrics account for "
        f"{dissemination.get('known_social_views_label') or _format_number(known_views)} "
        "known views"
    )
    highest_views = int(dissemination.get("highest_social_views") or 0)
    if highest_views:
        sentence += (
            ", with the highest recorded item reaching "
            f"{dissemination.get('highest_social_views_label') or _format_number(highest_views)} views"
        )
    return f"{sentence}."


def _recognition_sentence(recognition: dict[str, Any]) -> str:
    parts = []
    honors_text = str(recognition.get("honors_text") or "")
    grants_text = str(recognition.get("grants_text") or "")
    if honors_text:
        parts.append(f"{recognition.get('honors_phrase')}: {honors_text}")
    if grants_text:
        parts.append(f"{recognition.get('grants_phrase')}: {grants_text}")
    if not parts:
        return ""
    return f"This academic trajectory has been recognized and supported through {'; '.join(parts)}."


def _recognition_counts_sentence(recognition: dict[str, Any]) -> str:
    parts = [
        recognition.get("honors_phrase"),
        recognition.get("grants_phrase"),
    ]
    recognition_text = _join_summary_phrases(parts)
    if not recognition_text:
        return ""
    return f"The trajectory has been recognized and supported through {recognition_text}."


def _count_phrase(label: str, count: int) -> str:
    suffix = "" if count == 1 else "s"
    return f"{_format_number(count)} {label}{suffix}"


def _join_summary_phrases(values: Any) -> str:
    items = [str(value) for value in values if value]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _cached_github_stats(
    cache_path: Path | str = "build/cache/github_repositories.json",
) -> dict[str, dict[str, Any]]:
    data = _read_json_cache(cache_path)
    repositories = data.get("repositories", {})
    return repositories if isinstance(repositories, dict) else {}


def _cached_package_stats(
    cache_path: Path | str = "build/cache/software_packages.json",
) -> dict[str, dict[str, Any]]:
    data = _read_json_cache(cache_path)
    stats_by_id = data.get("stats_by_id", {})
    return stats_by_id if isinstance(stats_by_id, dict) else {}


def _attach_cached_package_stats(packages: list[dict[str, Any]]) -> None:
    package_stats_by_id = _cached_package_stats()
    for package in packages:
        package_id = str(package.get("id") or "")
        if package_id in package_stats_by_id:
            package["package_stats"] = package_stats_by_id[package_id]


def _read_json_cache(cache_path: Path | str) -> dict[str, Any]:
    path = Path(cache_path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _core_view(model: CVModel, records: dict[str, Any]) -> dict[str, Any]:
    profile = records["profile"]
    return {
        "profile": profile,
        "current_activity": {
            "detail": model.section_detail("current_positions"),
            "positions": _finalize_entries(
                model,
                [
                    _prepare_position(record, model.section_detail("current_positions"))
                    for record in profile.get("current_positions", [])
                ],
            ),
            "stays": _finalize_entries(
                model,
                [
                    _prepare_stay(record, model.section_detail("current_positions"))
                    for record in profile.get("current_stays", [])
                ],
            ),
        },
        "education": _entry_block(model, "degrees", records["degrees"], _prepare_degree),
        "experience": _experience_block(model, records["experience"]),
        "research_stays": _entry_block(
            model,
            "research_stays",
            records["research_stays"],
            _prepare_stay,
        ),
        "honors": _entry_block(model, "honors", records["honors"], _prepare_honor),
        "grants": _entry_block(model, "grants", records["grants"], _prepare_grant),
        "publications": _publication_block(model, records),
        "research_projects": _entry_block(
            model,
            "research_projects",
            records["research_projects"],
            _prepare_research_project,
        ),
    }


def _aggregate_view(
    model: CVModel,
    records: dict[str, Any],
    aggregate_records: dict[str, Any],
) -> dict[str, Any]:
    certifications = _entry_block(
        model,
        "certifications",
        records["certifications"],
        _prepare_certification,
    )
    software = {
        "detail": _combined_detail(model, "software_projects", "software_packages"),
        "projects": _entry_block(
            model,
            "software_projects",
            records["software_projects"],
            _prepare_software_project,
        ),
        "packages": _entry_block(
            model,
            "software_packages",
            records["software_packages"],
            _prepare_software_package,
        ),
        "summary": _software_summary(
            aggregate_records["software_projects"],
            aggregate_records["software_packages"],
        ),
    }
    teaching = {
        "detail": model.section_detail("teaching"),
        "classes": _entry_block(
            model,
            "teaching",
            records["university_classes"],
            _prepare_university_class,
        ),
        "supervision": _entry_block(
            model,
            "teaching",
            records["academic_supervision"],
            _prepare_academic_supervision,
        ),
        "innovation_projects": _entry_block(
            model,
            "teaching",
            records["teaching_innovation_projects"],
            _prepare_teaching_innovation_project,
        ),
        "summary": _teaching_summary(
            aggregate_records["university_classes"],
            aggregate_records["academic_supervision"],
            aggregate_records["teaching_innovation_projects"],
        ),
    }
    dissemination = {
        "detail": model.section_detail("dissemination"),
        "scientific_articles": _entry_block(
            model,
            "dissemination",
            records["scientific_articles"],
            _prepare_scientific_article,
        ),
        "presentations": _entry_block(
            model,
            "dissemination",
            records["presentations"],
            _prepare_presentation,
        ),
        "press": _entry_block(model, "dissemination", records["press"], _prepare_press_item),
        "social_media": _entry_block(
            model,
            "dissemination",
            records["social_media"],
            _prepare_social_media_item,
        ),
        "tv_media": _entry_block(model, "dissemination", records["tv_media"], _prepare_tv_item),
        "summary": _dissemination_summary(
            aggregate_records["scientific_articles"],
            aggregate_records["presentations"],
            aggregate_records["press"],
            aggregate_records["social_media"],
            aggregate_records["tv_media"],
        ),
    }
    reviewing = _entry_block(model, "reviewing", records["reviewing"], _prepare_reviewing)
    return {
        "certifications": certifications,
        "software": software,
        "teaching": teaching,
        "dissemination": dissemination,
        "reviewing": {
            **reviewing,
            "summary": _reviewing_summary(aggregate_records["reviewing"]),
        },
        "highlights": _aggregate_highlights(software, teaching, dissemination, reviewing),
    }


def _entry_block(
    model: CVModel,
    section: str,
    records: list[dict[str, Any]],
    prepare_entry: Any,
) -> dict[str, Any]:
    detail = model.section_detail(section)
    if detail == "hidden":
        return {"detail": detail, "records": records, "items": []}
    items = [prepare_entry(record, detail) for record in records]
    return {
        "detail": detail,
        "records": records,
        "items": _finalize_entries(model, items),
    }


def _experience_block(model: CVModel, records: list[dict[str, Any]]) -> dict[str, Any]:
    block = _entry_block(model, "experience", records, _prepare_position)
    block["groups"] = _experience_groups(model, records, block["detail"])
    return block


def _experience_groups(
    model: CVModel,
    records: list[dict[str, Any]],
    detail: str,
) -> list[dict[str, Any]]:
    if detail == "hidden":
        return []

    grouped_records: dict[str, list[dict[str, Any]]] = {}
    organizations_by_key: dict[str, dict[str, Any]] = {}

    for record in records:
        organization = _position_group_organization(record)
        organization_key = str(organization.get("id") or "unknown")
        grouped_records.setdefault(organization_key, []).append(record)
        organizations_by_key[organization_key] = organization

    groups = []
    for organization_key, group_records in grouped_records.items():
        sorted_records = sorted(
            group_records,
            key=_record_sort_month,
            reverse=model.reverse_chronological,
        )
        role_entries = _finalize_entries(
            model,
            [_prepare_position(record, detail) for record in sorted_records],
        )
        roles = [
            _experience_role(record, entry)
            for record, entry in zip(sorted_records, role_entries, strict=True)
        ]
        organization = organizations_by_key[organization_key]
        groups.append(
            {
                "id": f"experience_group_{organization_key}",
                "organization": organization,
                "title": _organization_display_label(organization),
                "url": _record_url(organization) if model.layout.get("include_urls", True) else "",
                "location": _experience_group_location(group_records, organization),
                "period": _experience_group_period(group_records),
                "duration": _format_duration(_experience_group_months(group_records)),
                "sort_month": max(_record_sort_month(record) for record in group_records),
                "roles": roles,
                "progression": " <- ".join(role["entry"]["title"] for role in roles),
            }
        )

    if model.reverse_chronological:
        return sorted(groups, key=lambda group: (-group["sort_month"], group["title"]))
    return sorted(groups, key=lambda group: (group["sort_month"], group["title"]))


def _experience_role(record: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    dedication = str(record.get("dedication") or "")
    employment_type = str(record.get("employment_type") or "")
    return {
        "entry": entry,
        "employment_type": employment_type,
        "dedication": "" if dedication == employment_type else dedication,
        "department": str(record.get("department") or ""),
        "duration": _format_duration(_record_months(record)),
    }


def _position_group_organization(record: dict[str, Any]) -> dict[str, Any]:
    organizations = _resolved(record, "organization_ids")
    if not organizations:
        return {"id": "unknown", "name": "Unspecified institution"}
    return organizations[0]


def _organization_display_label(organization: dict[str, Any]) -> str:
    return str(
        organization.get("name")
        or organization.get("full_name")
        or organization.get("abbreviation")
        or "Unspecified institution"
    )


def _experience_group_location(
    records: list[dict[str, Any]],
    organization: dict[str, Any],
) -> str:
    for record in records:
        location = record.get("location")
        if isinstance(location, str) and location:
            return location
        if isinstance(location, dict):
            location_text = _join_nonempty(
                [location.get("city"), location.get("country")],
                separator=", ",
            )
            if location_text:
                return location_text

    location = organization.get("location", {})
    if isinstance(location, dict):
        return _join_nonempty(
            [location.get("city"), location.get("country")],
            separator=", ",
        )
    return ""


def _experience_group_period(records: list[dict[str, Any]]) -> str:
    start_dates = [record.get("start_date") for record in records if record.get("start_date")]
    end_dates = [record.get("end_date") for record in records if record.get("end_date")]
    if not start_dates and not end_dates:
        return ""
    start_date = min(start_dates) if start_dates else None
    end_date = None if any(not record.get("end_date") for record in records) else max(end_dates, default=None)
    return _date_span({"start_date": start_date, "end_date": end_date})


def _experience_group_months(records: list[dict[str, Any]]) -> int:
    return _merged_month_span(
        [
            interval
            for record in records
            if (interval := _record_month_interval(record)) is not None
        ]
    )


def _publication_block(model: CVModel, records: dict[str, Any]) -> dict[str, Any]:
    detail = model.section_detail("publications")
    if detail == "hidden":
        items: list[dict[str, Any]] = []
        journal_items: list[dict[str, Any]] = []
        conference_items: list[dict[str, Any]] = []
    else:
        items = [_prepare_publication(record, detail) for record in records["publications"]]
        journal_items = [
            _prepare_publication(record, detail) for record in records["journal_papers"]
        ]
        conference_items = [
            _prepare_publication(record, detail) for record in records["conference_papers"]
        ]
        items = _finalize_entries(model, items)
        journal_items = _finalize_entries(model, journal_items)
        conference_items = _finalize_entries(model, conference_items)
    return {
        "detail": detail,
        "records": records["publications"],
        "items": items,
        "groups": {
            "journal_papers": journal_items,
            "conference_papers": conference_items,
        },
        "counts": {
            "total": len(records["publications"]),
            "journal_papers": len(records["journal_papers"]),
            "conference_papers": len(records["conference_papers"]),
        },
    }


def _finalize_entries(model: CVModel, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    finalized_entries = []
    for entry in entries:
        finalized_entry = dict(entry)
        if not model.layout.get("include_urls", True):
            finalized_entry["url"] = ""
        if model.style == "sober":
            finalized_entry.pop("css_class", None)
        finalized_entries.append(finalized_entry)
    return finalized_entries


def _combined_detail(model: CVModel, *sections: str) -> str:
    return max(
        (model.section_detail(section) for section in sections),
        key=lambda detail: SECTION_DETAIL_RANKS[detail],
    )


def _prepare_degree(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if _detail_at_least(detail, "compact") and record.get("program"):
        details.append(_detail("Program", record["program"]))
    if _detail_at_least(detail, "standard") and record.get("grade"):
        details.append(_detail("Grade", record["grade"]))
    thesis = record.get("thesis") or {}
    if _detail_at_least(detail, "standard") and thesis.get("title"):
        details.append(_detail(str(thesis.get("type") or "Thesis"), thesis["title"]))
    return _entry(
        record,
        kind=str(record.get("level") or "Degree"),
        title=str(record.get("title") or ""),
        date=str(_date_span(record) or record.get("date_awarded") or ""),
        meta="",
        details=details,
        references=_references(
            _reference("Honors", record.get("related_honors", [])),
            _reference("Grants", _resolved(record, "grant_ids")),
        ),
        css_class="cv-entry-education",
    )


def _prepare_certification(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if record.get("duration_hours"):
        details.append(_detail("Duration", f"{_format_number(float(record['duration_hours']))} hours"))
    if _detail_at_least(detail, "standard") and record.get("notes"):
        details.append(_detail("Notes", record["notes"]))
    return _entry(
        record,
        kind="Certification",
        title=str(record.get("title") or ""),
        date=str(record.get("issue_date") or _date_span(record)),
        meta=_organization_names_text(record) or str(record.get("issuer") or ""),
        details=details,
        css_class="cv-entry-certification",
    )


def _prepare_position(record: dict[str, Any], detail: str) -> dict[str, Any]:
    meta_parts = []
    if record.get("department"):
        meta_parts.append(str(record["department"]))
    if record.get("location"):
        meta_parts.append(str(record["location"]))
    return _entry(
        record,
        kind=str(record.get("employment_type") or "Position"),
        title=str(record.get("title") or ""),
        date=_date_span(record),
        meta=_join_nonempty(meta_parts, separator=" · "),
        references=_references(_reference("Grants", record.get("related_grants", []))),
        tasks=list(record.get("tasks") or []) if _detail_at_least(detail, "full") else [],
        css_class="cv-entry-experience",
    )


def _prepare_stay(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if _detail_at_least(detail, "standard") and record.get("purpose"):
        details.append(_detail("Purpose", record["purpose"]))
    if _detail_at_least(detail, "full") and record.get("description"):
        details.append(_detail("Description", record["description"]))
    location = record.get("location") or {}
    location_text = _join_nonempty(
        [location.get("city"), location.get("country")],
        separator=", ",
    )
    return _entry(
        record,
        kind=str(record.get("type") or "Research stay"),
        title=str(record.get("title") or ""),
        date=_date_span(record),
        meta=location_text,
        details=details,
        references=_references(_reference("Grants", record.get("related_grants", []))),
        css_class="cv-entry-stay",
    )


def _prepare_honor(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if _detail_at_least(detail, "standard") and record.get("context"):
        details.append(_detail("Context", record["context"]))
    return _entry(
        record,
        kind="Honor",
        title=str(record.get("title") or ""),
        date=str(record.get("issue_date") or ""),
        meta=", ".join(record.get("awarding_entities") or []),
        details=details,
        references=_references(_reference("Related education", _resolved(record, "degree_ids"))),
        css_class="cv-entry-honor",
    )


def _prepare_grant(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if _detail_at_least(detail, "standard") and record.get("purpose"):
        details.append(_detail("Purpose", record["purpose"]))
    if _detail_at_least(detail, "compact") and _date_span(record):
        details.append(_detail("Period", _date_span(record)))
    return _entry(
        record,
        kind=str(record.get("awarding_entity_type") or "Grant"),
        title=str(record.get("name") or record.get("title") or ""),
        date=str(record.get("issue_date") or ""),
        meta=str(record.get("awarding_entity") or ""),
        details=details,
        references=_references(
            _reference("Related positions", _resolved(record, "position_ids")),
            _reference("Related stays", _resolved(record, "stay_ids")),
        ),
        css_class="cv-entry-grant",
    )


def _prepare_publication(record: dict[str, Any], detail: str) -> dict[str, Any]:
    publication_type = str(
        record.get("format")
        or record.get("publication_type")
        or record.get("type")
        or ""
    )
    kind = "Conference paper" if "conference" in publication_type.lower() else "Journal paper"
    details = []
    if record.get("venue"):
        venue_label = "Conference" if kind == "Conference paper" else "Journal"
        details.append(_detail(venue_label, record["venue"]))
    if _detail_at_least(detail, "standard") and record.get("publisher"):
        details.append(_detail("Publisher", record["publisher"]))
    if _detail_at_least(detail, "compact") and record.get("doi"):
        doi = str(record["doi"])
        details.append(_detail("DOI", doi, f"https://doi.org/{doi}"))
    return _entry(
        record,
        kind=kind,
        title=str(record.get("title") or ""),
        date=str(record.get("publication_date") or ""),
        meta=_author_line(record, detail),
        meta_label="Authors",
        url=str(record.get("url") or ""),
        details=details,
        references=_publication_references(record) if _detail_at_least(detail, "standard") else [],
        organizations=[],
        css_class="cv-entry-conference" if kind == "Conference paper" else "cv-entry-publication",
    )


def _prepare_research_project(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if _detail_at_least(detail, "standard") and record.get("funders"):
        details.append(_detail("Funders", ", ".join(record["funders"])))
    if _detail_at_least(detail, "standard") and record.get("principal_investigators"):
        details.append(_detail("Principal investigators", ", ".join(record["principal_investigators"])))
    title = _join_nonempty([record.get("acronym"), record.get("title")], separator=": ")
    return _entry(
        record,
        kind=str(record.get("participation") or "Research project"),
        title=title,
        date=_date_span(record),
        meta=str(record.get("code") or ""),
        details=details,
        css_class="cv-entry-project",
    )


def _prepare_software_project(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if _detail_at_least(detail, "standard") and record.get("description"):
        details.append(_detail("Description", record["description"]))
    if _detail_at_least(detail, "standard") and record.get("domains"):
        details.append(_detail("Domains", ", ".join(record["domains"])))
    return _entry(
        record,
        kind=str(record.get("type") or "Software project"),
        title=str(record.get("name") or ""),
        meta=str(record.get("full_name") or ""),
        url=_record_url(record),
        details=details,
        css_class="cv-entry-software",
    )


def _prepare_software_package(record: dict[str, Any], detail: str) -> dict[str, Any]:
    package_coordinates = _join_nonempty(
        [record.get("group_id"), record.get("artifact_id")],
        separator=":",
    )
    stats = record.get("package_stats") or {}
    return _entry(
        record,
        kind=str(record.get("ecosystem") or "Package"),
        title=str(record.get("name") or ""),
        meta="",
        url=str(stats.get("package_url") or stats.get("mvnrepository_url") or ""),
        details=_software_package_details(record, stats, detail, package_coordinates),
        css_class="cv-entry-package",
    )


def _prepare_university_class(record: dict[str, Any], _detail_level: str) -> dict[str, Any]:
    details = [_detail("Degree programme", record.get("degree") or "")]
    if record.get("department"):
        details.append(_detail("Department", record["department"]))
    if record.get("workload_hours"):
        details.append(_detail("Hours", _format_number(float(record["workload_hours"]))))
    return _entry(
        record,
        kind="University class",
        title=str(record.get("name") or ""),
        date=str(record.get("academic_year") or _date_span(record)),
        meta="",
        details=details,
        css_class="cv-entry-teaching",
    )


def _prepare_academic_supervision(record: dict[str, Any], _detail_level: str) -> dict[str, Any]:
    details = [
        _detail(label, value)
        for label, value in (
            ("Degree programme", record.get("degree")),
            ("Role", record.get("role")),
        )
        if value
    ]
    if record.get("workload_hours"):
        details.append(_detail("Hours", _format_number(float(record["workload_hours"]))))
    if record.get("repository_url"):
        details.append(_detail("Repository", "Repository", record["repository_url"]))
    return _entry(
        record,
        kind=str(record.get("type") or "Academic supervision"),
        title=str(record.get("title") or ""),
        date=str(record.get("date") or ""),
        url=str(record.get("url") or record.get("repository_url") or ""),
        details=details,
        css_class="cv-entry-supervision",
    )


def _prepare_teaching_innovation_project(
    record: dict[str, Any],
    _detail_level: str,
) -> dict[str, Any]:
    title = _join_nonempty([record.get("code"), record.get("title")], separator=": ")
    details = []
    if record.get("funding_entity"):
        details.append(_detail("Funding entity", record["funding_entity"]))
    return _entry(
        record,
        kind=str(record.get("participation") or "Teaching innovation project"),
        title=title,
        date=_date_span(record),
        meta="",
        details=details,
        css_class="cv-entry-project",
    )


def _prepare_scientific_article(record: dict[str, Any], _detail_level: str) -> dict[str, Any]:
    meta = _join_nonempty(
        [record.get("outlet"), f"Issue {record['issue']}" if record.get("issue") else ""],
        separator=" · ",
    )
    return _entry(
        record,
        kind="Article",
        title=str(record.get("title") or ""),
        date=str(record.get("date") or ""),
        meta=meta,
        url=str(record.get("url") or ""),
        references=_references(
            _reference("Publications", _resolved(record, "publication_ids")),
            _reference("Software packages", _resolved(record, "software_package_ids")),
        ),
        css_class="cv-entry-dissemination",
    )


def _prepare_presentation(record: dict[str, Any], _detail_level: str) -> dict[str, Any]:
    return _entry(
        record,
        kind=str(record.get("type") or "Presentation"),
        title=str(record.get("title") or ""),
        date=_date_span(record),
        meta=_join_nonempty([record.get("event"), record.get("location")], separator=" · "),
        references=_references(
            _reference("Publications", _resolved(record, "publication_ids")),
            _reference("Software packages", _resolved(record, "software_package_ids")),
        ),
        css_class="cv-entry-dissemination",
    )


def _prepare_press_item(record: dict[str, Any], _detail_level: str) -> dict[str, Any]:
    return _entry(
        record,
        kind=str(record.get("outlet") or "Press"),
        title=str(record.get("title") or ""),
        date=str(record.get("date") or ""),
        url=str(record.get("url") or ""),
        references=_references(_reference("Publications", _resolved(record, "publication_ids"))),
        css_class="cv-entry-press",
    )


def _prepare_social_media_item(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if record.get("accounts"):
        details.append(_detail("Accounts", ", ".join(_account_names(record["accounts"]))))
    if record.get("views"):
        details.append(_detail("Views", _format_number(float(record["views"]))))
    if _detail_at_least(detail, "standard") and record.get("description"):
        details.append(_detail("Description", record["description"]))
    return _entry(
        record,
        kind=str(record.get("platform") or "Social media"),
        title=str(record.get("platform") or ""),
        date=str(record.get("date") or ""),
        url=str(record.get("url") or ""),
        details=details,
        references=_references(_reference("Publications", _resolved(record, "publication_ids"))),
        css_class="cv-entry-social",
    )


def _prepare_tv_item(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if _detail_at_least(detail, "standard") and record.get("description"):
        details.append(_detail("Description", record["description"]))
    return _entry(
        record,
        kind=str(record.get("channel") or "TV media"),
        title=str(record.get("program") or ""),
        date=str(record.get("date") or ""),
        url=str(record.get("url") or ""),
        details=details,
        references=_references(_reference("Publications", _resolved(record, "publication_ids"))),
        css_class="cv-entry-tv",
    )


def _prepare_reviewing(record: dict[str, Any], _detail_level: str) -> dict[str, Any]:
    count = int(record.get("manuscripts_reviewed") or 0)
    suffix = "" if count == 1 else "s"
    return _entry(
        record,
        kind=str(record.get("publisher") or "Reviewing"),
        title=str(record.get("journal") or ""),
        date=str(record.get("last_updated") or ""),
        details=[_detail("Reviewed manuscripts", f"{count} manuscript{suffix}")],
        css_class="cv-entry-reviewing",
    )


def _entry(
    record: dict[str, Any],
    *,
    kind: str,
    title: str,
    date: str = "",
    meta: str = "",
    meta_label: str = "Additional information",
    url: str = "",
    details: list[Any] | None = None,
    references: list[dict[str, Any]] | None = None,
    tasks: list[str] | None = None,
    organizations: list[dict[str, Any]] | None = None,
    css_class: str = "cv-entry",
) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "record": record,
        "organizations": _resolved(record, "organization_ids") if organizations is None else organizations,
        "kind": kind,
        "title": title,
        "date": date,
        "meta": meta,
        "meta_label": meta_label,
        "url": url,
        "details": [detail for detail in details or [] if detail],
        "references": references or [],
        "tasks": tasks or [],
        "css_class": css_class,
    }


def _detail(label: str, value: Any, url: Any = "") -> dict[str, str]:
    value_text = str(value or "").strip()
    if not value_text:
        return {}
    return {
        "label": label,
        "value": value_text,
        "url": str(url or ""),
    }


def _software_package_details(
    record: dict[str, Any],
    stats: dict[str, Any],
    detail: str,
    package_coordinates: str,
) -> list[dict[str, str]]:
    if detail == "aggregate":
        return []

    details: list[dict[str, str]] = []
    ecosystem = str(record.get("ecosystem") or stats.get("ecosystem") or "")
    package_name = str(record.get("package_name") or "")

    if package_name:
        details.append(_detail("Package name", package_name, stats.get("package_url")))
    if package_coordinates:
        details.append(
            _detail(
                "Coordinate",
                package_coordinates,
                stats.get("mvnrepository_url") or stats.get("package_url"),
            )
        )

    if not _detail_at_least(detail, "standard"):
        return [item for item in details if item]

    if stats.get("summary"):
        details.append(_detail("Summary", stats["summary"]))
    if stats.get("latest_version"):
        details.append(_detail("Latest version", stats["latest_version"]))
    if stats.get("release_count") not in (None, ""):
        details.append(_detail("Releases", _format_number(float(stats["release_count"]))))
    if stats.get("license"):
        details.append(_detail("License", stats["license"]))

    if ecosystem.lower() == "pypi":
        if stats.get("total_downloads") not in (None, ""):
            details.append(
                _detail("Total downloads", _format_number(float(stats["total_downloads"])))
            )
        download_period = _join_nonempty(
            [stats.get("first_download_date"), stats.get("last_download_date")],
            separator=" - ",
        )
        if download_period:
            details.append(_detail("Download period", download_period))
        if stats.get("requires_python"):
            details.append(_detail("Requires Python", stats["requires_python"]))
        if stats.get("clickpy_url"):
            details.append(_detail("Downloads dashboard", "ClickPy", stats["clickpy_url"]))
    elif ecosystem.lower() == "maven":
        if stats.get("last_updated"):
            details.append(_detail("Last updated", stats["last_updated"]))
        if stats.get("java_release"):
            details.append(_detail("Java release", stats["java_release"]))
        if stats.get("dependency_count") not in (None, ""):
            details.append(_detail("Dependencies", _format_number(float(stats["dependency_count"]))))
        if stats.get("project_url"):
            details.append(_detail("Project URL", stats["project_url"], stats["project_url"]))
        if stats.get("mvnrepository_url"):
            details.append(_detail("Maven Repository", "MvnRepository", stats["mvnrepository_url"]))

    return [item for item in details if item]


def _software_summary(
    software_projects: list[dict[str, Any]],
    software_packages: list[dict[str, Any]],
) -> dict[str, Any]:
    domain_counts = Counter(
        domain
        for project in software_projects
        for domain in project.get("domains", [])
    )
    ecosystem_counts = Counter(
        str(package.get("ecosystem"))
        for package in software_packages
        if package.get("ecosystem")
    )
    return {
        "counts": {
            "software_projects": len(software_projects),
            "published_packages": len(software_packages),
            "research_domains": len(domain_counts),
        },
        "metrics": [
            _metric("Software projects", len(software_projects)),
            _metric("Published packages", len(software_packages)),
            _metric("Research domains", len(domain_counts)),
        ],
        "highlights": _summary_lines(
            ("Main domains", _counter_list(domain_counts, limit=3)),
            ("Package ecosystems", _counter_list(ecosystem_counts, limit=3)),
        ),
    }


def _teaching_summary(
    university_classes: list[dict[str, Any]],
    academic_supervision: list[dict[str, Any]],
    teaching_innovation_projects: list[dict[str, Any]],
) -> dict[str, Any]:
    total_hours = sum(float(course.get("workload_hours") or 0) for course in university_classes)
    academic_years = {str(course.get("academic_year")) for course in university_classes if course.get("academic_year")}
    degrees = {str(course.get("degree")) for course in university_classes if course.get("degree")}
    supervision_counts = Counter(
        str(supervision.get("type"))
        for supervision in academic_supervision
        if supervision.get("type")
    )
    innovation_titles = [
        _join_nonempty([project.get("code"), project.get("title")], separator=": ")
        for project in teaching_innovation_projects
        if project.get("code") or project.get("title")
    ]
    return {
        "counts": {
            "classroom_hours": _format_number(total_hours),
            "academic_years": len(academic_years),
            "courses": len(university_classes),
            "degree_programmes": len(degrees),
            "supervisions": len(academic_supervision),
            "teaching_innovation_projects": len(teaching_innovation_projects),
        },
        "metrics": [
            _metric("Classroom hours", _format_number(total_hours)),
            _metric("Academic years", len(academic_years)),
            _metric("Courses", len(university_classes)),
            _metric("Degree programmes", len(degrees)),
            _metric("Supervisions", len(academic_supervision)),
            _metric("Teaching innovation projects", len(teaching_innovation_projects)),
        ],
        "highlights": _summary_lines(
            ("Supervision", _counter_list(supervision_counts, limit=3)),
            ("Teaching innovation", "; ".join(innovation_titles[:2])),
        ),
    }


def _dissemination_summary(
    scientific_articles: list[dict[str, Any]],
    presentations: list[dict[str, Any]],
    press: list[dict[str, Any]],
    social_media: list[dict[str, Any]],
    tv_media: list[dict[str, Any]],
) -> dict[str, Any]:
    known_views = [
        int(item["views"])
        for item in social_media
        if item.get("views") not in (None, "")
    ]
    total_items = (
        len(scientific_articles)
        + len(presentations)
        + len(press)
        + len(social_media)
        + len(tv_media)
    )
    return {
        "counts": {
            "total_items": total_items,
            "scientific_articles": len(scientific_articles),
            "presentations": len(presentations),
            "press": len(press),
            "social_media": len(social_media),
            "tv_media": len(tv_media),
            "known_social_views": _format_number(sum(known_views)),
        },
        "metrics": [
            _metric("Dissemination items", total_items),
            _metric("Scientific articles", len(scientific_articles)),
            _metric("Presentations", len(presentations)),
            _metric("Press items", len(press)),
            _metric("Social media items", len(social_media)),
            _metric("TV media items", len(tv_media)),
            _metric("Known social views", _format_number(sum(known_views))),
        ],
        "highlights": _summary_lines(
            ("Highest known social media item", f"{_format_number(max(known_views))} views" if known_views else ""),
        ),
    }


def _reviewing_summary(reviewing: list[dict[str, Any]]) -> dict[str, Any]:
    total_reviews = sum(int(item.get("manuscripts_reviewed") or 0) for item in reviewing)
    top_journals = sorted(
        reviewing,
        key=lambda item: (-int(item.get("manuscripts_reviewed") or 0), str(item.get("journal") or "")),
    )
    return {
        "counts": {
            "reviewed_manuscripts": total_reviews,
            "journals": len(reviewing),
        },
        "metrics": [
            _metric("Reviewed manuscripts", total_reviews),
            _metric("Journals", len(reviewing)),
        ],
        "highlights": _summary_lines(
            (
                "Main journals",
                ", ".join(str(item.get("journal")) for item in top_journals[:3] if item.get("journal")),
            ),
        ),
    }


def _aggregate_highlights(*blocks: dict[str, Any]) -> list[str]:
    highlights: list[str] = []
    for block in blocks:
        summary = block.get("summary", {})
        highlights.extend(summary.get("highlights", []))
    return highlights


def _metric(label: str, value: int | str) -> dict[str, str]:
    return {"label": label, "value": str(value)}


def _summary_lines(*items: tuple[str, str]) -> list[str]:
    return [f"{label}: {value}" for label, value in items if value]


def _counter_list(counter: Counter[str], *, limit: int) -> str:
    items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return ", ".join(f"{label} ({value})" for label, value in items)


def _publication_references(record: dict[str, Any]) -> list[dict[str, Any]]:
    return _references(
        _reference("Organizations", _resolved(record, "organization_ids")),
        _reference("Software", _resolved(record, "software_project_ids")),
        _reference("Projects", _resolved(record, "research_project_ids")),
        _reference("Positions", _resolved(record, "position_ids")),
        _reference("Stays", _resolved(record, "stay_ids")),
        _reference("Grants", _resolved(record, "grant_ids")),
    )


def _reference(label: str, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not records:
        return None
    return {"label": label, "records": records}


def _references(*references: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [reference for reference in references if reference]


def _resolved(record: dict[str, Any], field: str) -> list[dict[str, Any]]:
    return list(record.get("resolved", {}).get(field, []))


def _organization_names_text(record: dict[str, Any]) -> str:
    return ", ".join(_record_display_name(item) for item in _resolved(record, "organization_ids"))


def _record_display_name(record: dict[str, Any]) -> str:
    for field in ("name", "title", "journal", "program", "event", "full_name"):
        value = record.get(field)
        if value:
            return str(value)
    return str(record.get("id", ""))


def _record_url(record: dict[str, Any]) -> str:
    if record.get("website"):
        return str(record["website"])
    if record.get("url"):
        return str(record["url"])
    urls = record.get("urls")
    if isinstance(urls, dict):
        for field in ("github", "website", "docs"):
            if urls.get(field):
                return str(urls[field])
    return ""


def _date_span(record: dict[str, Any]) -> str:
    start = record.get("start_date")
    end = record.get("end_date")
    if not start and not end:
        return ""
    return f"{start} - {end or 'Present'}" if start else str(end)


def _author_line(record: dict[str, Any], detail: str) -> str:
    authors = [str(author) for author in record.get("authors", [])]
    if not authors:
        return ""
    if _detail_at_least(detail, "compact") or len(authors) <= 3:
        return ", ".join(authors)
    return f"{authors[0]} et al."


def _account_names(values: list[Any]) -> list[str]:
    names = []
    for value in values:
        text = str(value)
        if text.startswith(("http://", "https://")):
            text = text.split("?", 1)[0].rstrip("/").split("/")[-1]
        if text not in names:
            names.append(text)
    return names


def _join_nonempty(values: list[Any], *, separator: str) -> str:
    return separator.join(str(value) for value in values if value)


def _detail_at_least(detail: str, threshold: str) -> bool:
    return SECTION_DETAIL_RANKS[detail] >= SECTION_DETAIL_RANKS[threshold]


def _publication_records_for_model(
    model: CVModel,
    journal_papers: list[dict[str, Any]],
    conference_papers: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    publications = sort_records_by_field(
        journal_papers + conference_papers,
        "publication_date",
        reverse=model.reverse_chronological,
    )
    selected_ids = {record.get("id") for record in publications}
    return (
        [record for record in journal_papers if record.get("id") in selected_ids],
        [record for record in conference_papers if record.get("id") in selected_ids],
        publications,
    )


def _render_options_for_model(model: CVModel) -> dict[str, bool]:
    return {
        "include_charts": bool(model.layout.get("include_charts", False)),
        "include_dashboard": bool(model.layout.get("include_dashboard", True)),
        "include_descriptions": _include_descriptions(model),
        "include_dissemination": model.includes_section("dissemination"),
        "include_internal_anchors": bool(model.layout.get("include_internal_anchors", True)),
        "include_profile_photo": bool(model.layout.get("include_profile_photo", False)),
        "include_profile_section": bool(model.layout.get("include_profile_section", False)),
        "include_profile_summary": model.section_detail_at_least("profile", "compact"),
        "include_research_focus": model.section_detail_at_least("profile", "standard"),
        "include_project_details": model.section_detail_at_least(
            "research_projects",
            "standard",
        ),
        "include_publication_relations": model.section_detail_at_least(
            "publications",
            "standard",
        ),
        "include_software_details": (
            model.section_detail_at_least("software_projects", "standard")
            or model.section_detail_at_least("software_packages", "standard")
        ),
        "include_tasks": model.section_detail_at_least("experience", "full"),
        "include_urls": bool(model.layout.get("include_urls", True)),
    }


def _include_descriptions(model: CVModel) -> bool:
    detail_sections = (
        "research_stays",
        "research_projects",
        "software_projects",
        "software_packages",
        "teaching",
        "dissemination",
    )
    return any(model.section_detail_at_least(section, "standard") for section in detail_sections)


def _limit_by_model(
    model: CVModel,
    records: list[dict[str, Any]],
    limit_name: str,
) -> list[dict[str, Any]]:
    return _limit_records(records, model.limits.get(limit_name))


def _limit_records(records: list[dict[str, Any]], limit: Any) -> list[dict[str, Any]]:
    if limit is None:
        return records

    parsed_limit = int(limit)
    if parsed_limit < 0:
        raise ValueError(f"CV item limit must be non-negative: {limit}")

    return records[:parsed_limit]


def _record_months(record: dict[str, Any]) -> int:
    return _month_span_to_present(record.get("start_date"), record.get("end_date"))


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


def _record_sort_month(record: dict[str, Any]) -> int:
    values = (
        record.get("end_date") or date.today().strftime("%Y-%m"),
        record.get("start_date"),
        record.get("issue_date"),
        record.get("date"),
    )
    for value in values:
        month = _month_number(value)
        if month is not None:
            return month
    return 0


def _merged_month_span(intervals: list[tuple[int, int]]) -> int:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
            continue
        merged[-1][1] = max(merged[-1][1], end)
    return sum(end - start + 1 for start, end in merged)


def _format_duration(months: int) -> str:
    years, remaining_months = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if remaining_months:
        parts.append(f"{remaining_months} month{'s' if remaining_months != 1 else ''}")
    return " and ".join(parts) if parts else "0 months"


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.1f}".rstrip("0").rstrip(".")


def generate_cv(
    model: str = "academic_rich",
    output_dir: Path | str = "build/cv",
    output_format: str = "pdf",
    page_limit: int | None = None,
    data_dir: Path | str = "data",
    model_dir: Path | str = "cv_models",
    template_dir: Path | str = "templates/cv",
    static_dir: Path | str = "assets/cv",
) -> CVOutput:
    output_format = output_format.lower()
    if output_format not in {"html", "pdf"}:
        raise ValueError(f"Unsupported CV format: {output_format}")

    cv_model = load_cv_model(model_path_for(model, model_dir))
    cv_model = _with_page_limit_override(cv_model, page_limit)
    resolver = PortfolioResolver(load_data(data_dir))

    output_base_dir = Path(output_dir)
    output_stem = _output_stem(cv_model, page_limit)
    html_path = output_base_dir / f"{output_stem}.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    asset_paths = _copy_static_assets(static_dir, html_path.parent / "assets")

    output_path = html_path
    page_count: int | None = None
    fit_status = "not_checked"
    if output_format == "pdf":
        output_path = output_base_dir / f"{output_stem}.pdf"
        cv_model, content, page_count, fit_status = _render_pdf_with_page_limit(
            base_model=cv_model,
            resolver=resolver,
            template_dir=template_dir,
            html_path=html_path,
            output_path=output_path,
        )
    else:
        content = _render_cv_html(cv_model, resolver, template_dir)
        html_path.write_text(content, encoding="utf-8")

    return CVOutput(
        model=cv_model,
        output_path=output_path,
        html_path=html_path,
        content=content,
        asset_paths=asset_paths,
        page_count=page_count,
        page_limit=cv_model.page_limit,
        fit_status=fit_status,
    )


def _with_page_limit_override(model: CVModel, page_limit: int | None) -> CVModel:
    if page_limit is None:
        return model

    parsed_limit = _parse_page_limit(page_limit)
    if model.style != "sober":
        raise ValueError("Dynamic page limits are only supported for sober CV models.")
    return replace(model, page_limit=parsed_limit)


def _output_stem(model: CVModel, page_limit_override: int | None) -> str:
    if page_limit_override is None:
        return model.name
    return f"{model.name}_{model.page_limit}p"


def _render_pdf_with_page_limit(
    *,
    base_model: CVModel,
    resolver: PortfolioResolver,
    template_dir: Path | str,
    html_path: Path,
    output_path: Path,
) -> tuple[CVModel, str, int, str]:
    attempted_results: list[tuple[CVModel, str, int]] = []

    for attempt_model in _compression_attempts(base_model):
        content = _render_cv_html(attempt_model, resolver, template_dir)
        html_path.write_text(content, encoding="utf-8")
        page_count = _export_pdf_from_html(html_path, output_path)
        attempted_results.append((attempt_model, content, page_count))

        if attempt_model.page_limit is None or page_count <= attempt_model.page_limit:
            fit_status = "not_limited" if attempt_model.page_limit is None else "fits"
            return attempt_model, content, page_count, fit_status

    final_model, final_content, final_page_count = attempted_results[-1]
    raise RuntimeError(_page_limit_failure_message(final_model, final_page_count, resolver))


def _render_cv_html(
    model: CVModel,
    resolver: PortfolioResolver,
    template_dir: Path | str,
) -> str:
    view = build_cv_view(model, resolver)
    return render_template(template_dir, model.template_name, view)


def _compression_attempts(model: CVModel) -> list[CVModel]:
    if model.page_limit is None:
        return [model]

    attempts = [
        model,
        _compressed_model(
            model,
            stage="compact",
            density="compact",
            font_scale="small",
            core_detail_cap="compact",
            include_charts=False,
        ),
        _compressed_model(
            model,
            stage="tight",
            density="micro",
            font_scale="xsmall",
            core_detail_cap="micro",
            include_charts=False,
            fit_stage="tight",
        ),
        _compressed_model(
            model,
            stage="minimal",
            density="micro",
            font_scale="xsmall",
            core_detail_cap="micro",
            include_charts=False,
            include_dashboard=False,
            include_urls=False,
            current_positions_detail="hidden",
            profile_detail="micro",
            fit_stage="minimal",
        ),
    ]
    return _unique_models(attempts)


def _compressed_model(
    model: CVModel,
    *,
    stage: str,
    density: str,
    font_scale: str,
    core_detail_cap: str,
    include_charts: bool,
    include_dashboard: bool | None = None,
    include_urls: bool | None = None,
    current_positions_detail: str | None = None,
    profile_detail: str | None = None,
    fit_stage: str | None = None,
) -> CVModel:
    sections = {
        section: _capped_detail(detail, core_detail_cap)
        for section, detail in model.sections.items()
    }
    for section in AGGREGABLE_SECTIONS:
        if sections.get(section) != "hidden":
            sections[section] = "aggregate"

    if current_positions_detail is not None:
        sections["current_positions"] = current_positions_detail
    if profile_detail is not None:
        sections["profile"] = profile_detail

    layout = {
        **model.layout,
        "density": density,
        "font_scale": font_scale,
        "include_charts": include_charts,
        "compression_stage": stage,
    }
    if fit_stage is not None:
        layout["fit_stage"] = fit_stage
    else:
        layout.pop("fit_stage", None)
    if include_dashboard is not None:
        layout["include_dashboard"] = include_dashboard
    if include_urls is not None:
        layout["include_urls"] = include_urls

    return replace(model, sections=sections, layout=layout)


def _capped_detail(detail: str, cap: str) -> str:
    if detail == "hidden":
        return detail
    return detail if SECTION_DETAIL_RANKS[detail] <= SECTION_DETAIL_RANKS[cap] else cap


def _unique_models(models: list[CVModel]) -> list[CVModel]:
    seen_signatures = set()
    unique_models = []
    for model in models:
        signature = (
            tuple(sorted(model.sections.items())),
            tuple(sorted(model.layout.items())),
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        unique_models.append(model)
    return unique_models


def _page_limit_failure_message(
    model: CVModel,
    page_count: int,
    resolver: PortfolioResolver,
) -> str:
    contributors = _page_limit_contributors(model, resolver)
    lines = [
        f"{model.name} cannot fit all required core records in {model.page_limit} pages.",
        f"Minimum compact render requires {page_count} pages.",
        "Largest contributors:",
    ]
    lines.extend(f"- {label}: {count} items" for label, count in contributors)
    return "\n".join(lines)


def _page_limit_contributors(
    model: CVModel,
    resolver: PortfolioResolver,
) -> list[tuple[str, int]]:
    del model
    counts = [
        (
            "publications",
            _resolved_count(resolver, "research/publications.yaml", "journal_papers")
            + _resolved_count(resolver, "research/publications.yaml", "conference_papers"),
        ),
        ("experience", _resolved_count(resolver, "career/experience.yaml", "positions")),
        (
            "research_projects",
            _resolved_count(resolver, "research/research_projects.yaml", "funded_projects"),
        ),
        ("degrees", _resolved_count(resolver, "career/degrees.yaml", "degrees")),
        ("honors", _resolved_count(resolver, "career/honors.yaml", "honors")),
        ("grants", _resolved_count(resolver, "career/grants.yaml", "grants")),
        ("research_stays", _resolved_count(resolver, "career/research_stays.yaml", "stays")),
    ]
    return sorted(counts, key=lambda item: (-item[1], item[0]))[:5]


def _resolved_count(resolver: PortfolioResolver, file_path: str, group: str) -> int:
    return len(resolved_records(resolver, file_path, group, reverse=False))


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


def _export_pdf_from_html(html_path: Path, output_path: Path) -> int:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "PDF generation requires Playwright. Install project dependencies and run "
            "`playwright install chromium`."
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(html_path.resolve().as_uri(), wait_until="load")
                page.emulate_media(media="print")
                page.pdf(
                    path=str(output_path),
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                )
            finally:
                browser.close()
        return _count_pdf_pages(output_path)
    except PlaywrightError as exc:
        message = str(exc)
        if "Executable doesn't exist" in message or "playwright install" in message.lower():
            raise RuntimeError(
                "Chromium is required for PDF generation. Run "
                "`playwright install chromium` and retry."
            ) from exc
        raise


def _count_pdf_pages(pdf_path: Path) -> int:
    return len(PDF_PAGE_PATTERN.findall(pdf_path.read_bytes()))
