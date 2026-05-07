from __future__ import annotations

from collections import Counter
from typing import Any

from academic_portfolio.render import date_range, record_name
from academic_portfolio.site.common import _percentage

DISSEMINATION_CATEGORIES = [
    {"id": "articles", "label": "Scientific articles", "singular": "Scientific article"},
    {"id": "presentations", "label": "Presentations", "singular": "Presentation"},
    {"id": "press", "label": "Press", "singular": "Press"},
    {"id": "social", "label": "Social media", "singular": "Social media"},
    {"id": "tv", "label": "TV media", "singular": "TV media"},
]


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
