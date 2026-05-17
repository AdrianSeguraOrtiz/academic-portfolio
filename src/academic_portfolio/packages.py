from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree

CACHE_SCHEMA_VERSION = 2
CLICKHOUSE_URL = "https://sql-clickhouse.clickhouse.com/?user=demo"
MAVEN_BASE_URL = "https://repo.maven.apache.org/maven2"
VERSION_COLORS = [
    "#0f766e",
    "#8a3342",
    "#a66f21",
    "#3572a5",
    "#6d5cae",
    "#b65f2a",
    "#4b8b6f",
    "#7c5c2a",
    "#66706d",
    "#2f7f9f",
    "#9c4f67",
    "#6b7f2a",
]


@dataclass(frozen=True)
class PackageStatsResult:
    stats_by_id: dict[str, dict[str, Any]]
    errors: dict[str, str]


def collect_package_stats(
    packages: list[dict[str, Any]],
    cache_path: Path | str = "build/cache/software_packages.json",
) -> PackageStatsResult:
    cache = _load_cache(Path(cache_path))
    cached_stats = cache.get("stats_by_id", {}) if cache else {}
    stats_by_id: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}

    for package in packages:
        package_id = str(package["id"])
        try:
            stats_by_id[package_id] = _fetch_package_stats(package)
        except Exception as error:  # noqa: BLE001 - cache fallback should survive flaky public APIs.
            if package_id in cached_stats:
                stats_by_id[package_id] = cached_stats[package_id]
            errors[package_id] = str(error)

    _write_cache(Path(cache_path), stats_by_id)
    return PackageStatsResult(stats_by_id=stats_by_id, errors=errors)


def _fetch_package_stats(package: dict[str, Any]) -> dict[str, Any]:
    ecosystem = str(package.get("ecosystem", "")).lower()
    if ecosystem == "pypi":
        return _fetch_pypi_stats(package)
    if ecosystem == "maven":
        return _fetch_maven_stats(package)
    raise ValueError(f"Unsupported package ecosystem: {package.get('ecosystem')}")


