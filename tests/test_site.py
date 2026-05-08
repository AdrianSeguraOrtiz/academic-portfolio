from pathlib import Path
from typing import Any

from academic_portfolio.github import github_repository_from_url
from academic_portfolio.loader import load_data
from academic_portfolio.resolver import PortfolioResolver
from academic_portfolio.site import build_site_view, generate_site


def _flatten_organization_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for node in nodes:
        flattened.append(node)
        flattened.extend(_flatten_organization_nodes(node.get("children", [])))
    return flattened


def test_build_site_view_computes_core_metrics() -> None:
    resolver = PortfolioResolver(load_data(Path("data")))

    view = build_site_view(resolver)

    assert view["metrics"]["journal_papers"] == 5
    assert view["metrics"]["conference_papers"] == 1
    assert view["metrics"]["publications"] == 6
    assert view["metrics"]["projects"] == 5
    assert view["metrics"]["software_projects"] == 12
    assert view["metrics"]["software_packages"] == 2
    assert view["metrics"]["research_projects"] == 4
    assert view["metrics"]["teaching_innovation_projects"] == 1
    assert len(view["projects"]) == 5
    assert {project["participation_class"] for project in view["projects"]} == {"working"}
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
    assert view["career_timeline"]["items"]
    assert view["career_timeline"]["markers"]
    assert any(
        item["type"] == "experience" and item["grants"]
        for item in view["career_timeline"]["items"]
    )
    assert any(
        item["type"] == "stay" and item["grants"]
        for item in view["career_timeline"]["items"]
    )
    assert any(
        item["type"] == "education" and item["grants"]
        for item in view["career_timeline"]["items"]
    )
    assert len(view["teaching_timeline"]["events"]) == 10
    organizations = resolver.loaded_data.documents["entities/organizations.yaml"]["organizations"]
    university_of_malaga = next(
        organization for organization in organizations if organization["id"] == "organization_01"
    )
    assert view["teaching_timeline"]["legend"][0]["label"] == university_of_malaga["abbreviation"]
    assert {event["type"] for event in view["teaching_timeline"]["events"]} == {
        "class",
        "supervision",
    }
    assert {event["side"] for event in view["teaching_timeline"]["events"]} == {
        "left",
        "right",
    }
    assert any(event["lane"] > 0 for event in view["teaching_timeline"]["events"])
    assert view["dissemination_hub"]["total"] == 38
    assert len(view["dissemination_hub"]["items"]) == 38
    assert view["dissemination_hub"]["categories"][0]["count"] == 2
    assert view["dissemination_hub"]["categories"][2]["count"] == 16
    assert view["dissemination_hub"]["publication_groups"]
    publication_group_dates = [
        group["publication"]["publication_date"]
        for group in view["dissemination_hub"]["publication_groups"]
    ]
    assert publication_group_dates == sorted(publication_group_dates, reverse=True)
    assert view["organization_network"]["metrics"]["countries"] == 3
    assert [row["id"] for row in view["organization_network"]["rows"]] == [
        "education",
        "experience",
        "stays",
        "publications",
        "teaching",
    ]
    publications_row = next(
        row for row in view["organization_network"]["rows"] if row["id"] == "publications"
    )
    assert round(publications_row["total"], 6) == 6
    organization_nodes = _flatten_organization_nodes(
        [
            node
            for row in view["organization_network"]["rows"]
            for country in row["countries"]
            for node in country["nodes"]
        ]
    )
    organization_ids = {node["id"] for node in organization_nodes}
    assert {"organization_01", "organization_03", "organization_04", "organization_11"}.issubset(
        organization_ids
    )
    assert {"organization_13", "organization_14", "organization_15"}.isdisjoint(
        organization_ids
    )
    khaos = next(node for node in organization_nodes if node["id"] == "organization_03")
    assert khaos["path_label"] == "UMA > ITIS > Khaos Research"
    assert khaos["value"] > 0
    assert view["software_timeline"]["rows"] == []
    assert view["publications"][0]["publication_kind"] in {"journal", "conference"}


