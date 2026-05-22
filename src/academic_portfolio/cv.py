from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field as dataclass_field, fields, replace
from datetime import date
import json
from pathlib import Path
import re
from shutil import copy2
from typing import Any
import tomllib

from academic_portfolio.i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    Translator,
    format_date_range,
    format_duration,
    format_number,
    load_translator,
    resolve_localized_values,
)
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
FEATURED_RECORD_COLLECTIONS = {
    "certifications",
    "software_projects",
    "software_packages",
    "reviewing",
    "university_classes",
    "academic_supervision",
    "teaching_innovation_projects",
    "scientific_articles",
    "presentations",
    "press",
    "social_media",
    "tv_media",
}
TASK_FILTER_SECTIONS = {"experience"}
SOBER_DISPLAY_SECTIONS = (
    "profile",
    "degrees",
    "experience",
    "research_stays",
    "publications",
    "research_projects",
    "honors",
    "grants",
    "certifications",
    "teaching",
    "software",
    "dissemination",
    "reviewing",
)
SOBER_DISPLAY_SECTION_TO_CV_SECTIONS = {
    "profile": {"profile"},
    "degrees": {"degrees"},
    "experience": {"experience"},
    "research_stays": {"research_stays"},
    "publications": {"publications"},
    "research_projects": {"research_projects"},
    "honors": {"honors"},
    "grants": {"grants"},
    "certifications": {"certifications"},
    "teaching": {"teaching"},
    "software": {"software_projects", "software_packages"},
    "dissemination": {"dissemination"},
    "reviewing": {"reviewing"},
}
PDF_PAGE_PATTERN = re.compile(rb"/Type\s*/Page\b")
_ACTIVE_TRANSLATOR: ContextVar[Translator | None] = ContextVar(
    "academic_portfolio_cv_translator",
    default=None,
)


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
    output_stem: str | None = None
    summary_override: str | None = None
    section_order: list[str] = dataclass_field(default_factory=list)
    section_titles: dict[str, str] = dataclass_field(default_factory=dict)
    extra_sections: list[dict[str, Any]] = dataclass_field(default_factory=list)
    fit_detail_floors: dict[str, str] = dataclass_field(default_factory=dict)
    featured_ids: dict[str, list[str]] = dataclass_field(default_factory=dict)
    task_filters: dict[str, dict[str, Any]] = dataclass_field(default_factory=dict)

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
class ApplicationOverlay:
    path: Path
    base_model: str
    name: str | None = None
    title: str | None = None
    language: str | None = None
    output_stem: str | None = None
    page_limit: int | None = None
    summary_override: str | None = None
    sections: dict[str, str] = dataclass_field(default_factory=dict)
    layout: dict[str, Any] = dataclass_field(default_factory=dict)
    limits: dict[str, Any] = dataclass_field(default_factory=dict)
    section_order: list[str] = dataclass_field(default_factory=list)
    section_titles: dict[str, str] = dataclass_field(default_factory=dict)
    extra_sections: list[dict[str, Any]] = dataclass_field(default_factory=list)
    fit_detail_floors: dict[str, str] = dataclass_field(default_factory=dict)
    featured_ids: dict[str, list[str]] = dataclass_field(default_factory=dict)
    task_filters: dict[str, dict[str, Any]] = dataclass_field(default_factory=dict)


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


def load_application_overlay(overlay_path: Path | str) -> ApplicationOverlay:
    path = Path(overlay_path)
    with path.open("rb") as handle:
        raw_overlay = tomllib.load(handle)

    _validate_overlay_shape(path, raw_overlay)

    page_limit = (
        _parse_page_limit(raw_overlay.get("page_limit"))
        if raw_overlay.get("page_limit") is not None
        else None
    )
    sections = {
        str(section): str(detail)
        for section, detail in dict(raw_overlay.get("sections", {})).items()
    }
    layout = dict(raw_overlay.get("layout", {}))
    limits = dict(raw_overlay.get("limits", {}))
    section_order = [str(section) for section in raw_overlay.get("section_order", [])]
    section_titles = {
        str(section): str(title)
        for section, title in dict(raw_overlay.get("section_titles", {})).items()
    }
    extra_sections = _normalized_extra_sections(path, raw_overlay.get("extra_sections", []))
    fit_detail_floors = {
        str(section): str(detail)
        for section, detail in dict(raw_overlay.get("fit_detail_floors", {})).items()
    }
    featured_ids = {
        str(collection): _string_list(ids)
        for collection, ids in dict(raw_overlay.get("featured_ids", {})).items()
    }
    task_filters = _normalized_task_filters(path, raw_overlay.get("task_filters", {}))

    _validate_overlay_values(
        path=path,
        sections=sections,
        layout=layout,
        limits=limits,
        section_order=section_order,
        section_titles=section_titles,
        extra_sections=extra_sections,
        fit_detail_floors=fit_detail_floors,
        featured_ids=featured_ids,
        task_filters=task_filters,
    )

    return ApplicationOverlay(
        path=path,
        base_model=str(raw_overlay["base_model"]),
        name=str(raw_overlay["name"]) if raw_overlay.get("name") else None,
        title=str(raw_overlay["title"]) if raw_overlay.get("title") else None,
        language=str(raw_overlay["language"]) if raw_overlay.get("language") else None,
        output_stem=str(raw_overlay["output_stem"]) if raw_overlay.get("output_stem") else None,
        page_limit=page_limit,
        summary_override=(
            str(raw_overlay["summary_override"]) if raw_overlay.get("summary_override") else None
        ),
        sections=sections,
        layout=layout,
        limits=limits,
        section_order=section_order,
        section_titles=section_titles,
        extra_sections=extra_sections,
        fit_detail_floors=fit_detail_floors,
        featured_ids=featured_ids,
        task_filters=task_filters,
    )


def load_cv_model_with_application(
    overlay_path: Path | str,
    model_dir: Path | str = "cv_models",
) -> CVModel:
    overlay = load_application_overlay(overlay_path)
    base_model = load_cv_model(model_path_for(overlay.base_model, model_dir))
    if base_model.style != "sober":
        raise ValueError("Application overlays are currently supported only for sober CV models.")

    merged_sections = {**base_model.sections, **overlay.sections}
    merged_layout = {**base_model.layout, **overlay.layout}
    merged_limits = {**base_model.limits, **overlay.limits}
    merged_model = replace(
        base_model,
        name=overlay.name or base_model.name,
        title=overlay.title or base_model.title,
        language=overlay.language or base_model.language,
        page_limit=overlay.page_limit if overlay.page_limit is not None else base_model.page_limit,
        sections=merged_sections,
        layout=merged_layout,
        limits=merged_limits,
        output_stem=overlay.output_stem,
        summary_override=overlay.summary_override,
        section_order=overlay.section_order,
        section_titles=overlay.section_titles,
        extra_sections=overlay.extra_sections,
        fit_detail_floors=overlay.fit_detail_floors,
        featured_ids=overlay.featured_ids,
        task_filters=overlay.task_filters,
    )

    _validate_model_values(
        path=overlay.path,
        style=merged_model.style,
        page_limit=merged_model.page_limit,
        sections=merged_model.sections,
        layout=merged_model.layout,
        limits=merged_model.limits,
    )
    _validate_sober_section_order(overlay.path, merged_model)
    return merged_model


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


