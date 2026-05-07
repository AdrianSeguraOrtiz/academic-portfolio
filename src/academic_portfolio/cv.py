from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib

from academic_portfolio.loader import load_data
from academic_portfolio.render import render_template
from academic_portfolio.resolver import PortfolioResolver
from academic_portfolio.view_records import (
    attach_related_records,
    resolved_records,
    sort_records_by_field,
    with_resolved_references,
)


@dataclass(frozen=True)
class CVModel:
    name: str
    title: str
    language: str
    sections: list[str]
    options: dict[str, Any]

    @property
    def reverse_chronological(self) -> bool:
        return bool(self.options.get("reverse_chronological", True))

    @property
    def template_name(self) -> str:
        return str(self.options.get("template", f"{self.name}.md.j2"))


@dataclass(frozen=True)
class CVOutput:
    model: CVModel
    output_path: Path
    content: str


def load_cv_model(model_path: Path | str) -> CVModel:
    path = Path(model_path)
    with path.open("rb") as handle:
        raw_model = tomllib.load(handle)

    return CVModel(
        name=str(raw_model["name"]),
        title=str(raw_model["title"]),
        language=str(raw_model.get("language", "en")),
        sections=list(raw_model.get("sections", [])),
        options=dict(raw_model.get("options", {})),
    )


def model_path_for(model: str, model_dir: Path | str = "cv_models") -> Path:
    path = Path(model)
    if path.suffix:
        return path
    return Path(model_dir) / f"{model}.toml"


def build_cv_view(model: CVModel, resolver: PortfolioResolver) -> dict[str, Any]:
    loaded_data = resolver.loaded_data
    profile = dict(loaded_data.documents["profile.yaml"])
    profile["current_positions"] = [
        with_resolved_references(resolver, record)
        for record in resolver.resolve_many(profile.get("current_position_ids", []))
    ]
    profile["current_stays"] = [
        with_resolved_references(resolver, record)
        for record in resolver.resolve_many(profile.get("current_stay_ids", []))
    ]

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

    attach_related_records(degrees, honors, "degree_ids", "related_honors")
    attach_related_records(experience, grants, "position_ids", "related_grants")
    attach_related_records(research_stays, grants, "stay_ids", "related_grants")

    return {
        "model": model,
        "sections": model.sections,
        "options": model.options,
        "profile": profile,
        "degrees": degrees,
        "certifications": resolved_records(
            resolver,
            "career/certifications.yaml",
            "certifications",
            reverse=model.reverse_chronological,
        ),
        "experience": experience,
        "research_stays": research_stays,
        "honors": honors,
        "grants": grants,
        "publication_groups": {
            "journal_papers": journal_papers,
            "conference_papers": conference_papers,
        },
        "publications": sort_records_by_field(
            journal_papers + conference_papers,
            "publication_date",
            reverse=model.reverse_chronological,
        ),
        "software_projects": resolved_records(
            resolver,
            "research/software_projects.yaml",
            "projects",
            reverse=model.reverse_chronological,
        ),
        "software_packages": resolved_records(
            resolver,
            "research/software_packages.yaml",
            "software_packages",
            reverse=False,
        ),
        "research_projects": {
            "funded_projects": resolved_records(
                resolver,
                "research/research_projects.yaml",
                "funded_projects",
                reverse=model.reverse_chronological,
            )
        },
        "reviewing": resolved_records(
            resolver,
            "research/reviewing.yaml",
            "reviewing",
            reverse=model.reverse_chronological,
        ),
        "teaching": {
            "university_classes": resolved_records(
                resolver,
                "activities/teaching/university_classes.yaml",
                "university_classes",
                reverse=model.reverse_chronological,
            ),
            "academic_supervision": resolved_records(
                resolver,
                "activities/teaching/academic_supervision.yaml",
                "academic_supervision",
                reverse=model.reverse_chronological,
            ),
            "teaching_innovation_projects": resolved_records(
                resolver,
                "activities/teaching/teaching_innovation_projects.yaml",
                "teaching_innovation_projects",
                reverse=model.reverse_chronological,
            ),
        },
        "dissemination": {
            "scientific_articles": resolved_records(
                resolver,
                "activities/dissemination/scientific_dissemination_articles.yaml",
                "scientific_dissemination_articles",
                reverse=model.reverse_chronological,
            ),
            "presentations": resolved_records(
                resolver,
                "activities/dissemination/presentations.yaml",
                "presentations",
                reverse=model.reverse_chronological,
            ),
            "press": resolved_records(
                resolver,
                "activities/dissemination/press.yaml",
                "press_items",
                reverse=model.reverse_chronological,
            ),
            "social_media": resolved_records(
                resolver,
                "activities/dissemination/social_media.yaml",
                "social_media_items",
                reverse=model.reverse_chronological,
            ),
            "tv_media": resolved_records(
                resolver,
                "activities/dissemination/tv_media.yaml",
                "tv_items",
                reverse=model.reverse_chronological,
            ),
        },
    }


def generate_cv(
    model: str = "academic_full",
    output_dir: Path | str = "build/cv",
    output_format: str = "md",
    data_dir: Path | str = "data",
    model_dir: Path | str = "cv_models",
    template_dir: Path | str = "templates/cv",
) -> CVOutput:
    if output_format != "md":
        raise ValueError(f"Unsupported CV format: {output_format}")

    cv_model = load_cv_model(model_path_for(model, model_dir))
    resolver = PortfolioResolver(load_data(data_dir))
    view = build_cv_view(cv_model, resolver)
    content = render_template(template_dir, cv_model.template_name, view)

    output_path = Path(output_dir) / f"{cv_model.name}.{output_format}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    return CVOutput(model=cv_model, output_path=output_path, content=content)
