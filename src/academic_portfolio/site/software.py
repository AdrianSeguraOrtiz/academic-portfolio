from __future__ import annotations

from collections import Counter
from typing import Any

from academic_portfolio.site.common import (
    _month_label,
    _month_number,
    _percentage,
    _year_from_month,
)

LANGUAGE_COLORS = {
    "Dockerfile": "#384d54",
    "Go": "#00add8",
    "HTML": "#e34c26",
    "Java": "#b07219",
    "Julia": "#9558b2",
    "MATLAB": "#d85f2a",
    "Makefile": "#427819",
    "Perl": "#0298c3",
    "Python": "#3572a5",
    "R": "#198ce7",
    "Shell": "#89a65a",
}

OTHER_LANGUAGE_COLOR = "#66706d"
LANGUAGE_CHART_TOP_LIMIT = 7


def _attach_github_stats(
    projects: list[dict[str, Any]],
    github_stats_by_url: dict[str, dict[str, Any]],
) -> None:
    for project in projects:
        github_url = str(project.get("urls", {}).get("github") or "")
        if github_url in github_stats_by_url:
            project["github"] = github_stats_by_url[github_url]



def _attach_package_stats(
    packages: list[dict[str, Any]],
    package_stats_by_id: dict[str, dict[str, Any]],
) -> None:
    for package in packages:
        package_id = str(package.get("id"))
        if package_id in package_stats_by_id:
            package["package_stats"] = package_stats_by_id[package_id]



def _software_github_summary(projects: list[dict[str, Any]]) -> dict[str, Any]:
    github_records = [project["github"] for project in projects if project.get("github")]
    pushed_dates = [stats.get("pushed_at") for stats in github_records if stats.get("pushed_at")]
    return {
        "repositories_with_stats": len(github_records),
        "total_stars": sum(int(stats.get("stargazers_count") or 0) for stats in github_records),
        "total_forks": sum(int(stats.get("forks_count") or 0) for stats in github_records),
        "open_issues": sum(int(stats.get("open_issues_count") or 0) for stats in github_records),
        "active_repositories": sum(1 for stats in github_records if not stats.get("archived")),
        "last_push_date": max(pushed_dates)[:10] if pushed_dates else None,
    }



def _software_timeline(projects: list[dict[str, Any]]) -> dict[str, Any]:
    timeline_projects = []
    timeline_months: list[int] = []

    for project in projects:
        github = project.get("github", {})
        commit_months = _commit_month_counts(github)
        created_month = _month_number(github.get("created_at"))
        pushed_month = _month_number(github.get("pushed_at"))
        active_months = list(commit_months)

        if not active_months and created_month is None and pushed_month is None:
            continue

        timeline_months.extend(active_months)
        timeline_months.extend(
            month for month in (created_month, pushed_month) if month is not None
        )

        timeline_projects.append(
            {
                "project": project,
                "commit_months": commit_months,
                "created_month": created_month,
                "pushed_month": pushed_month,
                "language": project.get("github", {}).get("language"),
                "color": _language_color(project.get("github", {}).get("language")),
            }
        )

    if not timeline_months:
        return {"years": [], "rows": []}

    min_month = min(timeline_months)
    max_month = max(timeline_months)
    total_months = max(max_month - min_month + 1, 1)
    rows = []
    for item in sorted(timeline_projects, key=_timeline_recent_sort_month, reverse=True):
        commit_months = item["commit_months"]
        max_commits = max(commit_months.values(), default=1)
        created = item["created_month"]
        pushed = item["pushed_month"]
        rows.append(
            {
                "project": item["project"],
                "language": item["language"],
                "color": item["color"],
                "months": [
                    {
                        "month": _month_label(month),
                        "count": count,
                        "left": _percentage(month - min_month, total_months),
                        "width": max(_percentage(1, total_months), 0.8),
                        "height": round(8 + ((count / max_commits) * 24), 2),
                    }
                    for month, count in sorted(commit_months.items())
                ],
                "created_left": _percentage(int(created) - min_month, total_months)
                if created is not None
                else None,
                "pushed_left": _percentage(int(pushed) - min_month + 1, total_months)
                if pushed is not None
                else None,
            }
        )

    return {
        "years": list(range(_year_from_month(min_month), _year_from_month(max_month) + 1)),
        "rows": rows,
    }



def _software_language_chart(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    language_totals: Counter[str] = Counter()
    for project in projects:
        languages = project.get("github", {}).get("languages", {})
        if isinstance(languages, dict):
            language_totals.update(
                {
                    str(language): int(byte_count)
                    for language, byte_count in languages.items()
                    if int(byte_count) > 0
                }
            )

    total_bytes = sum(language_totals.values())
    if total_bytes == 0:
        return []

    top_languages = language_totals.most_common(LANGUAGE_CHART_TOP_LIMIT)
    other_bytes = total_bytes - sum(byte_count for _language, byte_count in top_languages)
    chart = [
        {
            "name": language,
            "bytes": byte_count,
            "share": round((byte_count / total_bytes) * 100, 1),
            "color": _language_color(language),
        }
        for language, byte_count in top_languages
    ]
    if other_bytes:
        chart.append(
            {
                "name": "Other",
                "bytes": other_bytes,
                "share": round((other_bytes / total_bytes) * 100, 1),
                "color": OTHER_LANGUAGE_COLOR,
            }
        )

    return chart



def _commit_month_counts(github: dict[str, Any]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for item in github.get("commit_months", []):
        if not isinstance(item, dict):
            continue

        month = _month_number(item.get("month"))
        count = item.get("count")
        if month is None or count is None:
            continue

        counts[month] = int(count)

    return counts



def _timeline_recent_sort_month(row: dict[str, Any]) -> int:
    commit_months = row["commit_months"]
    candidates = [
        _month_number(row["project"].get("github", {}).get("last_commit_at")),
        *list(commit_months),
        *(
            month
            for month in (row["created_month"], row["pushed_month"])
            if month is not None
        ),
    ]
    return max((month for month in candidates if month is not None), default=0)



def _language_color(language: str | None) -> str:
    if not language:
        return OTHER_LANGUAGE_COLOR
    return LANGUAGE_COLORS.get(language, OTHER_LANGUAGE_COLOR)
