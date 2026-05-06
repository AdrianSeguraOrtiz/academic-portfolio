from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

GITHUB_API_ROOT = "https://api.github.com"
USER_AGENT = "academic-portfolio-generator"
CACHE_SCHEMA_VERSION = 2
COMMIT_ACTIVITY_FIELDS = ("commits_count", "first_commit_at", "last_commit_at", "commit_months")


@dataclass(frozen=True)
class GithubCollectionResult:
    stats_by_url: dict[str, dict[str, Any]]
    errors: dict[str, str]


def collect_github_project_stats(
    projects: list[dict[str, Any]],
    *,
    cache_path: Path | str = "build/cache/github_repositories.json",
    timeout: float = 10,
) -> GithubCollectionResult:
    """Fetch public GitHub repository metadata for software projects.

    The collector is intentionally non-fatal: failed requests fall back to cached
    values when available and otherwise leave the project without GitHub stats.
    """

    cache_file = Path(cache_path)
    cache = _load_cache(cache_file)
    token = os.getenv("GITHUB_TOKEN")
    stats_by_url: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    cache_changed = False

    for project in projects:
        url = str(project.get("urls", {}).get("github") or "")
        repository = github_repository_from_url(url)
        if not repository:
            continue

        cached_stats = cache.get(url)
        if cached_stats and _has_commit_activity(cached_stats):
            stats_by_url[url] = cached_stats
            continue

        try:
            stats = _fetch_repository_stats(
                repository,
                cached_stats=cached_stats,
                token=token,
                timeout=timeout,
            )
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            errors[url] = str(exc)
            stats = cached_stats
        else:
            cache[url] = stats
            cache_changed = True

        if stats:
            stats_by_url[url] = stats

    if cache_changed:
        _write_cache(cache_file, cache)

    return GithubCollectionResult(stats_by_url=stats_by_url, errors=errors)


def github_repository_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.netloc.lower() != "github.com":
        return None

    path_parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(path_parts) < 2:
        return None

    owner, repo = path_parts[:2]
    repo = repo.removesuffix(".git")
    if not owner or not repo:
        return None

    return f"{owner}/{repo}"


def _fetch_repository_stats(
    repository: str,
    *,
    cached_stats: dict[str, Any] | None = None,
    token: str | None,
    timeout: float,
) -> dict[str, Any]:
    if cached_stats:
        stats = dict(cached_stats)
    else:
        repository_data, _headers = _request_json(
            f"/repos/{repository}",
            token=token,
            timeout=timeout,
        )
        languages, _language_headers = _request_json(
            f"/repos/{repository}/languages",
            token=token,
            timeout=timeout,
        )
        stats = {
            "repository": repository,
            "html_url": repository_data.get("html_url"),
            "description": repository_data.get("description"),
            "stargazers_count": int(repository_data.get("stargazers_count") or 0),
            "forks_count": int(repository_data.get("forks_count") or 0),
            "watchers_count": int(repository_data.get("watchers_count") or 0),
            "subscribers_count": int(repository_data.get("subscribers_count") or 0),
            "open_issues_count": int(repository_data.get("open_issues_count") or 0),
            "language": repository_data.get("language"),
            "topics": repository_data.get("topics") or [],
            "license": _license_id(repository_data),
            "created_at": repository_data.get("created_at"),
            "updated_at": repository_data.get("updated_at"),
            "pushed_at": repository_data.get("pushed_at"),
            "default_branch": repository_data.get("default_branch"),
            "archived": bool(repository_data.get("archived")),
            "size_kb": int(repository_data.get("size") or 0),
            "languages": languages if isinstance(languages, dict) else {},
        }

    stats.update(
        _fetch_commit_activity(
            repository,
            since=stats.get("created_at"),
            token=token,
            timeout=timeout,
        )
    )
    return stats


def _fetch_commit_activity(
    repository: str,
    *,
    since: Any,
    token: str | None,
    timeout: float,
) -> dict[str, Any]:
    dates: list[str] = []
    page = 1

    while True:
        query = {"per_page": 100, "page": page}
        if since:
            query["since"] = str(since)

        commits, headers = _request_json(
            f"/repos/{repository}/commits?{urlencode(query)}",
            token=token,
            timeout=timeout,
        )
        if not isinstance(commits, list) or not commits:
            break

        for commit in commits:
            date = _commit_date(commit)
            if date:
                dates.append(date)

        link_header = headers.get("Link") or headers.get("link") or ""
        if 'rel="next"' not in link_header:
            break

        page += 1

    sorted_dates = sorted(dates)
    month_counts: dict[str, int] = {}
    for date in sorted_dates:
        month = date[:7]
        month_counts[month] = month_counts.get(month, 0) + 1

    return {
        "commits_count": len(sorted_dates),
        "first_commit_at": sorted_dates[0] if sorted_dates else None,
        "last_commit_at": sorted_dates[-1] if sorted_dates else None,
        "commit_months": [
            {"month": month, "count": count}
            for month, count in sorted(month_counts.items())
        ],
    }


def _commit_date(commit: Any) -> str | None:
    if not isinstance(commit, dict):
        return None

    commit_data = commit.get("commit")
    if not isinstance(commit_data, dict):
        return None

    committer = commit_data.get("committer")
    if isinstance(committer, dict) and committer.get("date"):
        return str(committer["date"])

    author = commit_data.get("author")
    if isinstance(author, dict) and author.get("date"):
        return str(author["date"])

    return None


def _request_json(
    path: str,
    *,
    token: str | None,
    timeout: float,
) -> tuple[Any, dict[str, str]]:
    request = Request(
        f"{GITHUB_API_ROOT}{path}",
        headers=_headers(token),
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
        return payload, dict(response.headers.items())


def _headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _license_id(repository_data: dict[str, Any]) -> str | None:
    license_data = repository_data.get("license")
    if not isinstance(license_data, dict):
        return None

    spdx_id = license_data.get("spdx_id")
    if spdx_id and spdx_id != "NOASSERTION":
        return str(spdx_id)

    name = license_data.get("name")
    return str(name) if name else None


def _load_cache(cache_path: Path) -> dict[str, dict[str, Any]]:
    if not cache_path.exists():
        return {}

    with cache_path.open(encoding="utf-8") as file:
        data = json.load(file)
    repositories = data.get("repositories", {})
    if not isinstance(repositories, dict):
        return {}

    if data.get("schema_version") == CACHE_SCHEMA_VERSION:
        return repositories

    return {
        url: {
            key: value
            for key, value in stats.items()
            if key not in COMMIT_ACTIVITY_FIELDS
        }
        for url, stats in repositories.items()
        if isinstance(stats, dict)
    }


def _has_commit_activity(stats: dict[str, Any]) -> bool:
    return all(key in stats for key in COMMIT_ACTIVITY_FIELDS)


def _write_cache(cache_path: Path, cache: dict[str, dict[str, Any]]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as file:
        json.dump(
            {"schema_version": CACHE_SCHEMA_VERSION, "repositories": cache},
            file,
            indent=2,
            sort_keys=True,
        )
        file.write("\n")