def test_build_site_view_uses_github_stats_for_software_visuals() -> None:
    resolver = PortfolioResolver(load_data(Path("data")))
    geneci_url = "https://github.com/AdrianSeguraOrtiz/GENECI"
    psycotreat_url = "https://github.com/AdrianSeguraOrtiz/PsycoTreat"

    view = build_site_view(
        resolver,
        github_stats_by_url={
            psycotreat_url: {
                "repository": "AdrianSeguraOrtiz/PsycoTreat",
                "html_url": psycotreat_url,
                "stargazers_count": 0,
                "forks_count": 0,
                "open_issues_count": 0,
                "language": "HTML",
                "license": "MIT",
                "created_at": "2021-03-01T09:00:00Z",
                "updated_at": "2023-03-01T09:00:00Z",
                "pushed_at": "2023-03-01T09:00:00Z",
                "archived": False,
                "languages": {"HTML": 20_000},
                "commits_count": 4,
                "first_commit_at": "2021-03-01T09:00:00Z",
                "last_commit_at": "2023-03-01T09:00:00Z",
                "commit_months": [
                    {"month": "2021-03", "count": 2},
                    {"month": "2023-03", "count": 2},
                ],
            },
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
    assert view["software_timeline"]["rows"][0]["project"]["name"] == "GENECI"
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
    assert (tmp_path / "assets" / "software-timeline.js").exists()
    assert (tmp_path / "assets" / "career-timeline.js").exists()
    assert (tmp_path / "assets" / "teaching-timeline.js").exists()
    assert (tmp_path / "assets" / "dissemination.js").exists()
    assert (tmp_path / "assets" / "profile.jpg").exists()
    assert "Adrián Segura Ortiz" in output.content
    assert 'class="profile-photo"' in output.content
    assert "Journal papers" in output.content
    assert "Conference papers" in output.content
    assert "Research Stays and Publication Cities" in output.content
    assert "collaboration-map" in output.content
    assert "collaboration-map-data" in output.content
    assert "Publications by Year" in output.content
    assert "repo-row" in output.content
    assert "Software Index" in output.content
    assert "Software Packages" in output.content
    assert "Package: geneci" in output.content
    assert "Research Focus" in output.content
    assert "Current position" in output.content
    assert "Khaos Research" in output.content
    assert "Education, Experience, Stays, Honors, and Grants" in output.content
    assert "career-timeline-data" in output.content
    assert "data-career-timeline" in output.content
    assert "Research and Teaching Innovation Projects" in output.content
    assert "project-role-legend" in output.content
    assert "project-card type-research role-working" in output.content
    assert "project-card type-teaching role-working" in output.content
    assert "Teaching innovation project" in output.content
    assert "PIE22-114" in output.content
    assert "Classes and Supervision" in output.content
    assert "teaching-timeline-stage" in output.content
    assert "teaching-timeline-item type-class" in output.content
    assert "teaching-timeline-item type-supervision" in output.content
    assert "teaching-timeline-connector" in output.content
    assert "Lenguajes y Ciencias de la Computación" in output.content
    assert "teaching-organization-legend" in output.content
    assert "Dissemination and Media" in output.content
    assert "dissemination-summary" in output.content
    assert "channel-mix" in output.content
    assert "publication-impact" in output.content
    assert "media-card category-articles" in output.content
    assert "media-card category-presentations" in output.content
    assert "media-card category-press" in output.content
    assert "media-card category-social" in output.content
    assert "media-card category-tv" in output.content
    assert "data-dissemination-filters" in output.content
    assert "Organizations" in output.content
    assert "organization-relationship-chart" in output.content
    assert "relationship-country-track" in output.content
    assert "relationship-node depth-2" in output.content
    assert "Certificates-only organizations are omitted" in output.content
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