def _validate_overlay_shape(path: Path, raw_overlay: dict[str, Any]) -> None:
    allowed_fields = {
        "base_model",
        "name",
        "title",
        "language",
        "output_stem",
        "page_limit",
        "summary_override",
        "section_order",
        "section_titles",
        "sections",
        "layout",
        "limits",
        "extra_sections",
        "fit_detail_floors",
        "featured_ids",
        "task_filters",
    }
    unknown_fields = sorted(set(raw_overlay) - allowed_fields)
    if unknown_fields:
        raise ValueError(f"{path} defines unknown application overlay fields: {unknown_fields}")

    if "base_model" not in raw_overlay:
        raise ValueError(f"{path} is missing required application overlay field: base_model")

    for table_name in (
        "sections",
        "layout",
        "limits",
        "section_titles",
        "fit_detail_floors",
        "featured_ids",
        "task_filters",
    ):
        if table_name in raw_overlay and not isinstance(raw_overlay[table_name], dict):
            raise ValueError(f"{path} must define [{table_name}] as a TOML table.")

    if "section_order" in raw_overlay and not isinstance(raw_overlay["section_order"], list):
        raise ValueError(f"{path} must define section_order as a TOML array.")

    if "extra_sections" in raw_overlay and not isinstance(raw_overlay["extra_sections"], list):
        raise ValueError(f"{path} must define [[extra_sections]] as an array of tables.")


def _normalized_extra_sections(path: Path, raw_sections: Any) -> list[dict[str, Any]]:
    extra_sections = []
    for index, raw_section in enumerate(raw_sections):
        if not isinstance(raw_section, dict):
            raise ValueError(f"{path} extra_sections[{index}] must be a TOML table.")
        section_id = str(raw_section.get("id") or "").strip()
        if not section_id:
            raise ValueError(f"{path} extra_sections[{index}] is missing id.")
        title = str(raw_section.get("title") or "").strip()
        placement = str(raw_section.get("placement") or "after_summary").strip()
        style = str(raw_section.get("style") or "bullets").strip()
        paragraphs = _string_list(raw_section.get("paragraphs", []))
        items = _string_list(raw_section.get("items", []))
        extra_sections.append(
            {
                "id": section_id,
                "title": title,
                "placement": placement,
                "style": style,
                "paragraphs": paragraphs,
                "items": items,
            }
        )
    return extra_sections


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"Expected a TOML array of strings, got {type(value).__name__}.")
    return [str(item) for item in value if str(item).strip()]


def _normalized_task_filters(path: Path, raw_filters: Any) -> dict[str, dict[str, Any]]:
    if raw_filters is None:
        return {}
    if not isinstance(raw_filters, dict):
        raise ValueError(f"{path} must define [task_filters] as a TOML table.")

    filters: dict[str, dict[str, Any]] = {}
    for section, raw_filter in raw_filters.items():
        section_name = str(section)
        if section_name not in TASK_FILTER_SECTIONS:
            raise ValueError(f"{path} defines unsupported task filter section: {section_name}")
        if not isinstance(raw_filter, dict):
            raise ValueError(f"{path} task_filters.{section_name} must be a TOML table.")

        max_tasks = raw_filter.get("max_tasks_per_record")
        if max_tasks is not None:
            try:
                max_tasks = int(max_tasks)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{path} task_filters.{section_name}.max_tasks_per_record must be an integer."
                ) from exc
            if max_tasks < 0:
                raise ValueError(
                    f"{path} task_filters.{section_name}.max_tasks_per_record must be non-negative."
                )

        filters[section_name] = {
            "max_tasks_per_record": max_tasks,
            "include_keywords": _string_list(raw_filter.get("include_keywords", [])),
            "exclude_keywords": _string_list(raw_filter.get("exclude_keywords", [])),
        }
    return filters


def _validate_overlay_values(
    *,
    path: Path,
    sections: dict[str, str],
    layout: dict[str, Any],
    limits: dict[str, Any],
    section_order: list[str],
    section_titles: dict[str, str],
    extra_sections: list[dict[str, Any]],
    fit_detail_floors: dict[str, str],
    featured_ids: dict[str, list[str]],
    task_filters: dict[str, dict[str, Any]],
) -> None:
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

    hidden_nuclear_sections = sorted(
        section
        for section in NUCLEAR_SECTIONS
        if sections.get(section) == "hidden"
    )
    if hidden_nuclear_sections:
        raise ValueError(f"{path} cannot hide nuclear CV sections: {hidden_nuclear_sections}")

    _validate_model_values(
        path=path,
        style="sober",
        page_limit=None,
        sections={section: "full" for section in NUCLEAR_SECTIONS} | sections,
        layout=layout,
        limits=limits,
    )

    extra_ids = {section["id"] for section in extra_sections}
    duplicate_extra_ids = sorted(
        section_id
        for section_id in extra_ids
        if [section["id"] for section in extra_sections].count(section_id) > 1
    )
    if duplicate_extra_ids:
        raise ValueError(f"{path} defines duplicate extra section ids: {duplicate_extra_ids}")

    reserved_extra_ids = sorted(extra_ids & set(SOBER_DISPLAY_SECTIONS))
    if reserved_extra_ids:
        raise ValueError(f"{path} extra section ids cannot reuse built-in sections: {reserved_extra_ids}")

    allowed_order_ids = set(SOBER_DISPLAY_SECTIONS) | extra_ids
    unknown_order_ids = sorted(set(section_order) - allowed_order_ids)
    if unknown_order_ids:
        raise ValueError(f"{path} section_order contains unknown sections: {unknown_order_ids}")

    unknown_title_ids = sorted(set(section_titles) - allowed_order_ids)
    if unknown_title_ids:
        raise ValueError(f"{path} section_titles contains unknown sections: {unknown_title_ids}")

    invalid_extra_styles = sorted(
        {section["style"] for section in extra_sections} - {"bullets", "paragraphs"}
    )
    if invalid_extra_styles:
        raise ValueError(f"{path} defines unsupported extra section styles: {invalid_extra_styles}")

    invalid_placements = sorted(
        {section["placement"] for section in extra_sections} - {"after_summary"}
    )
    if invalid_placements:
        raise ValueError(f"{path} defines unsupported extra section placements: {invalid_placements}")

    unknown_floor_sections = sorted(set(fit_detail_floors) - CV_SECTIONS)
    if unknown_floor_sections:
        raise ValueError(f"{path} defines unknown fit detail floor sections: {unknown_floor_sections}")

    invalid_floor_details = {
        section: detail
        for section, detail in fit_detail_floors.items()
        if detail not in SECTION_DETAIL_LEVELS or detail in {"hidden", "aggregate"}
    }
    if invalid_floor_details:
        raise ValueError(f"{path} defines invalid fit detail floors: {invalid_floor_details}")

    unknown_featured_collections = sorted(set(featured_ids) - FEATURED_RECORD_COLLECTIONS)
    if unknown_featured_collections:
        raise ValueError(
            f"{path} defines unsupported featured_id collections: {unknown_featured_collections}"
        )

    unknown_task_filter_sections = sorted(set(task_filters) - TASK_FILTER_SECTIONS)
    if unknown_task_filter_sections:
        raise ValueError(
            f"{path} defines unsupported task filter sections: {unknown_task_filter_sections}"
        )


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


