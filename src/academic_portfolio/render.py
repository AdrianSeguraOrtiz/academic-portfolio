from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

from academic_portfolio.i18n import (
    Translator,
    configure_jinja_i18n,
    format_date_range,
    load_translator,
    localized_value,
)


def compact(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def linked_names(
    records: Sequence[Mapping[str, Any]] | None,
    translator: Translator | None = None,
) -> str:
    if not records:
        return ""
    return Markup(", ").join(record_link(record, translator) for record in records)


def anchor_links(
    records: Sequence[Mapping[str, Any]] | None,
    translator: Translator | None = None,
) -> str:
    if not records:
        return ""
    return Markup(", ").join(anchor_link(record, translator) for record in records)


def account_names(values: Sequence[Any] | None) -> str:
    if not values:
        return ""

    names: list[str] = []
    for value in values:
        text = compact(value)
        if not text:
            continue

        if text.startswith(("http://", "https://")):
            parsed = urlparse(text)
            path_parts = [part for part in parsed.path.split("/") if part]
            text = path_parts[0] if path_parts else parsed.netloc

        if text not in names:
            names.append(text)

    return ", ".join(names)


def record_name(record: Mapping[str, Any], translator: Translator | None = None) -> str:
    for field in ("name", "title", "journal", "program", "event", "full_name"):
        value = record.get(field)
        if value:
            value = translator.localized(value) if translator is not None else localized_value(value)
            return str(value)
    return str(record.get("id", ""))


def date_range(start: Any, end: Any, translator: Translator | None = None) -> str:
    return format_date_range(start, end, translator)


def html_link(label: Any, url: Any) -> str:
    label_text = compact(label)
    url_text = compact(url)
    if label_text and url_text:
        return Markup('<a href="{}">{}</a>').format(url_text, label_text)
    return label_text or url_text


def anchor_id(record: Mapping[str, Any] | Any) -> str:
    if isinstance(record, Mapping):
        return compact(record.get("id"))
    return compact(record)


def anchor_link(record: Mapping[str, Any], translator: Translator | None = None) -> str:
    target = anchor_id(record)
    if not target:
        return record_name(record, translator)
    return html_link(record_name(record, translator), f"#{target}")


def record_link(record: Mapping[str, Any], translator: Translator | None = None) -> str:
    return html_link(record_name(record, translator), record_url(record))


def record_url(record: Mapping[str, Any]) -> str:
    website = record.get("website")
    if website:
        return str(website)

    url = record.get("url")
    if url:
        return str(url)

    urls = record.get("urls")
    if isinstance(urls, Mapping):
        for field in ("github", "website", "docs"):
            value = urls.get(field)
            if value:
                return str(value)

    return ""


def create_environment(template_dir: Path | str, translator: Translator | None = None) -> Environment:
    active_translator = translator or load_translator()
    environment = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(
            enabled_extensions=("html", "html.j2", "xml"),
            default_for_string=True,
        ),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
        finalize=active_translator.localized,
    )
    environment.filters["compact"] = compact
    environment.filters["anchor_link"] = lambda record: anchor_link(record, active_translator)
    environment.filters["anchor_links"] = lambda records: anchor_links(records, active_translator)
    environment.filters["account_names"] = account_names
    environment.filters["date_range"] = lambda start, end: date_range(start, end, active_translator)
    environment.filters["html_link"] = html_link
    environment.filters["linked_names"] = lambda records: linked_names(records, active_translator)
    environment.filters["record_link"] = lambda record: record_link(record, active_translator)
    environment.filters["record_name"] = lambda record: record_name(record, active_translator)
    configure_jinja_i18n(environment, active_translator)
    return environment


def render_template(
    template_dir: Path | str,
    template_name: str,
    context: Mapping[str, Any],
    translator: Translator | None = None,
) -> str:
    template = create_environment(template_dir, translator).get_template(template_name)
    return template.render(**context).strip() + "\n"
