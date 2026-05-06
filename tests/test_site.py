from pathlib import Path

from academic_portfolio.github import github_repository_from_url
from academic_portfolio.loader import load_data
from academic_portfolio.resolver import PortfolioResolver
from academic_portfolio.site import build_site_view, generate_site


def test_build_site_view_computes_core_metrics() -> None:
    resolver = PortfolioResolver(load_data(Path("data")))

    view = build_site_view(resolver)

    assert view["metrics"]["journal_papers"] == 5
    assert view["metrics"]["conference_papers"] == 1
    assert view["metrics"]["publications"] == 6
    assert view["metrics"]["software_projects"] == 12
    assert view["metrics"]["software_packages"] == 2
    assert view["publication_chart"]
    assert view["collaborations"]["metrics"]["research_stays"] == 2
    assert view["collaborations"]["metrics"]["stay_months"] == 6
    assert view["collaborations"]["metrics"]["publication_cities"] >= 3
    assert view["collaborations"]["metrics"]["total_papers"] == 6
    assert view["collaborations"]["metrics"]["publication_countries"] >= 2
    assert view["collaborations"]["metrics"]["stay_cities"] == 2
    assert view["collaborations"]["metrics"]["stay_countries"] == 2
    assert view["collaborations"]["publication_nodes"]
    assert any(node["city"] == "Málaga" for node in view["collaborations"]["publication_nodes"])
    assert view["software_timeline"]["rows"] == []
    assert view["publications"][0]["publication_kind"] in {"journal", "conference"}


def test_build_site_view_uses_github_stats_for_software_visuals() -> None:
    resolver = PortfolioResolver(load_data(Path("data")))
    geneci_url = "https://github.com/AdrianSeguraOrtiz/GENECI"

    view = build_site_view(
        resolver,
        github_stats_by_url={
            geneci_url: {
                "repository": "AdrianSeguraOrtiz/GENECI",
                "html_url": geneci_url,
                "stargazers_count": 49,
                "forks_count": 3,
                "open_issues_count": 2,
                "language": "Java",
                "license": "MIT",
                "created_at": "2022-01-19T09:08:29Z",
                "updated_at": "2026-04-24T03:43:28Z",
                "pushed_at": "2026-04-24T11:53:59Z",
                "archived": False,
                "languages": {"Java": 360_000, "Python": 140_000},
                "commits_count": 296,
                "first_commit_at": "2022-01-19T09:10:00Z",
                "last_commit_at": "2026-04-24T11:53:59Z",
                "commit_months": [
                    {"month": "2022-01", "count": 12},
                    {"month": "2026-04", "count": 4},
                ],
            }
        },
    )

    geneci = next(project for project in view["software_projects"] if project["name"] == "GENECI")
    assert geneci["github"]["stargazers_count"] == 49
    assert view["software_github"]["total_stars"] == 49
    assert view["software_language_chart"][0]["name"] == "Java"
    assert view["software_timeline"]["rows"][0]["months"][0]["count"] == 12


def test_build_site_view_uses_package_stats_for_software_packages() -> None:
    resolver = PortfolioResolver(load_data(Path("data")))

    view = build_site_view(
        resolver,
        package_stats_by_id={
            "package_01": {
                "ecosystem": "PyPI",
                "package_name": "geneci",
                "package_url": "https://pypi.org/project/geneci/",
                "clickpy_url": "https://clickpy.clickhouse.com/dashboard/geneci",
                "summary": "GENECI package.",
                "requires_python": ">=3.10",
                "latest_version": "4.0.1.2",
                "release_count": 6,
                "total_downloads": 18_024,
                "monthly_downloads": [{"month": "2026-04-01", "downloads": 293}],
                "downloads_by_version": [{"version": "4.0.1.2", "downloads": 934}],
                "downloads_by_country": [{"country_code": "US", "downloads": 7350}],
            }
        },
    )

    geneci = next(package for package in view["software_packages"] if package["id"] == "package_01")
    assert geneci["package_stats"]["latest_version"] == "4.0.1.2"
    assert geneci["package_stats"]["total_downloads"] == 18_024


def test_generate_site_writes_index_and_assets(tmp_path: Path) -> None:
    output = generate_site(output_dir=tmp_path)

    assert output.output_path == tmp_path / "index.html"
    assert output.output_path.exists()
    assert (tmp_path / "assets" / "site.css").exists()
    assert (tmp_path / "assets" / "collaborations.js").exists()
    assert "Adrián Segura Ortiz" in output.content
    assert "Journal papers" in output.content
    assert "Conference papers" in output.content
    assert "Research Stays and Publication Cities" in output.content
    assert "collaboration-map" in output.content
    assert "collaboration-map-data" in output.content
    assert "Publications by Year" in output.content
    assert "Recent Work" not in output.content
    assert "Bibliographic data" not in output.content
    assert "Total authors" not in output.content
    assert "Corresponding author" not in output.content
    assert "repo-row" in output.content
    assert "Software Index" in output.content
    assert "Software Packages" in output.content
    assert "Package: geneci" in output.content
    assert "Commit Activity" not in output.content
    assert "Research Focus" in output.content
    assert "Current position" in output.content
    assert "Khaos Research" in output.content
    assert "Education, Experience, Stays, Honors, and Grants" in output.content
    assert "Dissemination and Media" in output.content
    assert "Organizations" in output.content
    assert "undefined" not in output.content
    assert "null" not in output.content
    assert "None" not in output.content


def test_github_repository_from_url() -> None:
    assert (
        github_repository_from_url("https://github.com/AdrianSeguraOrtiz/GENECI")
        == "AdrianSeguraOrtiz/GENECI"
    )
    assert (
        github_repository_from_url("https://github.com/AdrianSeguraOrtiz/GENECI.git")
        == "AdrianSeguraOrtiz/GENECI"
    )
    assert github_repository_from_url("https://example.com/AdrianSeguraOrtiz/GENECI") is None