def _fetch_pypi_stats(package: dict[str, Any]) -> dict[str, Any]:
    package_name = str(package["package_name"]).lower()
    metadata = _http_json(f"https://pypi.org/pypi/{quote(package_name)}/json")
    info = metadata.get("info", {})
    releases = _pypi_releases(metadata.get("releases", {}), package_name)
    clickhouse_errors: list[str] = []
    clickhouse_available = True

    def clickhouse_scalar(query: str) -> int | None:
        nonlocal clickhouse_available
        if not clickhouse_available:
            return None
        try:
            return _clickhouse_scalar(query)
        except (HTTPError, KeyError, OSError, RuntimeError, TimeoutError, URLError, ValueError) as error:
            clickhouse_available = False
            clickhouse_errors.append(str(error))
            return None

    def clickhouse_rows(query: str) -> list[dict[str, Any]]:
        nonlocal clickhouse_available
        if not clickhouse_available:
            return []
        try:
            return _clickhouse_rows(query)
        except (HTTPError, KeyError, OSError, RuntimeError, TimeoutError, URLError, ValueError) as error:
            clickhouse_available = False
            clickhouse_errors.append(str(error))
            return []

    total_downloads = clickhouse_scalar(
        f"""
        SELECT sum(count) AS downloads
        FROM pypi.pypi_downloads
        WHERE project = {_sql_string(package_name)}
        """
    )
    monthly_downloads = clickhouse_rows(
        f"""
        SELECT toStartOfMonth(date) AS month, sum(count) AS downloads
        FROM pypi.pypi_downloads_per_day
        WHERE project = {_sql_string(package_name)}
        GROUP BY month
        ORDER BY month
        FORMAT JSON
        """
    )
    downloads_by_version = clickhouse_rows(
        f"""
        SELECT version, sum(count) AS downloads
        FROM pypi.pypi_downloads_by_version
        WHERE project = {_sql_string(package_name)} AND version != ''
        GROUP BY version
        ORDER BY downloads DESC
        FORMAT JSON
        """
    )
    downloads_by_month_by_version = clickhouse_rows(
        f"""
        SELECT toStartOfMonth(date) AS month, version, sum(count) AS downloads
        FROM pypi.pypi_downloads_per_day_by_version
        WHERE project = {_sql_string(package_name)} AND version != ''
        GROUP BY month, version
        ORDER BY month, downloads DESC
        FORMAT JSON
        """
    )
    version_colors = _version_colors(downloads_by_version)

    return {
        "ecosystem": "PyPI",
        "package_name": package_name,
        "package_url": f"https://pypi.org/project/{package_name}/",
        "clickpy_url": f"https://clickpy.clickhouse.com/dashboard/{package_name}",
        "summary": info.get("summary"),
        "license": info.get("license") or _classifier_license(info.get("classifiers", [])),
        "requires_python": info.get("requires_python"),
        "latest_version": info.get("version"),
        "release_count": len(releases),
        "releases": releases,
        "total_downloads": total_downloads,
        "first_download_date": monthly_downloads[0]["month"] if monthly_downloads else None,
        "last_download_date": monthly_downloads[-1]["month"] if monthly_downloads else None,
        "monthly_downloads": _monthly_download_chart(monthly_downloads, downloads_by_month_by_version, version_colors),
        "download_chart": _monthly_download_chart(monthly_downloads, downloads_by_month_by_version, version_colors),
        "downloads_by_version": [
            {**item, "color": version_colors.get(str(item["version"]), VERSION_COLORS[-1])}
            for item in downloads_by_version
        ],
        "downloads_by_country": clickhouse_rows(
            f"""
            SELECT country_code, sum(count) AS downloads
            FROM pypi.pypi_downloads_per_day_by_version_by_country
            WHERE project = {_sql_string(package_name)} AND country_code != ''
            GROUP BY country_code
            ORDER BY downloads DESC
            FORMAT JSON
            """
        ),
        "downloads_by_python": clickhouse_rows(
            f"""
            SELECT python_minor, sum(count) AS downloads
            FROM pypi.pypi_downloads_per_day_by_version_by_python
            WHERE project = {_sql_string(package_name)} AND python_minor != ''
            GROUP BY python_minor
            ORDER BY downloads DESC
            LIMIT 7
            FORMAT JSON
            """
        ),
        "downloads_by_system": clickhouse_rows(
            f"""
            SELECT system, sum(count) AS downloads
            FROM pypi.pypi_downloads_per_day_by_version_by_system
            WHERE project = {_sql_string(package_name)} AND system != ''
            GROUP BY system
            ORDER BY downloads DESC
            FORMAT JSON
            """
        ),
        "downloads_by_file_type": clickhouse_rows(
            f"""
            SELECT type, sum(count) AS downloads
            FROM pypi.pypi_downloads_per_day_by_version_by_file_type
            WHERE project = {_sql_string(package_name)}
            GROUP BY type
            ORDER BY downloads DESC
            FORMAT JSON
            """
        ),
        "download_stats_error": "; ".join(dict.fromkeys(clickhouse_errors)) or None,
    }


def _version_colors(downloads_by_version: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(item["version"]): VERSION_COLORS[index % len(VERSION_COLORS)]
        for index, item in enumerate(downloads_by_version)
    }


def _monthly_download_chart(
    monthly_downloads: list[dict[str, Any]],
    downloads_by_month_by_version: list[dict[str, Any]],
    version_colors: dict[str, str],
) -> list[dict[str, Any]]:
    monthly_versions: dict[str, list[dict[str, Any]]] = {}
    for row in downloads_by_month_by_version:
        month = str(row["month"])
        version = str(row["version"])
        monthly_versions.setdefault(month, []).append(
            {
                "version": version,
                "downloads": int(row["downloads"]),
                "color": version_colors.get(version, VERSION_COLORS[-1]),
            }
        )

    chart = []
    for row in monthly_downloads:
        month = str(row["month"])
        total = int(row["downloads"])
        segments = sorted(
            monthly_versions.get(month, []),
            key=lambda segment: segment["downloads"],
            reverse=True,
        )
        chart.append(
            {
                "month": month,
                "label": _month_short_label(month),
                "downloads": total,
                "segments": [
                    {
                        **segment,
                        "share": round((segment["downloads"] / total) * 100, 3) if total else 0,
                    }
                    for segment in segments
                ],
            }
        )
    return chart


