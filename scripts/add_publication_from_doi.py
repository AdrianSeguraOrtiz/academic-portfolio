#!/usr/bin/env python3
"""Add a journal or conference publication to data/research/publications.yaml from a DOI."""

from __future__ import annotations

import argparse
import copy
from datetime import date
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml

PUBLICATION_FIELDS = (
    "id",
    "title",
    "authors",
    "venue",
    "publisher",
    "volume",
    "article_number",
    "publication_date",
    "type",
    "format",
    "doi",
    "url",
    "total_authors",
    "corresponding_author",
    "organization_ids",
    "software_project_ids",
    "research_project_ids",
    "position_ids",
    "stay_ids",
    "grant_ids",
)
GROUP_BY_KIND = {
    "journal": "journal_papers",
    "conference": "conference_papers",
}
FORMAT_BY_KIND = {
    "journal": "Journal",
    "conference": "Conference proceeding",
}
MANUAL_FIELDS = (
    "corresponding_author",
    "organization_ids",
    "software_project_ids",
    "research_project_ids",
    "position_ids",
    "stay_ids",
    "grant_ids",
)
COUNTRY_NAMES = {
    "canada": "Canada",
    "estonia": "Estonia",
    "finland": "Finland",
    "france": "France",
    "germany": "Germany",
    "greece": "Greece",
    "south africa": "South Africa",
    "spain": "Spain",
    "switzerland": "Switzerland",
    "ukraine": "Ukraine",
    "united kingdom": "United Kingdom",
    "united states": "United States",
    "usa": "United States",
}


@dataclass(frozen=True)
class PublicationMetadata:
    title: str | None
    authors: list[str]
    venue: str | None
    publisher: str | None
    volume: str | None
    article_number: str | None
    publication_date: str | None
    doi: str
    url: str
    source_type: str | None
    affiliation_strings: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class AffiliationCandidate:
    display_name: str
    openalex_id: str | None
    ror: str | None
    type: str | None
    country_code: str | None
    acronyms: tuple[str, ...]
    alternatives: tuple[str, ...]
    homepage_url: str | None
    city: str | None
    country: str | None
    latitude: float | None
    longitude: float | None


@dataclass(frozen=True)
class AffiliationReport:
    matched_organization_ids: list[str]
    suggested_organizations: list[dict[str, Any]]
    warnings: list[str]


