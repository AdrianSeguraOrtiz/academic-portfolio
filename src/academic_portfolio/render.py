from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
import re

from jinja2 import Environment, FileSystemLoader, StrictUndefined


def compact(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def names(records: Sequence[Mapping[str, Any]] | None) -> str:
    if not records:
        return ""
    return ", ".join(record_name(record) for record in records)


def linked_names(records: Sequence[Mapping[str, Any]] | None) -> str:
    if not records:
        return ""
    return ", ".join(record_link(record) for record in records)


def anchor_links(records: Sequence[Mapping[str, Any]] | None) -> str:
    if not records:
        return ""
    return ", ".join(anchor_link(record) for record in records)


def compact_unique(values: Sequence[Any] | None) -> list[str]:
    if not values:
        return []

    result: list[str] = []
    for value in values:
        if value is None or value == "":
            continue

        text = str(value)
        if text not in result:
            result.append(text)

    return result


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


def markdown_link(label: Any, url: Any) -> str:
    label_text = compact(label)
    url_text = compact(url)
    if label_text and url_text:
        return f"[{label_text}]({url_text})"
    return label_text or url_text


def anchor_id(record: Mapping[str, Any] | Any) -> str:
    if isinstance(record, Mapping):
        return compact(record.get("id"))
    return compact(record)


def anchor_link(record: Mapping[str, Any]) -> str:
    target = anchor_id(record)
    if not target:
        return record_name(record)
    return markdown_link(record_name(record), f"#{target}")


def record_link(record: Mapping[str, Any]) -> str:
    return markdown_link(record_name(record), record_url(record))


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


def yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def create_environment(template_dir: Path | str) -> Environment:
    environment = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=False,
        trim_blocks=False,
        lstrip_blocks=False,
        undefined=StrictUndefined,
    )
    environment.filters["compact"] = compact
    environment.filters["anchor_id"] = anchor_id
    environment.filters["anchor_link"] = anchor_link
    environment.filters["anchor_links"] = anchor_links
    environment.filters["compact_unique"] = compact_unique
    environment.filters["date_range"] = date_range
    environment.filters["linked_names"] = linked_names
    environment.filters["markdown_link"] = markdown_link
    environment.filters["names"] = names
    environment.filters["record_link"] = record_link
    environment.filters["record_name"] = record_name
    environment.filters["yes_no"] = yes_no
    return environment


def render_template(template_dir: Path | str, template_name: str, context: Mapping[str, Any]) -> str:
    template = create_environment(template_dir).get_template(template_name)
    return normalize_markdown(template.render(**context))


def normalize_markdown(content: str) -> str:
    lines = [line.rstrip() for line in content.splitlines()]
    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.replace("\n\n  -", "\n  -")
    text = text.replace("\n\n    -", "\n    -")
    return text + "\n"