def _month_short_label(value: str) -> str:
    try:
        parsed = datetime.strptime(value[:10], "%Y-%m-%d")
    except ValueError:
        return value[:7]
    return parsed.strftime("%b %Y")


def _fetch_maven_stats(package: dict[str, Any]) -> dict[str, Any]:
    group_id = str(package["group_id"])
    artifact_id = str(package["artifact_id"])
    group_path = group_id.replace(".", "/")
    artifact_base_url = f"{MAVEN_BASE_URL}/{group_path}/{artifact_id}"
    metadata = _http_text(f"{artifact_base_url}/maven-metadata.xml")
    metadata_root = ElementTree.fromstring(metadata)
    versioning = metadata_root.find("versioning")
    if versioning is None:
        raise ValueError(f"Maven metadata without versioning for {group_id}:{artifact_id}")

    latest_version = _xml_text(versioning, "release") or _xml_text(versioning, "latest")
    versions = [
        version.text
        for version in versioning.findall("versions/version")
        if version.text
    ]
    pom_root = _maven_pom(f"{artifact_base_url}/{latest_version}/{artifact_id}-{latest_version}.pom")
    artifact_files = _maven_artifact_files(artifact_base_url, artifact_id, latest_version)

    return {
        "ecosystem": "Maven",
        "group_id": group_id,
        "artifact_id": artifact_id,
        "coordinate": f"{group_id}:{artifact_id}",
        "package_url": artifact_base_url,
        "mvnrepository_url": f"https://mvnrepository.com/artifact/{group_id}/{artifact_id}",
        "latest_version": latest_version,
        "release_count": len(versions),
        "versions": versions,
        "last_updated": _maven_timestamp(_xml_text(versioning, "lastUpdated")),
        "name": _pom_text(pom_root, "name"),
        "summary": _pom_text(pom_root, "description"),
        "project_url": _pom_text(pom_root, "url"),
        "license": _pom_license(pom_root),
        "java_release": _pom_property(pom_root, "maven.compiler.release"),
        "dependency_count": len(_pom_dependencies(pom_root)),
        "dependencies": _pom_dependencies(pom_root)[:8],
        "artifact_files": artifact_files,
    }


def _pypi_releases(release_map: dict[str, Any], package_name: str) -> list[dict[str, Any]]:
    releases = []
    for version, files in release_map.items():
        upload_times = [
            file.get("upload_time_iso_8601") or file.get("upload_time")
            for file in files
            if file.get("upload_time_iso_8601") or file.get("upload_time")
        ]
        releases.append(
            {
                "version": version,
                "url": f"https://pypi.org/project/{package_name}/{version}/",
                "upload_time": min(upload_times) if upload_times else None,
            }
        )
    return sorted(releases, key=lambda release: _version_key(release["version"]))


def _maven_artifact_files(
    artifact_base_url: str,
    artifact_id: str,
    latest_version: str | None,
) -> list[dict[str, Any]]:
    if not latest_version:
        return []

    listing = _http_text(f"{artifact_base_url}/{latest_version}/")
    pattern = re.compile(
        rf'href="(?P<name>{re.escape(artifact_id)}-{re.escape(latest_version)}[^"]+)"[^>]*>'
        rf"(?P=name)</a>\s+(?P<date>\d{{4}}-\d{{2}}-\d{{2}}\s+\d{{2}}:\d{{2}})\s+"
        rf"(?P<size>\d+)"
    )
    files = []
    for match in pattern.finditer(listing):
        name = match.group("name")
        if any(name.endswith(suffix) for suffix in (".asc", ".md5", ".sha1", ".sha256", ".sha512")):
            continue
        files.append(
            {
                "name": name,
                "url": f"{artifact_base_url}/{latest_version}/{name}",
                "published_at": match.group("date"),
                "size_bytes": int(match.group("size")),
                "kind": _maven_file_kind(name),
            }
        )
    return files


def _maven_pom(url: str) -> ElementTree.Element:
    return ElementTree.fromstring(_http_text(url))


