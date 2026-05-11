from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup


def compact(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def linked_names(records: Sequence[Mapping[str, Any]] | None) -> str:
    if not records:
        return ""
    return Markup(", ").join(record_link(record) for record in records)


def anchor_links(records: Sequence[Mapping[str, Any]] | None) -> str:
    if not records:
        return ""
    return Markup(", ").join(anchor_link(record) for record in records)


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


def record_name(record: Mapping[str, Any]) -> str:
    for field in ("name", "title", "journal", "program", "event", "full_name"):
        value = record.get(field)
        if value:
            return str(value)
    return str(record.get("id", ""))


def date_range(start: Any, end: Any) -> str:
    start_text = compact(start)
    end_text = compact(end) or "Present"
    if start_text:
        return f"{start_text} - {end_text}"
    return end_text if end else ""


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


def anchor_link(record: Mapping[str, Any]) -> str:
    target = anchor_id(record)
    if not target:
        return record_name(record)
    return html_link(record_name(record), f"#{target}")


def record_link(record: Mapping[str, Any]) -> str:
    return html_link(record_name(record), record_url(record))


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


def create_environment(template_dir: Path | str) -> Environment:
    environment = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(
            enabled_extensions=("html", "html.j2", "xml"),
            default_for_string=True,
        ),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )
    environment.filters["compact"] = compact
    environment.filters["anchor_link"] = anchor_link
    environment.filters["anchor_links"] = anchor_links
    environment.filters["account_names"] = account_names
    environment.filters["date_range"] = date_range
    environment.filters["html_link"] = html_link
    environment.filters["linked_names"] = linked_names
    environment.filters["record_link"] = record_link
    environment.filters["record_name"] = record_name
    return environment


def render_template(template_dir: Path | str, template_name: str, context: Mapping[str, Any]) -> str:
    template = create_environment(template_dir).get_template(template_name)
    return template.render(**context).strip() + "\n"