def _validate_sober_section_order(path: Path, model: CVModel) -> None:
    if model.style != "sober" or not model.section_order:
        return

    covered_cv_sections = set()
    for display_section in model.section_order:
        covered_cv_sections.update(
            SOBER_DISPLAY_SECTION_TO_CV_SECTIONS.get(display_section, set())
        )

    omitted_nuclear_sections = sorted(
        section
        for section in NUCLEAR_SECTIONS
        if model.includes_section(section) and section not in covered_cv_sections
    )
    if omitted_nuclear_sections:
        raise ValueError(
            f"{path} section_order cannot omit active nuclear CV sections: "
            f"{omitted_nuclear_sections}"
        )


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


def build_cv_view(
    model: CVModel,
    resolver: PortfolioResolver,
    translator: Translator | None = None,
) -> dict[str, Any]:
    active_translator = translator or load_translator(model.language)
    with _using_translator(active_translator):
        view = _build_cv_view(model, resolver)
    return resolve_localized_values(view, active_translator)


def _build_cv_view(model: CVModel, resolver: PortfolioResolver) -> dict[str, Any]:
    source_records = _load_cv_records(model, resolver)
    source_records = _localized_record_set(source_records, _current_translator())
    records = _records_for_model(model, source_records)
    record_mapping = _record_mapping(records)
    site_view = _cv_site_view(resolver)
    core = _core_view(model, record_mapping)
    aggregates = _aggregate_view(model, record_mapping)

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
        view["sober_view"] = _sober_cv_view(model, core, aggregates)

    return view