def _pom_text(root: ElementTree.Element, tag: str) -> str | None:
    value = root.findtext(f"m:{tag}", namespaces=_maven_namespaces())
    return value.strip() if value else None


def _pom_property(root: ElementTree.Element, name: str) -> str | None:
    value = root.findtext(f"m:properties/m:{name}", namespaces=_maven_namespaces())
    return value.strip() if value else None


def _pom_license(root: ElementTree.Element) -> str | None:
    return root.findtext("m:licenses/m:license/m:name", namespaces=_maven_namespaces())


def _pom_dependencies(root: ElementTree.Element) -> list[dict[str, str | None]]:
    dependencies = []
    for dependency in root.findall("m:dependencies/m:dependency", namespaces=_maven_namespaces()):
        dependencies.append(
            {
                "group_id": dependency.findtext("m:groupId", namespaces=_maven_namespaces()),
                "artifact_id": dependency.findtext("m:artifactId", namespaces=_maven_namespaces()),
                "version": dependency.findtext("m:version", namespaces=_maven_namespaces()),
                "scope": dependency.findtext("m:scope", namespaces=_maven_namespaces()),
            }
        )
    return dependencies


def _maven_namespaces() -> dict[str, str]:
    return {"m": "http://maven.apache.org/POM/4.0.0"}


def _maven_file_kind(filename: str) -> str:
    if filename.endswith("-jar-with-dependencies.jar"):
        return "Fat JAR"
    if filename.endswith("-sources.jar"):
        return "Sources"
    if filename.endswith("-javadoc.jar"):
        return "Javadoc"
    if filename.endswith(".jar"):
        return "JAR"
    if filename.endswith(".pom"):
        return "POM"
    return "Artifact"


def _maven_timestamp(value: str | None) -> str | None:
    if not value or len(value) != 14:
        return value
    parsed = datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    return parsed.date().isoformat()


def _xml_text(root: ElementTree.Element, tag: str) -> str | None:
    value = root.findtext(tag)
    return value.strip() if value else None


def _clickhouse_scalar(query: str) -> int:
    rows = _clickhouse_rows(f"{query} FORMAT JSON")
    if not rows:
        return 0
    value = next(iter(rows[0].values()))
    return int(value or 0)


def _clickhouse_rows(query: str) -> list[dict[str, Any]]:
    response = _http_json(CLICKHOUSE_URL, data=query.strip().encode("utf-8"))
    rows = response.get("data", [])
    return [_normalize_clickhouse_row(row) for row in rows]


def _normalize_clickhouse_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {}
    for key, value in row.items():
        if key == "downloads":
            normalized[key] = int(value or 0)
        else:
            normalized[key] = value
    return normalized


def _http_json(url: str, data: bytes | None = None) -> dict[str, Any]:
    return json.loads(_http_text(url, data=data))


def _http_text(url: str, data: bytes | None = None) -> str:
    request = Request(
        url,
        data=data,
        headers={
            "Accept": "application/json,text/xml,text/html,*/*",
            "User-Agent": "academic-portfolio/0.1",
        },
        method="POST" if data is not None else "GET",
    )
    try:
        with urlopen(request, timeout=25) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"Failed to fetch {url}: {error}") from error


def _sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _classifier_license(classifiers: list[str]) -> str | None:
    for classifier in classifiers:
        prefix = "License :: OSI Approved :: "
        if classifier.startswith(prefix):
            return classifier.removeprefix(prefix)
    return None


def _version_key(version: str) -> list[int | str]:
    parts: list[int | str] = []
    for part in re.split(r"[.\-]", version):
        parts.append(int(part) if part.isdigit() else part)
    return parts


def _load_cache(cache_path: Path) -> dict[str, Any]:
    if not cache_path.exists():
        return {}

    data = json.loads(cache_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != CACHE_SCHEMA_VERSION:
        return {}
    return data


def _write_cache(cache_path: Path, stats_by_id: dict[str, dict[str, Any]]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "schema_version": CACHE_SCHEMA_VERSION,
                "fetched_at": datetime.now(UTC).isoformat(),
                "stats_by_id": stats_by_id,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