@dataclass(frozen=True)
class ResearchContextSuggestion:
    kind: str
    item_id: str
    title: str
    organization_ids: list[str]
    start_date: str | None
    end_date: str | None
    reasons: list[str]
    score: int


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch DOI metadata and append a complete publication record to "
            "data/research/publications.yaml."
        )
    )
    parser.add_argument("doi", help="Publication DOI, with or without https://doi.org/")
    parser.add_argument("kind", choices=sorted(GROUP_BY_KIND), help="Publication kind.")
    parser.add_argument(
        "--data-file",
        default="data/research/publications.yaml",
        type=Path,
        help="Path to publications.yaml.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated record without modifying the YAML file.",
    )
    parser.add_argument(
        "--mailto",
        help="Optional contact email included in the Crossref User-Agent.",
    )
    parser.add_argument(
        "--organizations-file",
        default="data/entities/organizations.yaml",
        type=Path,
        help=(
            "Path to organizations.yaml. It is read only, and only used to map "
            "existing affiliation names and suggest missing organizations."
        ),
    )
    parser.add_argument(
        "--interactive-contexts",
        action="store_true",
        help=(
            "Recover affiliations, suggest missing organizations, and ask which "
            "recommended positions, research stays, and derived grants should be linked."
        ),
    )
    parser.add_argument("--profile-file", default="data/profile.yaml", type=Path)
    parser.add_argument("--experience-file", default="data/career/experience.yaml", type=Path)
    parser.add_argument("--stays-file", default="data/career/research_stays.yaml", type=Path)
    parser.add_argument("--grants-file", default="data/career/grants.yaml", type=Path)
    args = parser.parse_args()

    try:
        metadata = fetch_doi_metadata(args.doi, mailto=args.mailto)
        document = load_publications(args.data_file)
        affiliation_report = AffiliationReport([], [], [])
        selected_organizations = []
        context_suggestions: list[ResearchContextSuggestion] = []
        selected_grant_ids: list[str] = []
        if args.interactive_contexts:
            affiliation_report = fetch_affiliation_report(
                metadata.doi,
                args.organizations_file,
                fallback_affiliations=metadata.affiliation_strings,
                mailto=args.mailto,
            )
        record = build_publication_record(
            document,
            metadata,
            args.kind,
            organization_ids=affiliation_report.matched_organization_ids,
        )
        assert_new_doi(document, record["doi"])
        if args.interactive_contexts:
            selected_organizations = select_suggested_organizations(
                affiliation_report.suggested_organizations,
                args.organizations_file,
                mailto=args.mailto,
            )
            record["organization_ids"] = unique_strings(
                [*record["organization_ids"], *(item["id"] for item in selected_organizations)]
            )
            context_suggestions = recommend_research_contexts(
                publication_date=record["publication_date"],
                publication_organization_ids=record["organization_ids"],
                profile_path=args.profile_file,
                experience_path=args.experience_file,
                stays_path=args.stays_file,
                organizations_path=args.organizations_file,
            )
            selected_contexts = select_research_contexts(context_suggestions)
            record["position_ids"] = [
                context.item_id for context in selected_contexts if context.kind == "position"
            ]
            record["stay_ids"] = [context.item_id for context in selected_contexts if context.kind == "stay"]
            selected_grant_ids = select_grants_for_contexts(
                position_ids=record["position_ids"],
                stay_ids=record["stay_ids"],
                grants_path=args.grants_file,
            )
            record["grant_ids"] = selected_grant_ids
    except (OSError, ValueError, HTTPError, URLError, TimeoutError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(yaml.safe_dump(record, sort_keys=False, allow_unicode=True).strip())
    else:
        if selected_organizations:
            append_organizations(args.organizations_file, selected_organizations)
            print(f"Added {len(selected_organizations)} organization(s) to {args.organizations_file}.")
        group = GROUP_BY_KIND[args.kind]
        document.setdefault(group, []).append(record)
        document[group] = sorted(
            document[group],
            key=lambda item: (str(item.get("publication_date") or "9999-99-99"), str(item["id"])),
        )
        write_publications(args.data_file, document)
        print(f"Added {record['id']} to {args.data_file} ({group}).")

    print_report(
        record,
        metadata,
        affiliation_report,
        selected_organizations,
        context_suggestions,
        selected_grant_ids,
        context_enrichment_enabled=args.interactive_contexts,
    )
    return 0


def fetch_doi_metadata(raw_doi: str, mailto: str | None = None) -> PublicationMetadata:
    doi = normalize_doi(raw_doi)
    if not doi:
        raise ValueError("DOI cannot be empty.")

    errors: list[str] = []
    for fetcher in (_fetch_crossref, _fetch_doi_csl):
        try:
            payload = fetcher(doi, mailto)
            return metadata_from_payload(doi, payload)
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            errors.append(f"{fetcher.__name__}: {error}")

    raise ValueError("Could not fetch DOI metadata. " + " | ".join(errors))


def _fetch_crossref(doi: str, mailto: str | None) -> dict[str, Any]:
    url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
    payload = _http_json(url, mailto=mailto)
    message = payload.get("message")
    if not isinstance(message, dict):
        raise ValueError("Crossref response does not contain a metadata message.")
    return message


def _fetch_doi_csl(doi: str, mailto: str | None) -> dict[str, Any]:
    request = Request(
        f"https://doi.org/{quote(doi, safe='/')}",
        headers={
            "Accept": "application/vnd.citationstyles.csl+json",
            "User-Agent": _user_agent(mailto),
        },
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("DOI content negotiation response is not a metadata object.")
    return payload


def _http_json(url: str, mailto: str | None) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": _user_agent(mailto),
        },
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("HTTP response is not a JSON object.")
    return payload


def _user_agent(mailto: str | None) -> str:
    suffix = f" (mailto:{mailto})" if mailto else ""
    return f"academic-portfolio DOI importer{suffix}"


def metadata_from_payload(doi: str, payload: dict[str, Any]) -> PublicationMetadata:
    warnings: list[str] = []
    authors = [_author_name(author) for author in _as_list(payload.get("author"))]
    authors = [author for author in authors if author]
    publication_date, date_warning = _publication_date(payload)
    if date_warning:
        warnings.append(date_warning)

    return PublicationMetadata(
        title=_first_string(payload.get("title")),
        authors=authors,
        venue=_venue(payload),
        publisher=_string_or_none(payload.get("publisher")),
        volume=_string_or_none(payload.get("volume")),
        article_number=_string_or_none(
            payload.get("article-number")
            or payload.get("article_number")
            or payload.get("article")
            or payload.get("number")
        ),
        publication_date=publication_date,
        doi=normalize_doi(str(payload.get("DOI") or payload.get("doi") or doi)),
        url=f"https://doi.org/{doi}",
        source_type=_string_or_none(payload.get("type")),
        affiliation_strings=_affiliation_strings_from_payload(payload),
        warnings=warnings,
    )


def _affiliation_strings_from_payload(payload: dict[str, Any]) -> list[str]:
    affiliations: list[str] = []
    for author in _as_list(payload.get("author")):
        if not isinstance(author, dict):
            continue
        for affiliation in _as_list(author.get("affiliation")):
            if not isinstance(affiliation, dict):
                continue
            name = _string_or_none(affiliation.get("name"))
            if name and name not in affiliations:
                affiliations.append(name)
    return affiliations


def load_publications(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        document = yaml.safe_load(file) or {}
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a YAML mapping.")
    for group in GROUP_BY_KIND.values():
        document.setdefault(group, [])
        if not isinstance(document[group], list):
            raise ValueError(f"{path}: {group} must be a list.")
    return document


def write_publications(path: Path, document: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        document = yaml.safe_load(file) or {}
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a YAML mapping.")
    return document


def build_publication_record(
    document: dict[str, Any],
    metadata: PublicationMetadata,
    kind: str,
    organization_ids: list[str] | None = None,
) -> dict[str, Any]:
    record = {
        "id": next_publication_id(document),
        "title": metadata.title,
        "authors": metadata.authors,
        "venue": metadata.venue,
        "publisher": metadata.publisher,
        "volume": metadata.volume,
        "article_number": metadata.article_number,
        "publication_date": metadata.publication_date,
        "type": "Scientific paper",
        "format": FORMAT_BY_KIND[kind],
        "doi": metadata.doi,
        "url": metadata.url,
        "total_authors": len(metadata.authors) if metadata.authors else None,
        "corresponding_author": None,
        "organization_ids": organization_ids or [],
        "software_project_ids": [],
        "research_project_ids": [],
        "position_ids": [],
        "stay_ids": [],
        "grant_ids": [],
    }
    return {field: record[field] for field in PUBLICATION_FIELDS}


def fetch_affiliation_report(
    doi: str,
    organizations_path: Path,
    fallback_affiliations: list[str],
    mailto: str | None = None,
) -> AffiliationReport:
    warnings: list[str] = []
    try:
        existing_organizations = load_organizations(organizations_path)
    except (OSError, ValueError) as error:
        return AffiliationReport([], [], [f"Existing organizations could not be read: {error}"])

    try:
        work = _fetch_openalex_work(doi, mailto=mailto)
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        warnings.append(f"OpenAlex affiliations could not be fetched: {error}")
        return _crossref_affiliation_report(fallback_affiliations, existing_organizations, warnings)

    candidates = _affiliation_candidates_from_work(work, mailto=mailto, warnings=warnings)
    if not candidates:
        warnings.append("OpenAlex did not provide affiliations; using Crossref affiliation strings.")
        return _crossref_affiliation_report(fallback_affiliations, existing_organizations, warnings)

    matched_ids, unmatched = match_affiliations_to_organizations(candidates, existing_organizations)
    suggestions = suggest_organization_records(unmatched, existing_organizations)
    openalex_report = AffiliationReport(matched_ids, suggestions, warnings)
    crossref_report = _crossref_affiliation_report(
        fallback_affiliations,
        existing_organizations,
        [],
        warn_if_empty=False,
    )
    return renumber_affiliation_suggestions(
        merge_affiliation_reports(openalex_report, crossref_report),
        existing_organizations,
    )


def _crossref_affiliation_report(
    affiliation_strings: list[str],
    organizations: list[dict[str, Any]],
    warnings: list[str],
    warn_if_empty: bool = True,
) -> AffiliationReport:
    if not affiliation_strings:
        if warn_if_empty:
            warnings.append("Crossref did not provide author affiliation strings.")
        return AffiliationReport([], [], warnings)

    matched_ids = match_affiliation_strings_to_organizations(affiliation_strings, organizations)
    candidates = crossref_affiliation_candidates(affiliation_strings, organizations)
    suggestions = suggest_organization_records(candidates, organizations)
    return AffiliationReport(matched_ids, suggestions, warnings)


def merge_affiliation_reports(*reports: AffiliationReport) -> AffiliationReport:
    matched_ids: list[str] = []
    suggestions_by_name: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    for report in reports:
        for organization_id in report.matched_organization_ids:
            if organization_id not in matched_ids:
                matched_ids.append(organization_id)
        for suggestion in report.suggested_organizations:
            key = normalize_label(str(suggestion.get("name") or ""))
            if key and key not in suggestions_by_name:
                suggestions_by_name[key] = suggestion
        warnings.extend(report.warnings)

    return AffiliationReport(matched_ids, list(suggestions_by_name.values()), warnings)


def renumber_affiliation_suggestions(
    report: AffiliationReport,
    organizations: list[dict[str, Any]],
) -> AffiliationReport:
    next_number = next_organization_number(organizations)
    suggestions: list[dict[str, Any]] = []
    for offset, suggestion in enumerate(report.suggested_organizations):
        renumbered = dict(suggestion)
        renumbered["id"] = f"organization_{next_number + offset:02d}"
        suggestions.append(renumbered)
    return AffiliationReport(report.matched_organization_ids, suggestions, report.warnings)


def _fetch_openalex_work(doi: str, mailto: str | None) -> dict[str, Any]:
    return _http_json(f"https://api.openalex.org/works/doi:{quote(doi, safe=':/')}", mailto=mailto)


def load_organizations(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        document = yaml.safe_load(file) or {}
    organizations = document.get("organizations") if isinstance(document, dict) else None
    if not isinstance(organizations, list):
        raise ValueError(f"{path}: organizations must be a list.")
    return [item for item in organizations if isinstance(item, dict)]


def append_organizations(path: Path, organizations_to_add: list[dict[str, Any]]) -> None:
    with path.open(encoding="utf-8") as file:
        document = yaml.safe_load(file) or {}
    organizations = document.get("organizations") if isinstance(document, dict) else None
    if not isinstance(organizations, list):
        raise ValueError(f"{path}: organizations must be a list.")
    organizations.extend(organizations_to_add)
    path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def select_suggested_organizations(
    suggestions: list[dict[str, Any]],
    organizations_path: Path,
    mailto: str | None,
) -> list[dict[str, Any]]:
    if not suggestions:
        return []
    if not sys.stdin.isatty():
        print(
            "Suggested organizations were found, but stdin is not interactive; "
            "nothing will be added to organizations.yaml.",
            file=sys.stderr,
        )
        return []

    existing_organizations = load_organizations(organizations_path)
    print("\nSuggested organizations:")
    for index, suggestion in enumerate(suggestions, start=1):
        location = suggestion.get("location") if isinstance(suggestion.get("location"), dict) else {}
        place = ", ".join(
            value
            for value in (
                _string_or_none(location.get("city")),
                _string_or_none(location.get("country")),
            )
            if value
        )
        suffix = f" ({place})" if place else ""
        print(f"{index}. {suggestion.get('name')}{suffix}")

    raw_selection = input(
        "Organizations to add to organizations.yaml [numbers, ranges, all, or Enter for none]: "
    )
    indexes = parse_selection(raw_selection, len(suggestions))
    if not indexes:
        return []

    selected = [copy.deepcopy(suggestions[index]) for index in indexes]
    enriched = enrich_organization_records(selected, existing_organizations, mailto=mailto)
    return renumber_organization_records(enriched, existing_organizations)


def parse_selection(raw_selection: str, max_items: int) -> list[int]:
    selection = raw_selection.strip().lower()
    if not selection or selection in {"none", "no", "n"}:
        return []
    if selection in {"all", "a"}:
        return list(range(max_items))

    indexes: list[int] = []
    for token in re.split(r"\s*,\s*", selection):
        if not token:
            continue
        if "-" in token:
            start_raw, end_raw = token.split("-", 1)
            start = int(start_raw)
            end = int(end_raw)
            values = range(min(start, end), max(start, end) + 1)
        else:
            values = [int(token)]
        for value in values:
            index = value - 1
            if index < 0 or index >= max_items:
                raise ValueError(f"Selection {value} is out of range.")
            if index not in indexes:
                indexes.append(index)
    return indexes


def enrich_organization_records(
    organizations_to_add: list[dict[str, Any]],
    existing_organizations: list[dict[str, Any]],
    mailto: str | None,
) -> list[dict[str, Any]]:
    enriched_records: list[dict[str, Any]] = []
    for organization in organizations_to_add:
        enriched = copy.deepcopy(organization)
        details = fetch_openalex_institution_by_name(str(enriched.get("full_name") or enriched.get("name")), mailto)
        if details:
            merge_openalex_institution(enriched, details)
        enrich_coordinates_from_known_city(enriched, existing_organizations)
        enriched_records.append(enriched)
    return enriched_records


def renumber_organization_records(
    organizations_to_add: list[dict[str, Any]],
    existing_organizations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    next_number = next_organization_number(existing_organizations)
    renumbered_records: list[dict[str, Any]] = []
    for offset, organization in enumerate(organizations_to_add):
        renumbered = copy.deepcopy(organization)
        renumbered["id"] = f"organization_{next_number + offset:02d}"
        renumbered_records.append(renumbered)
    return renumbered_records


def recommend_research_contexts(
    publication_date: str | None,
    publication_organization_ids: list[str],
    profile_path: Path,
    experience_path: Path,
    stays_path: Path,
    organizations_path: Path,
) -> list[ResearchContextSuggestion]:
    profile = load_yaml_mapping(profile_path)
    experience = load_yaml_mapping(experience_path)
    stays = load_yaml_mapping(stays_path)
    organizations = load_organizations(organizations_path)
    organization_ancestors = build_organization_ancestor_index(organizations)

    current_position_ids = set(_as_list(profile.get("current_position_ids")))
    current_stay_ids = set(_as_list(profile.get("current_stay_ids")))
    publication_family_ids = expand_organization_ids(publication_organization_ids, organization_ancestors)

    suggestions: list[ResearchContextSuggestion] = []
    for position in _as_list(experience.get("positions")):
        if not isinstance(position, dict):
            continue
        suggestion = score_research_context(
            item=position,
            kind="position",
            current_ids=current_position_ids,
            publication_date=publication_date,
            publication_family_ids=publication_family_ids,
            organization_ancestors=organization_ancestors,
        )
        if suggestion:
            suggestions.append(suggestion)

    for stay in _as_list(stays.get("stays")):
        if not isinstance(stay, dict):
            continue
        suggestion = score_research_context(
            item=stay,
            kind="stay",
            current_ids=current_stay_ids,
            publication_date=publication_date,
            publication_family_ids=publication_family_ids,
            organization_ancestors=organization_ancestors,
        )
        if suggestion:
            suggestions.append(suggestion)

    return sorted(suggestions, key=lambda item: (-item.score, item.kind, item.start_date or ""))


def score_research_context(
    item: dict[str, Any],
    kind: str,
    current_ids: set[Any],
    publication_date: str | None,
    publication_family_ids: set[str],
    organization_ancestors: dict[str, set[str]],
) -> ResearchContextSuggestion | None:
    item_id = _string_or_none(item.get("id"))
    if not item_id:
        return None

    score = 0
    reasons: list[str] = []
    if item_id in current_ids:
        score += 4
        reasons.append("current context")

    start_date = _string_or_none(item.get("start_date"))
    end_date = _string_or_none(item.get("end_date"))
    if publication_date and date_ranges_overlap(publication_date, publication_date, start_date, end_date):
        score += 3
        reasons.append("active on publication date")
    elif publication_date and date_within_months_after_end(publication_date, end_date, months=12):
        score += 1
        reasons.append("ended within 12 months before publication")

    context_organization_ids = [_string_or_none(value) for value in _as_list(item.get("organization_ids"))]
    context_organization_ids = [value for value in context_organization_ids if value]
    context_family_ids = expand_organization_ids(context_organization_ids, organization_ancestors)
    if publication_family_ids and context_family_ids and publication_family_ids.intersection(context_family_ids):
        score += 3
        reasons.append("organization overlap")

    if score < 4:
        return None

    return ResearchContextSuggestion(
        kind=kind,
        item_id=item_id,
        title=localized_or_string(item.get("title")) or item_id,
        organization_ids=context_organization_ids,
        start_date=start_date,
        end_date=end_date,
        reasons=reasons,
        score=score,
    )


def select_research_contexts(
    suggestions: list[ResearchContextSuggestion],
) -> list[ResearchContextSuggestion]:
    if not suggestions:
        print("\nNo position or research stay recommendations found.")
        return []
    if not sys.stdin.isatty():
        print(
            "Position/stay recommendations were found, but stdin is not interactive; none will be linked.",
            file=sys.stderr,
        )
        return []

    print("\nRecommended research contexts:")
    for index, suggestion in enumerate(suggestions, start=1):
        label = "position" if suggestion.kind == "position" else "research stay"
        dates = format_date_span(suggestion.start_date, suggestion.end_date)
        print(f"{index}. {suggestion.item_id} · {label} · {suggestion.title} · {dates}")
        print(f"   Reason: {', '.join(suggestion.reasons)}.")

    raw_selection = input(
        "Contexts to link as position_ids/stay_ids [numbers, ranges, all, or Enter for none]: "
    )
    indexes = parse_selection(raw_selection, len(suggestions))
    return [suggestions[index] for index in indexes]


def select_grants_for_contexts(
    position_ids: list[str],
    stay_ids: list[str],
    grants_path: Path,
) -> list[str]:
    if not position_ids and not stay_ids:
        return []
    grant_suggestions = grant_suggestions_for_contexts(position_ids, stay_ids, grants_path)
    if not grant_suggestions:
        return []
    if not sys.stdin.isatty():
        return [grant["id"] for grant in grant_suggestions]

    print("\nRecommended grants from selected contexts:")
    for index, grant in enumerate(grant_suggestions, start=1):
        print(f"{index}. {grant['id']} · {grant['name']}")
    raw_selection = input("Grants to link [numbers, ranges, all, Enter for all, or none]: ")
    if not raw_selection.strip():
        return [grant["id"] for grant in grant_suggestions]
    indexes = parse_selection(raw_selection, len(grant_suggestions))
    return [grant_suggestions[index]["id"] for index in indexes]


def grant_suggestions_for_contexts(
    position_ids: list[str],
    stay_ids: list[str],
    grants_path: Path,
) -> list[dict[str, Any]]:
    grants = load_yaml_mapping(grants_path)
    suggestions: list[dict[str, Any]] = []
    selected_positions = set(position_ids)
    selected_stays = set(stay_ids)
    for grant in _as_list(grants.get("grants")):
        if not isinstance(grant, dict):
            continue
        grant_id = _string_or_none(grant.get("id"))
        if not grant_id:
            continue
        grant_positions = set(_as_list(grant.get("position_ids")))
        grant_stays = set(_as_list(grant.get("stay_ids")))
        if selected_positions.intersection(grant_positions) or selected_stays.intersection(grant_stays):
            suggestions.append({"id": grant_id, "name": _string_or_none(grant.get("name")) or grant_id})
    return suggestions


def fetch_openalex_institution_by_name(name: str, mailto: str | None) -> dict[str, Any] | None:
    normalized_name = normalize_label(name)
    if not normalized_name:
        return None
    try:
        payload = _http_json(
            f"https://api.openalex.org/institutions?search={quote(name)}&per-page=5",
            mailto=mailto,
        )
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None

    best_result: dict[str, Any] | None = None
    best_score = 0.0
    for result in _as_list(payload.get("results")):
        if not isinstance(result, dict):
            continue
        labels = [
            _string_or_none(result.get("display_name")),
            *(_string_or_none(value) for value in _as_list(result.get("display_name_acronyms"))),
            *(_string_or_none(value) for value in _as_list(result.get("display_name_alternatives"))),
        ]
        score = max(
            (name_match_score(normalized_name, normalize_label(label or "")) for label in labels),
            default=0.0,
        )
        if score > best_score:
            best_score = score
            best_result = result

    return best_result if best_score >= 0.86 else None


def name_match_score(query: str, candidate: str) -> float:
    if not query or not candidate:
        return 0.0
    if query == candidate:
        return 1.0
    if contains_normalized_phrase(candidate, query) or contains_normalized_phrase(query, candidate):
        return 0.92
    return SequenceMatcher(None, query, candidate).ratio()


def merge_openalex_institution(organization: dict[str, Any], details: dict[str, Any]) -> None:
    acronyms = [
        acronym
        for acronym in (_string_or_none(value) for value in _as_list(details.get("display_name_acronyms")))
        if acronym
    ]
    if not organization.get("abbreviation") and acronyms:
        organization["abbreviation"] = acronyms[0]

    if not organization.get("type"):
        candidate = _affiliation_candidate(details, details)
        organization["type"] = local_organization_type(candidate)

    if not organization.get("website"):
        organization["website"] = _string_or_none(details.get("homepage_url"))

    location = organization.setdefault("location", {})
    if not isinstance(location, dict):
        location = {}
        organization["location"] = location
    geo = details.get("geo") if isinstance(details.get("geo"), dict) else {}
    location["city"] = location.get("city") or _string_or_none(geo.get("city"))
    location["country"] = location.get("country") or _string_or_none(geo.get("country"))
    coordinates = location.setdefault("coordinates", {})
    if not isinstance(coordinates, dict):
        coordinates = {}
        location["coordinates"] = coordinates
    coordinates["latitude"] = coordinates.get("latitude") or _round_coordinate(_float_or_none(geo.get("latitude")))
    coordinates["longitude"] = coordinates.get("longitude") or _round_coordinate(_float_or_none(geo.get("longitude")))


def enrich_coordinates_from_known_city(
    organization: dict[str, Any],
    existing_organizations: list[dict[str, Any]],
) -> None:
    location = organization.get("location")
    if not isinstance(location, dict):
        return
    city = normalize_label(_string_or_none(location.get("city")) or "")
    country = normalize_label(_string_or_none(location.get("country")) or "")
    coordinates = location.get("coordinates")
    if not isinstance(coordinates, dict):
        return
    if coordinates.get("latitude") is not None and coordinates.get("longitude") is not None:
        return

    for existing in existing_organizations:
        existing_location = existing.get("location")
        if not isinstance(existing_location, dict):
            continue
        if normalize_label(_string_or_none(existing_location.get("city")) or "") != city:
            continue
        if normalize_label(_string_or_none(existing_location.get("country")) or "") != country:
            continue
        existing_coordinates = existing_location.get("coordinates")
        if not isinstance(existing_coordinates, dict):
            continue
        coordinates["latitude"] = existing_coordinates.get("latitude")
        coordinates["longitude"] = existing_coordinates.get("longitude")
        return


def _affiliation_candidates_from_work(
    work: dict[str, Any],
    mailto: str | None,
    warnings: list[str],
) -> list[AffiliationCandidate]:
    raw_institutions: dict[str, dict[str, Any]] = {}
    for authorship in _as_list(work.get("authorships")):
        if not isinstance(authorship, dict):
            continue
        for institution in _as_list(authorship.get("institutions")):
            if not isinstance(institution, dict):
                continue
            key = (
                _string_or_none(institution.get("ror"))
                or _string_or_none(institution.get("id"))
                or _string_or_none(institution.get("display_name"))
            )
            if key:
                raw_institutions.setdefault(key, institution)

    candidates = []
    for institution in raw_institutions.values():
        details = _openalex_institution_details(institution, mailto=mailto, warnings=warnings)
        candidates.append(_affiliation_candidate(institution, details))
    return candidates


def _openalex_institution_details(
    institution: dict[str, Any],
    mailto: str | None,
    warnings: list[str],
) -> dict[str, Any]:
    institution_id = _string_or_none(institution.get("id"))
    if not institution_id:
        return {}
    local_id = institution_id.rstrip("/").rsplit("/", 1)[-1]
    if not local_id.startswith("I"):
        return {}
    try:
        return _http_json(f"https://api.openalex.org/institutions/{local_id}", mailto=mailto)
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        name = _string_or_none(institution.get("display_name")) or institution_id
        warnings.append(f"OpenAlex institution details could not be fetched for {name}: {error}")
        return {}


def _affiliation_candidate(
    institution: dict[str, Any],
    details: dict[str, Any],
) -> AffiliationCandidate:
    geo = details.get("geo") if isinstance(details.get("geo"), dict) else {}
    return AffiliationCandidate(
        display_name=(
            _string_or_none(details.get("display_name"))
            or _string_or_none(institution.get("display_name"))
            or "Unknown organization"
        ),
        openalex_id=_string_or_none(details.get("id") or institution.get("id")),
        ror=_string_or_none(details.get("ror") or institution.get("ror")),
        type=_string_or_none(details.get("type") or institution.get("type")),
        country_code=_string_or_none(details.get("country_code") or institution.get("country_code")),
        acronyms=tuple(
            item
            for item in (_string_or_none(value) for value in _as_list(details.get("display_name_acronyms")))
            if item
        ),
        alternatives=tuple(
            item
            for item in (_string_or_none(value) for value in _as_list(details.get("display_name_alternatives")))
            if item
        ),
        homepage_url=_string_or_none(details.get("homepage_url")),
        city=_string_or_none(geo.get("city")),
        country=_string_or_none(geo.get("country")),
        latitude=_float_or_none(geo.get("latitude")),
        longitude=_float_or_none(geo.get("longitude")),
    )


def match_affiliation_strings_to_organizations(
    affiliation_strings: list[str],
    organizations: list[dict[str, Any]],
) -> list[str]:
    entries = organization_label_entries(organizations)
    matched_ids: list[str] = []

    for affiliation in affiliation_strings:
        normalized_affiliation = normalize_label(affiliation)
        matches = [
            (normalized_affiliation.find(label), organization_id)
            for organization_id, label, _raw_label in entries
            if contains_normalized_phrase(normalized_affiliation, label)
        ]
        for _position, organization_id in sorted(matches):
            if organization_id not in matched_ids:
                matched_ids.append(organization_id)

    return matched_ids


def crossref_affiliation_candidates(
    affiliation_strings: list[str],
    organizations: list[dict[str, Any]],
) -> list[AffiliationCandidate]:
    entries = organization_label_entries(organizations)
    candidates: list[AffiliationCandidate] = []
    seen: set[str] = set()

    for affiliation in affiliation_strings:
        country = infer_affiliation_country(affiliation, organizations)
        city = infer_affiliation_city(affiliation, organizations)
        segments = split_affiliation_segments(affiliation)
        for segment in segments:
            if not is_probable_organization_segment(segment):
                continue
            normalized_segment = normalize_label(segment)
            if any(contains_normalized_phrase(normalized_segment, label) for _id, label, _raw in entries):
                continue
            if normalized_segment in seen:
                continue
            seen.add(normalized_segment)
            name, acronym = extract_affiliation_acronym(segment)
            candidates.append(
                AffiliationCandidate(
                    display_name=name,
                    openalex_id=None,
                    ror=None,
                    type=infer_affiliation_type(name),
                    country_code=None,
                    acronyms=(acronym,) if acronym else (),
                    alternatives=(),
                    homepage_url=None,
                    city=city,
                    country=country,
                    latitude=None,
                    longitude=None,
                )
            )

    return candidates


def organization_label_entries(organizations: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    for organization in organizations:
        organization_id = _string_or_none(organization.get("id"))
        if not organization_id:
            continue
        for field in ("name", "full_name", "abbreviation"):
            raw_label = _string_or_none(organization.get(field))
            label = normalize_label(raw_label or "")
            if label and len(label) >= 3:
                entries.append((organization_id, label, raw_label or ""))
    return sorted(entries, key=lambda item: len(item[1]), reverse=True)


def split_affiliation_segments(affiliation: str) -> list[str]:
    return [
        clean_affiliation_segment(segment)
        for segment in re.split(r"\s*[,;]\s*", affiliation)
        if clean_affiliation_segment(segment)
    ]


def clean_affiliation_segment(segment: str) -> str:
    return re.sub(r"\s+", " ", segment).strip(" .")


def is_probable_organization_segment(segment: str) -> bool:
    normalized = normalize_label(segment)
    if not normalized or len(normalized) < 4:
        return False
    if re.search(r"\d", normalized):
        return False
    if normalized in COUNTRY_NAMES:
        return False
    if normalized in {"malaga", "valencia", "lille", "athens", "marousi", "campanillas"}:
        return False
    address_terms = {
        "street",
        "avenue",
        "road",
        "calle",
        "arquitecto",
        "severo",
        "ochoa",
        "parque",
        "technological",
        "tecnologica",
    }
    if any(term in normalized.split() for term in address_terms):
        return False
    organization_terms = {
        "athena",
        "biomedical",
        "center",
        "centre",
        "centro",
        "department",
        "departamento",
        "escuela",
        "faculty",
        "facultad",
        "group",
        "hospital",
        "ibima",
        "institute",
        "instituto",
        "itis",
        "khaos",
        "laboratory",
        "laboratorio",
        "polytechnic",
        "research",
        "school",
        "technical",
        "universidad",
        "universite",
        "university",
    }
    return any(term in normalized.split() for term in organization_terms)


def extract_affiliation_acronym(segment: str) -> tuple[str, str | None]:
    match = re.search(r"^(?P<name>.+?)\s*\((?P<acronym>[A-Za-z0-9-]{2,15})\)\s*$", segment)
    if not match:
        return segment, None
    return match.group("name").strip(), match.group("acronym").strip()


def infer_affiliation_type(name: str) -> str | None:
    normalized = normalize_label(name)
    words = normalized.split()
    if "university" in words or "universidad" in words or "universite" in words:
        return "University"
    if "school" in words or "escuela" in words or "faculty" in words or "facultad" in words:
        return "School"
    if "department" in words or "departamento" in words:
        return "Department"
    if "institute" in words or "instituto" in words:
        return "Research institute"
    if "center" in words or "centre" in words or "centro" in words:
        return "Research center"
    if "laboratory" in words or "laboratorio" in words:
        return "Laboratory"
    if "group" in words:
        return "Research group"
    return None


def infer_affiliation_country(
    affiliation: str,
    organizations: list[dict[str, Any]],
) -> str | None:
    normalized_segments = [normalize_label(segment) for segment in split_affiliation_segments(affiliation)]
    for country in sorted(known_country_names(organizations), key=len, reverse=True):
        if normalize_label(country) in normalized_segments:
            return country
    return None


def infer_affiliation_city(affiliation: str, organizations: list[dict[str, Any]]) -> str | None:
    normalized_affiliation = normalize_label(affiliation)
    for city in known_city_names(organizations):
        if contains_normalized_phrase(normalized_affiliation, normalize_label(city)):
            return city
    return None


def known_country_names(organizations: list[dict[str, Any]]) -> set[str]:
    countries = {country.title() for country in COUNTRY_NAMES.values()}
    for organization in organizations:
        location = organization.get("location")
        if not isinstance(location, dict):
            continue
        country = _string_or_none(location.get("country"))
        if country:
            countries.add(country)
    return countries


def known_city_names(organizations: list[dict[str, Any]]) -> set[str]:
    cities: set[str] = set()
    for organization in organizations:
        location = organization.get("location")
        if not isinstance(location, dict):
            continue
        city = _string_or_none(location.get("city"))
        if city:
            cities.add(city)
    return cities


def match_affiliations_to_organizations(
    candidates: list[AffiliationCandidate],
    organizations: list[dict[str, Any]],
) -> tuple[list[str], list[AffiliationCandidate]]:
    index = organization_lookup_index(organizations)
    matched_ids: list[str] = []
    unmatched: list[AffiliationCandidate] = []

    for candidate in candidates:
        organization_id = _match_candidate(candidate, index)
        if organization_id:
            if organization_id not in matched_ids:
                matched_ids.append(organization_id)
        else:
            unmatched.append(candidate)

    return matched_ids, unmatched


def organization_lookup_index(organizations: list[dict[str, Any]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for organization in organizations:
        organization_id = _string_or_none(organization.get("id"))
        if not organization_id:
            continue
        for field in ("name", "full_name", "abbreviation"):
            key = normalize_label(_string_or_none(organization.get(field)) or "")
            if key:
                index.setdefault(key, organization_id)
        website_key = normalize_url_host(_string_or_none(organization.get("website")) or "")
        if website_key:
            index.setdefault(f"url:{website_key}", organization_id)
    return index


def _match_candidate(candidate: AffiliationCandidate, index: dict[str, str]) -> str | None:
    labels = [candidate.display_name, *candidate.acronyms, *candidate.alternatives]
    for label in labels:
        key = normalize_label(label)
        if key in index:
            return index[key]
    website_key = normalize_url_host(candidate.homepage_url or "")
    if website_key and f"url:{website_key}" in index:
        return index[f"url:{website_key}"]
    return None


def suggest_organization_records(
    candidates: list[AffiliationCandidate],
    organizations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    next_number = next_organization_number(organizations)
    for offset, candidate in enumerate(candidates):
        suggestions.append(
            {
                "id": f"organization_{next_number + offset:02d}",
                "name": candidate.display_name,
                "full_name": candidate.display_name,
                "abbreviation": candidate.acronyms[0] if candidate.acronyms else None,
                "type": local_organization_type(candidate),
                "parent_organization_id": None,
                "location": {
                    "city": candidate.city,
                    "country": candidate.country,
                    "coordinates": {
                        "latitude": _round_coordinate(candidate.latitude),
                        "longitude": _round_coordinate(candidate.longitude),
                    },
                },
                "website": candidate.homepage_url,
            }
        )
    return suggestions


def next_organization_number(organizations: list[dict[str, Any]]) -> int:
    max_number = 0
    for organization in organizations:
        raw_id = _string_or_none(organization.get("id")) or ""
        if not raw_id.startswith("organization_"):
            continue
        try:
            max_number = max(max_number, int(raw_id.rsplit("_", 1)[1]))
        except ValueError:
            continue
    return max_number + 1


def local_organization_type(candidate: AffiliationCandidate) -> str | None:
    local_types = {
        "Department",
        "Health research institute",
        "Laboratory",
        "Research center",
        "Research group",
        "Research institute",
        "School",
        "University",
    }
    if candidate.type in local_types:
        return candidate.type
    display_name = candidate.display_name.lower()
    if "university" in display_name or "universidad" in display_name or "université" in display_name:
        return "University"
    if candidate.type == "education":
        return "University"
    if candidate.type == "healthcare":
        return "Health research institute"
    if candidate.type == "facility":
        return "Research center"
    return candidate.type.replace("_", " ").title() if candidate.type else None


def build_organization_ancestor_index(organizations: list[dict[str, Any]]) -> dict[str, set[str]]:
    parent_by_id = {
        str(organization["id"]): _string_or_none(organization.get("parent_organization_id"))
        for organization in organizations
        if organization.get("id")
    }
    ancestors: dict[str, set[str]] = {}
    for organization_id in parent_by_id:
        values = {organization_id}
        parent_id = parent_by_id.get(organization_id)
        while parent_id and parent_id not in values:
            values.add(parent_id)
            parent_id = parent_by_id.get(parent_id)
        ancestors[organization_id] = values
    return ancestors


def expand_organization_ids(
    organization_ids: list[str],
    organization_ancestors: dict[str, set[str]],
) -> set[str]:
    expanded: set[str] = set()
    for organization_id in organization_ids:
        expanded.update(organization_ancestors.get(organization_id, {organization_id}))
    return expanded


def date_ranges_overlap(
    start_a: str | None,
    end_a: str | None,
    start_b: str | None,
    end_b: str | None,
) -> bool:
    parsed_start_a = parse_partial_date(start_a, default_end=False)
    parsed_end_a = parse_partial_date(end_a, default_end=True) or date.max
    parsed_start_b = parse_partial_date(start_b, default_end=False)
    parsed_end_b = parse_partial_date(end_b, default_end=True) or date.max
    if not parsed_start_a or not parsed_start_b:
        return False
    return parsed_start_a <= parsed_end_b and parsed_start_b <= parsed_end_a


def date_within_months_after_end(
    value: str | None,
    end_date: str | None,
    months: int,
) -> bool:
    parsed_value = parse_partial_date(value, default_end=False)
    parsed_end = parse_partial_date(end_date, default_end=True)
    if not parsed_value or not parsed_end:
        return False
    delta_months = (parsed_value.year - parsed_end.year) * 12 + parsed_value.month - parsed_end.month
    return 0 <= delta_months <= months


def parse_partial_date(value: str | None, default_end: bool) -> date | None:
    if not value:
        return None
    parts = [int(part) for part in str(value).split("-") if part]
    if not parts:
        return None
    year = parts[0]
    month = parts[1] if len(parts) > 1 else (12 if default_end else 1)
    if len(parts) > 2:
        day = parts[2]
    elif default_end:
        day = last_day_of_month(year, month)
    else:
        day = 1
    return date(year, month, day)


def last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def localized_or_string(value: Any) -> str | None:
    if isinstance(value, dict):
        return _string_or_none(value.get("en") or value.get("es") or next(iter(value.values()), None))
    return _string_or_none(value)


def format_date_span(start_date: str | None, end_date: str | None) -> str:
    return f"{start_date or '?'} - {end_date or 'present'}"


def assert_new_doi(document: dict[str, Any], doi: str) -> None:
    existing = {
        normalize_doi(str(item.get("doi") or ""))
        for group in GROUP_BY_KIND.values()
        for item in document.get(group, [])
    }
    if normalize_doi(doi) in existing:
        raise ValueError(f"DOI already exists in publications.yaml: {doi}")


def next_publication_id(document: dict[str, Any]) -> str:
    max_number = 0
    for group in GROUP_BY_KIND.values():
        for item in document.get(group, []):
            raw_id = str(item.get("id") or "")
            if not raw_id.startswith("publication_"):
                continue
            try:
                max_number = max(max_number, int(raw_id.rsplit("_", 1)[1]))
            except ValueError:
                continue
    return f"publication_{max_number + 1:02d}"


def print_report(
    record: dict[str, Any],
    metadata: PublicationMetadata,
    affiliation_report: AffiliationReport,
    selected_organizations: list[dict[str, Any]],
    context_suggestions: list[ResearchContextSuggestion],
    selected_grant_ids: list[str],
    context_enrichment_enabled: bool,
) -> None:
    missing = [
        field
        for field in (
            "title",
            "authors",
            "venue",
            "publisher",
            "volume",
            "article_number",
            "publication_date",
            "total_authors",
        )
        if record[field] in (None, "", [])
    ]
    print("\nRecovered metadata:")
    for field in PUBLICATION_FIELDS:
        if field in MANUAL_FIELDS:
            continue
        print(f"- {field}: {record[field]}")

    print("\nFields not recovered from DOI metadata:")
    if missing:
        for field in missing:
            print(f"- {field}")
    else:
        print("- none")

    print("\nManual portfolio fields to review:")
    for field in MANUAL_FIELDS:
        print(f"- {field}: {record[field]}")

    if not context_enrichment_enabled:
        print("\nAffiliations, organizations, and research contexts:")
        print("- skipped; run with --interactive-contexts to recover and link them.")
    else:
        print("\nAffiliations recovered from DOI metadata:")
        if affiliation_report.matched_organization_ids:
            print("- matched existing organization_ids:")
            for organization_id in affiliation_report.matched_organization_ids:
                print(f"  - {organization_id}")
        else:
            print("- matched existing organization_ids: none")

        print("- suggested new organizations to review (provisional IDs): ")
        if affiliation_report.suggested_organizations:
            print(
                yaml.safe_dump(
                    {"organizations": affiliation_report.suggested_organizations},
                    sort_keys=False,
                    allow_unicode=True,
                    width=100,
                ).strip()
            )
        else:
            print("  none")

        if selected_organizations:
            print("- selected organizations to add/link:")
            print(
                yaml.safe_dump(
                    {"organizations": selected_organizations},
                    sort_keys=False,
                    allow_unicode=True,
                    width=100,
                ).strip()
            )

        if context_suggestions:
            print("\nPosition and research stay recommendations:")
            for suggestion in context_suggestions:
                label = "position_ids" if suggestion.kind == "position" else "stay_ids"
                selected = suggestion.item_id in record[label]
                marker = "selected" if selected else "not selected"
                print(
                    f"- {suggestion.item_id}: {suggestion.title} "
                    f"({label}, {marker}; reasons: {', '.join(suggestion.reasons)})"
                )

    if selected_grant_ids:
        print("\nDerived grant_ids selected:")
        for grant_id in selected_grant_ids:
            print(f"- {grant_id}")

    if metadata.source_type:
        print(f"\nDOI source type: {metadata.source_type}")
    warnings = [*metadata.warnings, *affiliation_report.warnings]
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")


def normalize_doi(value: str) -> str:
    doi = value.strip()
    doi = doi.removeprefix("doi:")
    doi = doi.removeprefix("DOI:")
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix) :]
            break
    return doi.strip().lower()


def _publication_date(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    for field in ("published-print", "published-online", "published", "issued", "created"):
        date_parts = payload.get(field, {}).get("date-parts") if isinstance(payload.get(field), dict) else None
        if not date_parts:
            continue
        first_part = date_parts[0]
        if not isinstance(first_part, list) or not first_part:
            continue
        date_value = "-".join(
            f"{int(part):02d}" if index else str(int(part))
            for index, part in enumerate(first_part[:3])
            if part is not None
        )
        warning = None
        if len(first_part) < 3:
            warning = f"publication_date is partial because {field} only provided {date_value}."
        return date_value, warning
    return None, None


def _venue(payload: dict[str, Any]) -> str | None:
    container_title = _first_string(payload.get("container-title"))
    if container_title:
        return container_title
    event = payload.get("event")
    if isinstance(event, dict):
        event_name = _string_or_none(event.get("name"))
        if event_name:
            return event_name
    for field in ("collection-title", "short-container-title"):
        value = _first_string(payload.get(field))
        if value:
            return value
    return None


def _author_name(author: Any) -> str | None:
    if not isinstance(author, dict):
        return None
    literal = _string_or_none(author.get("name"))
    if literal:
        return literal
    given = _string_or_none(author.get("given"))
    family = _string_or_none(author.get("family"))
    return " ".join(part for part in (given, family) if part) or None


def _first_string(value: Any) -> str | None:
    values = _as_list(value)
    for item in values:
        string_value = _string_or_none(item)
        if string_value:
            return string_value
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def unique_strings(values: list[Any]) -> list[str]:
    unique: list[str] = []
    for value in values:
        string_value = _string_or_none(value)
        if string_value and string_value not in unique:
            unique.append(string_value)
    return unique


def _string_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_coordinate(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def normalize_label(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(character for character in value if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def contains_normalized_phrase(value: str, phrase: str) -> bool:
    if not phrase:
        return False
    return f" {phrase} " in f" {value} "


def normalize_url_host(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = parsed.netloc.lower().removeprefix("www.")
    return host.rstrip("/")


if __name__ == "__main__":
    raise SystemExit(main())