def _localized_record_set(records: CVRecordSet, translator: Translator) -> CVRecordSet:
    return CVRecordSet(
        **{
            field.name: resolve_localized_values(getattr(records, field.name), translator)
            for field in fields(CVRecordSet)
        }
    )


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

    record_set = CVRecordSet(
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
    _validate_featured_ids_exist(model, record_set)
    return record_set


def _validate_featured_ids_exist(model: CVModel, records: CVRecordSet) -> None:
    for collection, featured_ids in model.featured_ids.items():
        available_ids = {str(record.get("id")) for record in getattr(records, collection)}
        unknown_ids = [record_id for record_id in featured_ids if record_id not in available_ids]
        if unknown_ids:
            raise ValueError(
                f"Unknown featured_ids for {collection}: {', '.join(unknown_ids)}"
            )


def _records_for_model(model: CVModel, records: CVRecordSet) -> CVRecordSet:
    return replace(
        records,
        certifications=_featured_limit_by_model(
            model,
            records.certifications,
            "certifications",
            "max_certifications",
        ),
        software_projects=_limit_by_model(
            model,
            _featured_records_first(model, records.software_projects, "software_projects"),
            "max_software_projects",
        ),
        software_packages=_limit_by_model(
            model,
            _featured_records_first(model, records.software_packages, "software_packages"),
            "max_software_packages",
        ),
        reviewing=_featured_limit_by_model(model, records.reviewing, "reviewing", "max_reviewing"),
        university_classes=_featured_limit_by_model(
            model,
            records.university_classes,
            "university_classes",
            "max_university_classes",
        ),
        academic_supervision=_featured_limit_by_model(
            model,
            records.academic_supervision,
            "academic_supervision",
            "max_academic_supervision",
        ),
        teaching_innovation_projects=_featured_limit_by_model(
            model,
            records.teaching_innovation_projects,
            "teaching_innovation_projects",
            "max_teaching_innovation_projects",
        ),
        scientific_articles=_featured_limit_by_model(
            model,
            records.scientific_articles,
            "scientific_articles",
            "max_scientific_articles",
        ),
        presentations=_featured_limit_by_model(
            model,
            records.presentations,
            "presentations",
            "max_presentations",
        ),
        press=_featured_limit_by_model(model, records.press, "press", "max_press"),
        social_media=_featured_limit_by_model(
            model,
            records.social_media,
            "social_media",
            "max_social_media",
        ),
        tv_media=_featured_limit_by_model(model, records.tv_media, "tv_media", "max_tv_media"),
    )


def _featured_limit_by_model(
    model: CVModel,
    records: list[dict[str, Any]],
    collection: str,
    limit_name: str,
) -> list[dict[str, Any]]:
    return _limit_by_model(model, _featured_records_first(model, records, collection), limit_name)


def _featured_records_first(
    model: CVModel,
    records: list[dict[str, Any]],
    collection: str,
) -> list[dict[str, Any]]:
    featured_ids = model.featured_ids.get(collection, [])
    if not featured_ids:
        return records

    by_id = {str(record.get("id")): record for record in records}
    featured_records = [by_id[record_id] for record_id in featured_ids if record_id in by_id]
    remaining_records = [
        record
        for record in records
        if str(record.get("id")) not in set(featured_ids)
    ]
    return featured_records + remaining_records


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


@contextmanager
def _using_translator(translator: Translator) -> Any:
    token = _ACTIVE_TRANSLATOR.set(translator)
    try:
        yield
    finally:
        _ACTIVE_TRANSLATOR.reset(token)


def _current_translator() -> Translator:
    return _ACTIVE_TRANSLATOR.get() or load_translator()


def _t(key: str, **values: Any) -> str:
    return _current_translator().t(key, **values)


def _cv_key(namespace: str, key: str) -> str:
    return f"cv.{namespace}.{key}"


def _cv_text(namespace: str, key: str, **values: Any) -> str:
    return _t(_cv_key(namespace, key), **values)


def _localized_participation(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = f" {text.lower().replace('/', ' ').replace('-', ' ').replace('.', ' ')} "
    if (
        "principal investigator" in normalized
        or "investigador principal" in normalized
        or " co pi " in normalized
        or " co ip " in normalized
        or " pi " in normalized
        or " ip " in normalized
    ):
        return _cv_text("labels", "pi_copi")
    if "research team" in normalized or "equipo de investigación" in normalized:
        return _cv_text("labels", "research_team_member")
    if "working team" in normalized or "equipo de trabajo" in normalized:
        return _cv_text("labels", "working_team_member")
    return text


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


def _sober_cv_view(
    model: CVModel,
    core: dict[str, Any],
    aggregates: dict[str, Any],
) -> dict[str, Any]:
    return {
        "section_order": _sober_section_order(model),
        "section_titles": model.section_titles,
        "extra_sections": model.extra_sections,
        "extra_sections_by_id": {
            section["id"]: section for section in model.extra_sections
        },
        "featured_ids": model.featured_ids,
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


def _sober_section_order(model: CVModel) -> list[str]:
    if model.section_order:
        return list(model.section_order)

    section_order = list(SOBER_DISPLAY_SECTIONS)
    for extra_section in reversed(model.extra_sections):
        if extra_section.get("placement") != "after_summary":
            continue
        section_order.insert(1, str(extra_section["id"]))
    return section_order


def _cv_site_view(resolver: PortfolioResolver) -> dict[str, Any]:
    from academic_portfolio.site.build import build_site_view

    return build_site_view(
        resolver,
        github_stats_by_url=_cached_github_stats(),
        package_stats_by_id=_cached_package_stats(),
        translator=_current_translator(),
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
    if model.summary_override:
        levels[active_level] = _summary_level(
            level=active_level,
            paragraphs=_paragraphs_from_text(model.summary_override),
        )
    return {
        "active_level": active_level,
        "active": levels[active_level],
        "levels": levels,
        "summary_full": levels["full"],
        "summary_compact": levels["compact"],
        "summary_micro": levels["micro"],
    }


def _paragraphs_from_text(value: str) -> list[str]:
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n", value) if paragraph.strip()]


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
                "academic_background",
                education.get("degrees_text"),
            ),
            _sentence(
                "professional_experience",
                experience.get("by_institution_text"),
            ),
            _stay_sentence(internationalization),
        ),
        _summary_paragraph(
            _research_output_sentence(research),
            _collaboration_sentence(internationalization),
            _sentence(
                "funded_research_roles",
                research.get("project_roles_text"),
            ),
            _count_sentence(
                "reviewed_manuscripts",
                metrics.get("reviewed_manuscripts"),
                "manuscript",
                "for_scientific_journals",
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
                "teaching_innovation_includes",
                teaching.get("teaching_innovation_projects_phrase"),
            ),
            _sentence(
                "academic_supervision_includes",
                teaching.get("supervision_text"),
            ),
        ),
        _summary_paragraph(
            _sentence(
                "dissemination_activity",
                dissemination.get("activity_text"),
            ),
            _count_sentence(
                "press_coverage",
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
            _sentence("academic_background", education.get("degrees_text")),
            _sentence("professional_experience", experience.get("by_institution_text")),
            _stay_sentence(internationalization),
        ),
        _summary_paragraph(
            _research_output_sentence(research),
            _collaboration_sentence(internationalization),
            _sentence("research_project_roles", research.get("project_roles_text")),
            _software_output_sentence(metrics),
            _downloads_sentence(metrics, software),
        ),
        _summary_paragraph(
            _teaching_sentence(teaching),
            _sentence("dissemination_covers", dissemination.get("activity_text")),
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
    generated_intro = _cv_text("summary", "intro_generated")
    if profile_summary:
        return f"{profile_summary} {generated_intro}"
    return generated_intro


def _summary_paragraph(*sentences: str) -> str:
    return " ".join(sentence for sentence in sentences if sentence)


def _sentence(key: str, value: Any) -> str:
    value_text = str(value or "")
    if not value_text:
        return ""
    return _cv_text("summary", key, value=value_text)


def _count_sentence(
    key: str,
    count: Any,
    unit_key: str,
    suffix_key: str = "",
) -> str:
    try:
        parsed_count = int(count)
    except (TypeError, ValueError):
        return ""
    count_text = _current_translator().unit(
        unit_key,
        parsed_count,
        display_count=_format_number(parsed_count),
    )
    suffix = _cv_text("summary", suffix_key) if suffix_key else ""
    return _cv_text("summary", key, count=count_text, suffix=suffix)


def _research_output_sentence(research: dict[str, Any]) -> str:
    journal_phrase = research.get("journal_papers_phrase")
    conference_phrase = research.get("conference_papers_phrase")
    if journal_phrase and conference_phrase:
        return _cv_text(
            "summary",
            "research_output_pair",
            journal=journal_phrase,
            conference=conference_phrase,
        )
    return _sentence("research_output_single", journal_phrase or conference_phrase)


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
    return _cv_text("summary", "publication_collaboration", value=collaboration_text)


def _stay_sentence(internationalization: dict[str, Any]) -> str:
    stays_text = str(internationalization.get("stays_text") or "")
    total_months = int(internationalization.get("total_stay_months") or 0)
    if not stays_text and not total_months:
        return ""
    if stays_text and total_months:
        return _cv_text(
            "summary",
            "research_stays_with_total",
            stays=stays_text,
            total=_current_translator().unit(
                "month",
                total_months,
                display_count=_format_number(total_months),
            ),
        )
    return _sentence("research_stays_single", stays_text)


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
    return _cv_text("summary", "software_output", value=output_text)


def _github_sentence(software: dict[str, Any]) -> str:
    repositories = int(software.get("repositories_with_stats") or 0)
    if not repositories:
        return ""
    return _cv_text(
        "summary",
        "github_activity",
        repositories=_current_translator().unit(
            "repository",
            repositories,
            display_count=_format_number(repositories),
        ),
        stars=_current_translator().unit(
            "star",
            int(software.get("total_stars") or 0),
            display_count=_format_number(int(software.get("total_stars") or 0)),
        ),
        forks=_current_translator().unit(
            "fork",
            int(software.get("total_forks") or 0),
            display_count=_format_number(int(software.get("total_forks") or 0)),
        ),
    )


def _downloads_sentence(metrics: dict[str, Any], software: dict[str, Any]) -> str:
    downloads = int(metrics.get("package_downloads") or 0)
    if not downloads:
        return ""
    return _cv_text(
        "summary",
        "package_downloads",
        downloads=_current_translator().unit(
            "download",
            downloads,
            display_count=software.get("package_downloads_label") or _format_number(downloads),
        ),
    )


def _teaching_sentence(teaching: dict[str, Any]) -> str:
    institution_years = str(teaching.get("institution_years_text") or "")
    total_hours = str(teaching.get("total_hours_label") or "")
    academic_years = int(teaching.get("academic_years") or 0)
    courses = int(teaching.get("courses") or 0)
    degree_programs = int(teaching.get("degree_programs") or 0)
    if not total_hours and not courses:
        return ""
    context = _cv_text("summary", "teaching_context", value=institution_years) if institution_years else ""
    parts = [
        _cv_text("summary", "classroom_hours_phrase", hours=total_hours) if total_hours else "",
        _count_phrase("academic year", academic_years) if academic_years else "",
        _count_phrase("course", courses) if courses else "",
        _count_phrase("degree programme", degree_programs) if degree_programs else "",
    ]
    return _cv_text("summary", "teaching_activity", context=context, value=_join_summary_phrases(parts))


def _teaching_micro_sentence(teaching: dict[str, Any]) -> str:
    total_hours = str(teaching.get("total_hours_label") or "")
    courses = int(teaching.get("courses") or 0)
    if not total_hours and not courses:
        return ""
    parts = [
        _cv_text("summary", "classroom_hours_phrase", hours=total_hours) if total_hours else "",
        _count_phrase("course", courses) if courses else "",
    ]
    return _cv_text("summary", "teaching_micro", value=_join_summary_phrases(parts))


def _social_views_sentence(metrics: dict[str, Any], dissemination: dict[str, Any]) -> str:
    known_views = int(metrics.get("known_social_views") or 0)
    if not known_views:
        return ""
    views_text = _current_translator().unit(
        "view",
        known_views,
        display_count=dissemination.get("known_social_views_label") or _format_number(known_views),
    )
    highest_views = int(dissemination.get("highest_social_views") or 0)
    if highest_views:
        return _cv_text(
            "summary",
            "social_views_with_highest",
            views=views_text,
            highest=_current_translator().unit(
                "view",
                highest_views,
                display_count=dissemination.get("highest_social_views_label")
                or _format_number(highest_views),
            ),
        )
    return _cv_text("summary", "social_views", views=views_text)


def _recognition_sentence(recognition: dict[str, Any]) -> str:
    parts = []
    honors_text = str(recognition.get("honors_text") or "")
    grants_text = str(recognition.get("grants_text") or "")
    if honors_text:
        parts.append(_cv_text("summary_labels", "honors", value=honors_text))
    if grants_text:
        parts.append(_cv_text("summary_labels", "grants", value=grants_text))
    if not parts:
        return ""
    return _cv_text("summary", "recognition", value="; ".join(parts))


def _recognition_counts_sentence(recognition: dict[str, Any]) -> str:
    parts = [
        recognition.get("honors_phrase"),
        recognition.get("grants_phrase"),
    ]
    recognition_text = _join_summary_phrases(parts)
    if not recognition_text:
        return ""
    return _cv_text("summary", "recognition_counts", value=recognition_text)


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


def _join_summary_phrases(values: Any) -> str:
    items = [str(value) for value in values if value]
    return _current_translator().format_list(items)


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
                    _prepare_position(record, model.section_detail("current_positions"), model)
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
            records["software_projects"],
            records["software_packages"],
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
            records["university_classes"],
            records["academic_supervision"],
            records["teaching_innovation_projects"],
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
            records["scientific_articles"],
            records["presentations"],
            records["press"],
            records["social_media"],
            records["tv_media"],
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
            "summary": _reviewing_summary(records["reviewing"]),
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
    block = _entry_block(
        model,
        "experience",
        records,
        lambda record, detail: _prepare_position(record, detail, model),
    )
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
            [_prepare_position(record, detail, model) for record in sorted_records],
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
        details.append(_detail_key("program", record["program"]))
    if _detail_at_least(detail, "standard") and record.get("grade"):
        details.append(_detail_key("grade", record["grade"]))
    thesis = record.get("thesis") or {}
    if _detail_at_least(detail, "standard") and thesis.get("title"):
        details.append(_detail(str(thesis.get("type") or _cv_text("fields", "thesis")), thesis["title"]))
    return _entry(
        record,
        kind=str(record.get("level") or _cv_text("kinds", "degree")),
        title=str(record.get("title") or ""),
        date=str(_date_span(record) or record.get("date_awarded") or ""),
        meta="",
        details=details,
        references=_references(
            _reference("honors", record.get("related_honors", [])),
            _reference("grants", _resolved(record, "grant_ids")),
        ),
        css_class="cv-entry-education",
    )


def _prepare_certification(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if record.get("duration_hours"):
        hours = _format_number(float(record["duration_hours"]))
        details.append(
            _detail_key(
                "duration",
                _current_translator().unit(
                    "hour",
                    float(record["duration_hours"]),
                    display_count=hours,
                ),
            )
        )
    if _detail_at_least(detail, "standard") and record.get("notes"):
        details.append(_detail_key("notes", record["notes"]))
    return _entry(
        record,
        kind=_cv_text("kinds", "certification"),
        title=str(record.get("title") or ""),
        date=str(record.get("issue_date") or _date_span(record)),
        meta=_organization_names_text(record) or str(record.get("issuer") or ""),
        details=details,
        css_class="cv-entry-certification",
    )


def _prepare_position(
    record: dict[str, Any],
    detail: str,
    model: CVModel | None = None,
) -> dict[str, Any]:
    meta_parts = []
    if record.get("department"):
        meta_parts.append(str(record["department"]))
    if record.get("location"):
        meta_parts.append(str(record["location"]))
    return _entry(
        record,
        kind=str(record.get("employment_type") or _cv_text("kinds", "position")),
        title=str(record.get("title") or ""),
        date=_date_span(record),
        meta=_join_nonempty(meta_parts, separator=" · "),
        references=_references(_reference("grants", record.get("related_grants", []))),
        tasks=_position_tasks(record, detail, model),
        css_class="cv-entry-experience",
    )


def _position_tasks(
    record: dict[str, Any],
    detail: str,
    model: CVModel | None = None,
) -> list[str]:
    tasks = [str(task) for task in record.get("tasks") or [] if str(task).strip()]
    if not tasks:
        return []

    task_filter = model.task_filters.get("experience") if model is not None else None
    if not task_filter:
        return tasks if _detail_at_least(detail, "full") else []

    if detail in {"hidden", "micro"}:
        return []

    include_keywords = _lowered_keywords(task_filter.get("include_keywords", []))
    exclude_keywords = _lowered_keywords(task_filter.get("exclude_keywords", []))
    selected_tasks = [
        task
        for task in tasks
        if _task_matches_filter(task, include_keywords, exclude_keywords)
    ]
    max_tasks = task_filter.get("max_tasks_per_record")
    if max_tasks is not None:
        selected_tasks = selected_tasks[: int(max_tasks)]
    return selected_tasks


def _lowered_keywords(keywords: Any) -> list[str]:
    return [str(keyword).lower() for keyword in keywords or [] if str(keyword).strip()]


def _task_matches_filter(
    task: str,
    include_keywords: list[str],
    exclude_keywords: list[str],
) -> bool:
    task_text = task.lower()
    if include_keywords and not any(keyword in task_text for keyword in include_keywords):
        return False
    return not any(keyword in task_text for keyword in exclude_keywords)


def _prepare_stay(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if _detail_at_least(detail, "standard") and record.get("purpose"):
        details.append(_detail_key("purpose", record["purpose"]))
    if _detail_at_least(detail, "full") and record.get("description"):
        details.append(_detail_key("description", record["description"]))
    location = record.get("location") or {}
    location_text = _join_nonempty(
        [location.get("city"), location.get("country")],
        separator=", ",
    )
    return _entry(
        record,
        kind=str(record.get("type") or _cv_text("kinds", "research_stay")),
        title=str(record.get("title") or ""),
        date=_date_span(record),
        meta=location_text,
        details=details,
        references=_references(_reference("grants", record.get("related_grants", []))),
        css_class="cv-entry-stay",
    )


def _prepare_honor(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if _detail_at_least(detail, "standard") and record.get("context"):
        details.append(_detail_key("context", record["context"]))
    return _entry(
        record,
        kind=_cv_text("kinds", "honor"),
        title=str(record.get("title") or ""),
        date=str(record.get("issue_date") or ""),
        meta=", ".join(record.get("awarding_entities") or []),
        details=details,
        references=_references(_reference("related_education", _resolved(record, "degree_ids"))),
        css_class="cv-entry-honor",
    )


def _prepare_grant(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if _detail_at_least(detail, "standard") and record.get("purpose"):
        details.append(_detail_key("purpose", record["purpose"]))
    if _detail_at_least(detail, "compact") and _date_span(record):
        details.append(_detail_key("period", _date_span(record)))
    return _entry(
        record,
        kind=str(record.get("awarding_entity_type") or _cv_text("kinds", "grant")),
        title=str(record.get("name") or record.get("title") or ""),
        date=str(record.get("issue_date") or ""),
        meta=str(record.get("awarding_entity") or ""),
        details=details,
        references=_references(
            _reference("related_positions", _resolved(record, "position_ids")),
            _reference("related_stays", _resolved(record, "stay_ids")),
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
    is_conference = "conference" in publication_type.lower()
    kind = _cv_text("kinds", "conference_paper" if is_conference else "journal_paper")
    details = []
    if record.get("venue"):
        venue_label_key = "conference" if is_conference else "journal"
        details.append(_detail_key(venue_label_key, record["venue"]))
    if _detail_at_least(detail, "standard") and record.get("publisher"):
        details.append(_detail_key("publisher", record["publisher"]))
    if _detail_at_least(detail, "compact") and record.get("doi"):
        doi = str(record["doi"])
        details.append(_detail_key("doi", doi, f"https://doi.org/{doi}"))
    return _entry(
        record,
        kind=kind,
        title=str(record.get("title") or ""),
        date=str(record.get("publication_date") or ""),
        meta=_author_line(record, detail),
        meta_label=_cv_text("meta", "authors"),
        url=str(record.get("url") or ""),
        details=details,
        references=_publication_references(record) if _detail_at_least(detail, "standard") else [],
        organizations=[],
        css_class="cv-entry-conference" if is_conference else "cv-entry-publication",
    )


def _prepare_research_project(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if _detail_at_least(detail, "standard") and record.get("funders"):
        details.append(_detail_key("funders", ", ".join(record["funders"])))
    if _detail_at_least(detail, "standard") and record.get("principal_investigators"):
        details.append(
            _detail_key("principal_investigators", ", ".join(record["principal_investigators"]))
        )
    title = _join_nonempty([record.get("acronym"), record.get("title")], separator=": ")
    return _entry(
        record,
        kind=_localized_participation(record.get("participation"))
        or _cv_text("kinds", "research_project"),
        title=title,
        date=_date_span(record),
        meta=str(record.get("code") or ""),
        details=details,
        css_class="cv-entry-project",
    )


def _prepare_software_project(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if _detail_at_least(detail, "standard") and record.get("description"):
        details.append(_detail_key("description", record["description"]))
    if _detail_at_least(detail, "standard") and record.get("domains"):
        details.append(_detail_key("domains", ", ".join(record["domains"])))
    return _entry(
        record,
        kind=_cv_text("kinds", "software_project"),
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
        kind=str(record.get("ecosystem") or _cv_text("kinds", "package")),
        title=str(record.get("name") or ""),
        meta="",
        url=str(stats.get("package_url") or stats.get("mvnrepository_url") or ""),
        details=_software_package_details(record, stats, detail, package_coordinates),
        css_class="cv-entry-package",
    )


def _prepare_university_class(record: dict[str, Any], _detail_level: str) -> dict[str, Any]:
    details = [_detail_key("degree_programme", record.get("degree") or "")]
    if record.get("department"):
        details.append(_detail_key("department", record["department"]))
    if record.get("workload_hours"):
        details.append(_detail_key("hours", _format_number(float(record["workload_hours"]))))
    return _entry(
        record,
        kind=_cv_text("kinds", "university_class"),
        title=str(record.get("name") or ""),
        date=str(record.get("academic_year") or _date_span(record)),
        meta="",
        details=details,
        css_class="cv-entry-teaching",
    )


def _prepare_academic_supervision(record: dict[str, Any], _detail_level: str) -> dict[str, Any]:
    details = [
        _detail_key(label_key, value)
        for label_key, value in (
            ("degree_programme", record.get("degree")),
            ("role", record.get("role")),
        )
        if value
    ]
    if record.get("workload_hours"):
        details.append(_detail_key("hours", _format_number(float(record["workload_hours"]))))
    if record.get("repository_url"):
        details.append(
            _detail_key("repository", _cv_text("fields", "repository"), record["repository_url"])
        )
    return _entry(
        record,
        kind=str(record.get("type") or _cv_text("kinds", "academic_supervision")),
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
        details.append(_detail_key("funding_entity", record["funding_entity"]))
    return _entry(
        record,
        kind=_localized_participation(record.get("participation"))
        or _cv_text("kinds", "teaching_innovation_project"),
        title=title,
        date=_date_span(record),
        meta="",
        details=details,
        css_class="cv-entry-project",
    )


def _prepare_scientific_article(record: dict[str, Any], _detail_level: str) -> dict[str, Any]:
    meta = _join_nonempty(
        [
            record.get("outlet"),
            _cv_text("fields", "issue_with_value", value=record["issue"])
            if record.get("issue")
            else "",
        ],
        separator=" · ",
    )
    return _entry(
        record,
        kind=_cv_text("kinds", "article"),
        title=str(record.get("title") or ""),
        date=str(record.get("date") or ""),
        meta=meta,
        url=str(record.get("url") or ""),
        references=_references(
            _reference("publications", _resolved(record, "publication_ids")),
            _reference("software_packages", _resolved(record, "software_package_ids")),
        ),
        css_class="cv-entry-dissemination",
    )


def _prepare_presentation(record: dict[str, Any], _detail_level: str) -> dict[str, Any]:
    return _entry(
        record,
        kind=str(record.get("type") or _cv_text("kinds", "presentation")),
        title=str(record.get("title") or ""),
        date=_date_span(record),
        meta=_join_nonempty([record.get("event"), record.get("location")], separator=" · "),
        references=_references(
            _reference("publications", _resolved(record, "publication_ids")),
            _reference("software_packages", _resolved(record, "software_package_ids")),
        ),
        css_class="cv-entry-dissemination",
    )


def _prepare_press_item(record: dict[str, Any], _detail_level: str) -> dict[str, Any]:
    return _entry(
        record,
        kind=str(record.get("outlet") or _cv_text("kinds", "press")),
        title=str(record.get("title") or ""),
        date=str(record.get("date") or ""),
        url=str(record.get("url") or ""),
        references=_references(_reference("publications", _resolved(record, "publication_ids"))),
        css_class="cv-entry-press",
    )


def _prepare_social_media_item(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if record.get("accounts"):
        details.append(_detail_key("accounts", ", ".join(_account_names(record["accounts"]))))
    if record.get("views"):
        details.append(_detail_key("views", _format_number(float(record["views"]))))
    if _detail_at_least(detail, "standard") and record.get("description"):
        details.append(_detail_key("description", record["description"]))
    return _entry(
        record,
        kind=str(record.get("platform") or _cv_text("kinds", "social_media")),
        title=str(record.get("platform") or ""),
        date=str(record.get("date") or ""),
        url=str(record.get("url") or ""),
        details=details,
        references=_references(_reference("publications", _resolved(record, "publication_ids"))),
        css_class="cv-entry-social",
    )


def _prepare_tv_item(record: dict[str, Any], detail: str) -> dict[str, Any]:
    details = []
    if _detail_at_least(detail, "standard") and record.get("description"):
        details.append(_detail_key("description", record["description"]))
    return _entry(
        record,
        kind=str(record.get("channel") or _cv_text("kinds", "tv_media")),
        title=str(record.get("program") or ""),
        date=str(record.get("date") or ""),
        url=str(record.get("url") or ""),
        details=details,
        references=_references(_reference("publications", _resolved(record, "publication_ids"))),
        css_class="cv-entry-tv",
    )


def _prepare_reviewing(record: dict[str, Any], _detail_level: str) -> dict[str, Any]:
    count = int(record.get("manuscripts_reviewed") or 0)
    return _entry(
        record,
        kind=str(record.get("publisher") or _cv_text("kinds", "reviewing")),
        title=str(record.get("journal") or ""),
        date=str(record.get("last_updated") or ""),
        details=[
            _detail_key(
                "reviewed_manuscripts",
                _current_translator().unit("manuscript", count),
            )
        ],
        css_class="cv-entry-reviewing",
    )


def _entry(
    record: dict[str, Any],
    *,
    kind: str,
    title: str,
    date: str = "",
    meta: str = "",
    meta_label: str = "",
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
        "meta_label": meta_label or _cv_text("meta", "additional_information"),
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


def _detail_key(label_key: str, value: Any, url: Any = "") -> dict[str, str]:
    return _detail(_cv_text("fields", label_key), value, url)


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
        details.append(_detail_key("package_name", package_name, stats.get("package_url")))
    if package_coordinates:
        details.append(
            _detail_key(
                "coordinate",
                package_coordinates,
                stats.get("mvnrepository_url") or stats.get("package_url"),
            )
        )

    if not _detail_at_least(detail, "standard"):
        return [item for item in details if item]

    if stats.get("summary"):
        details.append(_detail_key("summary", stats["summary"]))
    if stats.get("latest_version"):
        details.append(_detail_key("latest_version", stats["latest_version"]))
    if stats.get("release_count") not in (None, ""):
        details.append(_detail_key("releases", _format_number(float(stats["release_count"]))))
    if stats.get("license"):
        details.append(_detail_key("license", stats["license"]))

    if ecosystem.lower() == "pypi":
        if stats.get("total_downloads") not in (None, ""):
            details.append(
                _detail_key("total_downloads", _format_number(float(stats["total_downloads"])))
            )
        download_period = _join_nonempty(
            [stats.get("first_download_date"), stats.get("last_download_date")],
            separator=" - ",
        )
        if download_period:
            details.append(_detail_key("download_period", download_period))
        if stats.get("requires_python"):
            details.append(_detail_key("requires_python", stats["requires_python"]))
        if stats.get("clickpy_url"):
            details.append(_detail_key("downloads_dashboard", "ClickPy", stats["clickpy_url"]))
    elif ecosystem.lower() == "maven":
        if stats.get("last_updated"):
            details.append(_detail_key("last_updated", stats["last_updated"]))
        if stats.get("java_release"):
            details.append(_detail_key("java_release", stats["java_release"]))
        if stats.get("dependency_count") not in (None, ""):
            details.append(_detail_key("dependencies", _format_number(float(stats["dependency_count"]))))
        if stats.get("project_url"):
            details.append(_detail_key("project_url", stats["project_url"], stats["project_url"]))
        if stats.get("mvnrepository_url"):
            details.append(
                _detail_key("maven_repository", "MvnRepository", stats["mvnrepository_url"])
            )

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
            _metric_key("software_projects", len(software_projects)),
            _metric_key("published_packages", len(software_packages)),
            _metric_key("research_domains", len(domain_counts)),
        ],
        "highlights": _summary_lines(
            ("main_domains", _counter_list(domain_counts, limit=3)),
            ("package_ecosystems", _counter_list(ecosystem_counts, limit=3)),
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
            _metric_key("classroom_hours", _format_number(total_hours)),
            _metric_key("academic_years", len(academic_years)),
            _metric_key("courses", len(university_classes)),
            _metric_key("degree_programmes", len(degrees)),
            _metric_key("supervisions", len(academic_supervision)),
            _metric_key("teaching_innovation_projects", len(teaching_innovation_projects)),
        ],
        "highlights": _summary_lines(
            ("supervision", _counter_list(supervision_counts, limit=3)),
            ("teaching_innovation", "; ".join(innovation_titles[:2])),
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
    metrics = [
        _metric_key("dissemination_items", total_items),
        _metric_key("scientific_articles", len(scientific_articles)),
    ]
    if presentations:
        metrics.append(_metric_key("presentations", len(presentations)))
    if press:
        metrics.append(_metric_key("press_items", len(press)))
    if social_media:
        metrics.append(_metric_key("social_media_items", len(social_media)))
    if tv_media:
        metrics.append(_metric_key("tv_media_items", len(tv_media)))
    if known_views:
        metrics.append(_metric_key("known_social_views", _format_number(sum(known_views))))

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
        "metrics": metrics,
        "highlights": _summary_lines(
            (
                "highest_known_social_media_item",
                _current_translator().unit(
                    "view",
                    max(known_views),
                    display_count=_format_number(max(known_views)),
                )
                if known_views
                else "",
            ),
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
            _metric_key("reviewed_manuscripts", total_reviews),
            _metric_key("journals", len(reviewing)),
        ],
        "highlights": _summary_lines(
            (
                "main_journals",
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


def _metric_key(label_key: str, value: int | str) -> dict[str, str]:
    return _metric(_cv_text("metrics", label_key), value)


def _summary_lines(*items: tuple[str, str]) -> list[str]:
    return [_cv_text("summary_labels", label_key, value=value) for label_key, value in items if value]


def _counter_list(counter: Counter[str], *, limit: int) -> str:
    items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return ", ".join(f"{label} ({value})" for label, value in items)


def _publication_references(record: dict[str, Any]) -> list[dict[str, Any]]:
    return _references(
        _reference("organizations", _resolved(record, "organization_ids")),
        _reference("software", _resolved(record, "software_project_ids")),
        _reference("projects", _resolved(record, "research_project_ids")),
        _reference("positions", _resolved(record, "position_ids")),
        _reference("stays", _resolved(record, "stay_ids")),
        _reference("grants", _resolved(record, "grant_ids")),
    )


def _reference(reference_id: str, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not records:
        return None
    return {
        "id": reference_id,
        "label": _cv_text("references", reference_id),
        "records": records,
    }


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
    return format_date_range(
        record.get("start_date"),
        record.get("end_date"),
        _current_translator(),
    )


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
    return format_duration(months, _current_translator())


def _format_number(value: float) -> str:
    return format_number(value, _current_translator())


def generate_cv(
    model: str = "academic_rich",
    output_dir: Path | str = "build/cv",
    output_format: str = "pdf",
    page_limit: int | None = None,
    language: str | None = DEFAULT_LANGUAGE,
    application: Path | str | None = None,
    data_dir: Path | str = "data",
    model_dir: Path | str = "cv_models",
    template_dir: Path | str = "templates/cv",
    static_dir: Path | str = "assets/cv",
) -> CVOutput:
    output_format = output_format.lower()
    if output_format not in {"html", "pdf"}:
        raise ValueError(f"Unsupported CV format: {output_format}")

    if application is not None:
        cv_model = load_cv_model_with_application(application, model_dir)
        resolved_language = language or cv_model.language
    else:
        cv_model = load_cv_model(model_path_for(model, model_dir))
        resolved_language = language or DEFAULT_LANGUAGE
    if resolved_language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {resolved_language}")

    cv_model = replace(cv_model, language=resolved_language)
    cv_model = _with_page_limit_override(cv_model, page_limit)
    resolver = PortfolioResolver(load_data(data_dir))
    translator = load_translator(resolved_language)

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
            translator=translator,
            template_dir=template_dir,
            html_path=html_path,
            output_path=output_path,
        )
    else:
        content = _render_cv_html(cv_model, resolver, translator, template_dir)
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
    if model.output_stem:
        return model.output_stem

    language_suffix = f"_{model.language}"
    if page_limit_override is None:
        return f"{model.name}{language_suffix}"
    return f"{model.name}_{model.page_limit}p{language_suffix}"


def _render_pdf_with_page_limit(
    *,
    base_model: CVModel,
    resolver: PortfolioResolver,
    translator: Translator,
    template_dir: Path | str,
    html_path: Path,
    output_path: Path,
) -> tuple[CVModel, str, int, str]:
    attempted_results: list[tuple[CVModel, str, int]] = []

    for attempt_model in _compression_attempts(base_model):
        content = _render_cv_html(attempt_model, resolver, translator, template_dir)
        html_path.write_text(content, encoding="utf-8")
        page_count = _export_pdf_from_html(html_path, output_path)
        attempted_results.append((attempt_model, content, page_count))

        if attempt_model.page_limit is None or page_count <= attempt_model.page_limit:
            fit_status = "not_limited" if attempt_model.page_limit is None else "fits"
            return attempt_model, content, page_count, fit_status

    final_model, final_content, final_page_count = attempted_results[-1]
    raise RuntimeError(
        _page_limit_failure_message(final_model, final_page_count, resolver, translator)
    )


def _render_cv_html(
    model: CVModel,
    resolver: PortfolioResolver,
    translator: Translator,
    template_dir: Path | str,
) -> str:
    view = build_cv_view(model, resolver, translator)
    return render_template(template_dir, model.template_name, view, translator=translator)


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
    preserved_sections = set(model.layout.get("preserve_sections_on_fit") or [])
    for section in AGGREGABLE_SECTIONS:
        if section not in preserved_sections and sections.get(section) != "hidden":
            sections[section] = "aggregate"

    for section, floor in model.fit_detail_floors.items():
        if sections.get(section) in {None, "hidden"}:
            continue
        if SECTION_DETAIL_RANKS[sections[section]] < SECTION_DETAIL_RANKS[floor]:
            sections[section] = floor

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
            _hashable_config(model.layout),
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        unique_models.append(model)
    return unique_models


def _hashable_config(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _hashable_config(child)) for key, child in value.items()))
    if isinstance(value, list):
        return tuple(_hashable_config(child) for child in value)
    return value


def _page_limit_failure_message(
    model: CVModel,
    page_count: int,
    resolver: PortfolioResolver,
    translator: Translator,
) -> str:
    contributors = _page_limit_contributors(model, resolver)
    contributor_labels = {
        "publications": translator.t("cv.sections.publications"),
        "experience": translator.t("cv.sections.experience"),
        "research_projects": translator.t("cv.sections.research_projects"),
        "degrees": translator.t("cv.sections.education"),
        "honors": translator.t("cv.sections.honors"),
        "grants": translator.t("cv.sections.grants"),
        "research_stays": translator.t("cv.sections.research_stays"),
    }
    lines = [
        translator.t(
            "cv.document.page_limit_failure",
            model=model.name,
            pages=model.page_limit,
        ),
        translator.t("cv.document.minimum_compact_render", pages=page_count),
        translator.t("cv.document.largest_contributors"),
    ]
    lines.extend(
        translator.t(
            "cv.document.contributor_item_count",
            label=contributor_labels.get(label, label),
            count=translator.unit("record", count),
        )
        for label, count in contributors
    )
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
