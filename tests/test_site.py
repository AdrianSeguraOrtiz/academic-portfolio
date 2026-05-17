from pathlib import Path
import shutil
from typing import Any
from urllib.parse import urljoin

import pytest
import yaml

from academic_portfolio.github import github_repository_from_url
from academic_portfolio.loader import load_data
from academic_portfolio.resolver import PortfolioResolver
from academic_portfolio.site import build_site_view, generate_all_sites, generate_site
from academic_portfolio.site.collaborations import _collaboration_view


def _data_list(resolver: PortfolioResolver, path: str, key: str) -> list[dict[str, Any]]:
    return resolver.loaded_data.documents[path][key]


def _sum_numeric(items: list[dict[str, Any]], key: str) -> float:
    return sum(float(item.get(key) or 0) for item in items)


def _flatten_organization_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for node in nodes:
        flattened.append(node)
        flattened.extend(_flatten_organization_nodes(node.get("children", [])))
    return flattened


def test_collaboration_map_keeps_repeated_city_stays_as_separate_labels() -> None:
    collaborations = _collaboration_view(
        publications=[],
        research_stays=[
            {
                "id": "stay_a",
                "title": "First stay",
                "start_date": "2024-01",
                "end_date": "2024-02",
                "location": {
                    "city": "Lille",
                    "country": "France",
                    "coordinates": {"latitude": 50.6292, "longitude": 3.0573},
                },
                "resolved": {"organization_ids": []},
            },
            {
                "id": "stay_b",
                "title": "Second stay",
                "start_date": "2027-03",
                "end_date": "2027-05",
                "location": {
                    "city": "Lille",
                    "country": "France",
                    "coordinates": {"latitude": 50.6292, "longitude": 3.0573},
                },
                "resolved": {"organization_ids": []},
            },
        ],
    )

    assert collaborations["metrics"]["research_stays"] == 2
    assert collaborations["metrics"]["stay_cities"] == 1
    assert collaborations["metrics"]["stay_months"] == 5
    assert collaborations["map_data"]["stay_nodes"][0]["stays"] == [
        {"months": 2, "year": "2024", "label": "2 mo · 2024"},
        {"months": 3, "year": "2027", "label": "3 mo · 2027"},
    ]


def test_build_site_view_computes_core_metrics() -> None:
    resolver = PortfolioResolver(load_data(Path("data")))

    view = build_site_view(resolver)
    journal_papers = _data_list(resolver, "research/publications.yaml", "journal_papers")
    conference_papers = _data_list(resolver, "research/publications.yaml", "conference_papers")
    software_projects = _data_list(resolver, "research/software_projects.yaml", "projects")
    software_packages = _data_list(
        resolver,
        "research/software_packages.yaml",
        "software_packages",
    )
    research_projects = _data_list(resolver, "research/research_projects.yaml", "funded_projects")
    teaching_projects = _data_list(
        resolver,
        "activities/teaching/teaching_innovation_projects.yaml",
        "teaching_innovation_projects",
    )
    classes = _data_list(
        resolver,
        "activities/teaching/university_classes.yaml",
        "university_classes",
    )
    supervisions = _data_list(
        resolver,
        "activities/teaching/academic_supervision.yaml",
        "academic_supervision",
    )
    social_media = _data_list(
        resolver,
        "activities/dissemination/social_media.yaml",
        "social_media_items",
    )
    reviewing = _data_list(resolver, "research/reviewing.yaml", "reviewing")
    scientific_articles = _data_list(
        resolver,
        "activities/dissemination/scientific_dissemination_articles.yaml",
        "scientific_dissemination_articles",
    )
    presentations = _data_list(
        resolver,
        "activities/dissemination/presentations.yaml",
        "presentations",
    )
    press_items = _data_list(resolver, "activities/dissemination/press.yaml", "press_items")
    tv_media = _data_list(resolver, "activities/dissemination/tv_media.yaml", "tv_items")
    honors = _data_list(resolver, "career/honors.yaml", "honors")
    grants = _data_list(resolver, "career/grants.yaml", "grants")

    assert view["metrics"]["journal_papers"] == len(journal_papers)
    assert view["metrics"]["conference_papers"] == len(conference_papers)
    assert view["metrics"]["publications"] == len(journal_papers) + len(conference_papers)
    assert view["metrics"]["projects"] == len(research_projects) + len(teaching_projects)
    assert view["metrics"]["software_projects"] == len(software_projects)
    assert view["metrics"]["software_packages"] == len(software_packages)
    assert view["metrics"]["research_projects"] == len(research_projects)
    assert view["metrics"]["teaching_innovation_projects"] == len(teaching_projects)
    assert view["metrics"]["teaching_hours"] == round(_sum_numeric(classes, "workload_hours"))
    assert view["metrics"]["known_social_views"] == int(_sum_numeric(social_media, "views"))
    assert view["metrics"]["package_downloads"] == 0
    assert view["metrics"]["work_institutions"] == view["overview"]["experience"]["institution_count"]
    assert view["metrics"]["reviewed_manuscripts"] == int(
        _sum_numeric(reviewing, "manuscripts_reviewed")
    )
    assert view["overview"]["research"]["reviewed_manuscripts"] == view["metrics"][
        "reviewed_manuscripts"
    ]
    assert view["overview"]["internationalization"]["international_publications"] == view[
        "collaborations"
    ]["metrics"]["international_papers"]
    assert view["overview"]["internationalization"]["national_multicity_publications"] >= 0
    assert view["overview"]["education"]["degrees"][0].startswith("Bachelor")
    assert view["overview"]["education"]["degrees"][-1].startswith("Ph.D.")
    assert "from Universidad de Málaga" in view["overview"]["education"]["degrees"][0]
    assert [item["label"] for item in view["overview"]["experience"]["by_institution"]] == [
        "Universidad de Málaga"
    ]
    assert "Athena Research and Innovation Center" in view["overview"]["internationalization"][
        "stays_text"
    ]
    assert "ORKAD, belonging to CRIStAL, belonging to Université de Lille" in view[
        "overview"
    ]["internationalization"]["stays_text"]
    assert "covering Predoctoral Researcher (International Stay) at Université de Lille" in view[
        "overview"
    ]["recognition"]["grants_text"]
    assert "PhD candidate - FPU Fellowship at Universidad de Málaga" in view["overview"][
        "recognition"
    ]["grants_text"]
    assert view["overview"]["teaching"]["degree_programs"] == len(
        {item["degree"] for item in classes}
    )
    assert view["overview"]["teaching"]["teaching_innovation_projects"] == len(teaching_projects)
    assert "teaching innovation project" in view["overview"]["teaching"][
        "teaching_innovation_projects_phrase"
    ]
    assert sum(view["overview"]["teaching"]["supervision_counts"].values()) == len(supervisions)
    assert view["overview"]["dissemination"]["known_social_views"] == view["metrics"][
        "known_social_views"
    ]
    assert "honor" in view["overview"]["recognition"]["honors_phrase"]
    assert "grant" in view["overview"]["recognition"]["grants_phrase"]
    assert len(view["overview"]["recognition"]["honors"]) == len(honors)
    assert len(view["overview"]["recognition"]["grants"]) == len(grants)
    assert len(view["projects"]) == view["metrics"]["projects"]
    assert {project["participation_class"] for project in view["projects"]} == {"working"}
    assert view["publication_chart"]
    assert [item["year"] for item in view["publication_chart"]] == sorted(
        [item["year"] for item in view["publication_chart"]],
        reverse=True,
    )
    assert view["publication_groups"][0]["year"] == view["publication_chart"][0]["year"]
    assert view["collaborations"]["metrics"]["research_stays"] == len(
        _data_list(resolver, "career/research_stays.yaml", "stays")
    )
    assert view["collaborations"]["metrics"]["stay_months"] == sum(
        stay["months"]
        for node in view["collaborations"]["map_data"]["stay_nodes"]
        for stay in node["stays"]
    )
    assert view["collaborations"]["metrics"]["publication_cities"] >= 3
    assert view["collaborations"]["metrics"]["total_papers"] == view["metrics"]["publications"]
    assert view["collaborations"]["metrics"]["publication_countries"] >= 2
    assert view["collaborations"]["metrics"]["stay_cities"] == len(
        view["collaborations"]["map_data"]["stay_nodes"]
    )
    assert view["collaborations"]["metrics"]["stay_countries"] == len(
        {
            node["country"]
            for node in view["collaborations"]["map_data"]["stay_nodes"]
            if node.get("country")
        }
    )
    assert view["collaborations"]["publication_nodes"]
    stay_labels = {
        stay["label"]
        for node in view["collaborations"]["map_data"]["stay_nodes"]
        for stay in node["stays"]
    }
    assert all("mo ·" in label for label in stay_labels)
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
    assert view["career_details"]["items"]
    assert {filter_item["id"] for filter_item in view["career_details"]["filters"]} == {
        "education",
        "experience",
        "stay",
        "certification",
        "honor",
        "grant",
    }
    assert any(
        item["kind"] == "organization_group"
        and item["category"] == "experience"
        and item["title"] == "Khaos Research"
        and len(item["records"]) == 3
        for item in view["career_details"]["items"]
    )
    assert sum(row["hours"] for row in view["teaching_hours_chart"]["by_academic_year"]) == round(
        _sum_numeric(classes, "workload_hours"),
        1,
    )
    assert [row["label"] for row in view["teaching_hours_chart"]["by_academic_year"]] == sorted(
        {item["academic_year"] for item in classes}
    )
    assert view["teaching_hours_chart"]["by_degree"][0]["hours"] == max(
        row["hours"] for row in view["teaching_hours_chart"]["by_degree"]
    )
    assert len(view["teaching_timeline"]["events"]) == len(classes) + len(supervisions)
    organizations = resolver.loaded_data.documents["entities/organizations.yaml"]["organizations"]
    university_of_malaga = next(
        organization for organization in organizations if organization["id"] == "organization_01"
    )
    assert view["teaching_hours_chart"]["legend"][0]["label"] == university_of_malaga["abbreviation"]
    assert view["teaching_hours_chart"]["by_degree"][0]["segments"][0]["label"] == (
        university_of_malaga["abbreviation"]
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
    expected_dissemination_total = (
        len(scientific_articles)
        + len(presentations)
        + len(press_items)
        + len(social_media)
        + len(tv_media)
    )
    assert view["dissemination_hub"]["total"] == expected_dissemination_total
    assert len(view["dissemination_hub"]["items"]) == expected_dissemination_total
    category_counts = {
        category["id"]: category["count"] for category in view["dissemination_hub"]["categories"]
    }
    assert category_counts["articles"] == len(scientific_articles)
    assert category_counts["press"] == len(press_items)
    assert view["dissemination_hub"]["publication_groups"]
    publication_group_dates = [
        group["publication"]["publication_date"]
        for group in view["dissemination_hub"]["publication_groups"]
    ]
    assert publication_group_dates == sorted(publication_group_dates, reverse=True)
    assert view["organization_network"]["metrics"]["countries"] == len(
        view["organization_network"]["cards"]
    )
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
    assert round(publications_row["total"], 6) == view["metrics"]["publications"]
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
    spain = next(country for country in view["organization_network"]["cards"] if country["country"] == "Spain")
    malaga = next(city for city in spain["cities"] if city["city"] == "Málaga")
    uma = next(organization for organization in malaga["organizations"] if organization["id"] == "organization_01")
    itis = next(child for child in uma["children"] if child["id"] == "organization_06")
    cimes = next(child for child in uma["children"] if child["id"] == "organization_12")
    assert next(child for child in itis["children"] if child["id"] == "organization_03")
    assert next(child for child in cimes["children"] if child["id"] == "organization_02")
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
    assert view["metrics"]["package_downloads"] == 18_024
    assert view["overview"]["software"]["package_downloads_label"] == "18,024"


def test_generate_site_writes_index_and_assets(tmp_path: Path) -> None:
    output = generate_site(output_dir=tmp_path)

    assert output.language == "en"
    assert output.output_path == tmp_path / "en" / "index.html"
    assert output.output_path.exists()
    assert (tmp_path / "en" / "assets" / "site.css").exists()
    assert (tmp_path / "en" / "assets" / "ui.js").exists()
    assert (tmp_path / "en" / "assets" / "collaborations.js").exists()
    assert (tmp_path / "en" / "assets" / "publications.js").exists()
    assert (tmp_path / "en" / "assets" / "software-timeline.js").exists()
    assert (tmp_path / "en" / "assets" / "career-timeline.js").exists()
    assert (tmp_path / "en" / "assets" / "career-details.js").exists()
    assert (tmp_path / "en" / "assets" / "projects.js").exists()
    assert (tmp_path / "en" / "assets" / "teaching-timeline.js").exists()
    assert (tmp_path / "en" / "assets" / "dissemination.js").exists()
    assert (tmp_path / "en" / "assets" / "organizations.js").exists()
    assert (tmp_path / "en" / "assets" / "profile.jpg").exists()
    assert "Adrián Segura Ortiz" in output.content
    assert 'class="profile-photo"' in output.content
    assert "Download CV" in output.content
    assert 'href="downloads/academic_rich_en.pdf" download' in output.content
    assert 'href="downloads/academic_sober_en.pdf" download' in output.content
    assert "Portfolio Summary" in output.content
    assert "artificial intelligence applied" in output.content
    assert "Repository for the GENECI software ecosystem" in output.content
    assert "journal papers" in output.content
    assert "conference paper" in output.content
    assert "international collaboration" in output.content
    assert "national collaboration" in output.content
    assert "multi-city" not in output.content
    assert "GitHub metadata" not in output.content
    assert "Total publications" in output.content
    assert "Teaching hours" in output.content
    assert "Package downloads" in output.content
    assert "Known social views" in output.content
    assert "This academic trajectory has also been recognized" in output.content
    assert "Predoctoral grant (FPU)" in output.content
    assert "Destacad@s Awards 2021" in output.content
    assert "Research Stays and Publication Cities" in output.content
    assert "collaboration-map" in output.content
    assert "collaboration-map-data" in output.content
    assert "Publications by Year" in output.content
    assert "publication-carousel" in output.content
    assert "data-publication-carousel-prev" in output.content
    assert "data-publication-carousel-next" in output.content
    assert "assets/ui.js" in output.content
    assert "carousel-control publication-carousel-control previous" in output.content
    assert "data-publication-year-chart" in output.content
    assert "data-publication-year-group" in output.content
    assert "data-publication-slide" in output.content
    assert "repo-row" in output.content
    assert "data-repo-carousel" in output.content
    assert "data-software-carousel-track" in output.content
    assert "data-software-carousel-item" in output.content
    assert "Software Index" in output.content
    assert "Software Packages" in output.content
    assert "data-package-carousel" in output.content
    assert "Package: geneci" in output.content
    assert "Research Focus" in output.content
    assert "Current position" in output.content
    assert "Khaos Research" in output.content
    assert "Academic Trajectory" in output.content
    assert "career-timeline-data" in output.content
    assert "data-career-timeline" in output.content
    assert "data-career-detail-filters" in output.content
    assert "career-organization-card experience" in output.content
    assert "Associate Team Coordinator <- Associate Software Engineer" in output.content
    assert "Research and Teaching Innovation Projects" in output.content
    assert "project-role-legend" in output.content
    assert "data-project-carousel" in output.content
    assert "data-project-carousel-track" in output.content
    assert "data-project-meta-details" in output.content
    assert "project-card type-research role-working" in output.content
    assert "project-card type-teaching role-working" in output.content
    assert "Teaching innovation project" in output.content
    assert "PIE22-114" in output.content
    assert "Classes and Supervision" in output.content
    assert "teaching-chart-grid" in output.content
    assert "Classroom Hours by Academic Year" in output.content
    assert "Classroom Hours by Degree Programme" in output.content
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
    assert "data-dissemination-carousel" in output.content
    assert "data-dissemination-prev" in output.content
    assert "data-dissemination-next" in output.content
    assert "data-media-details" in output.content
    assert "media-card category-articles" in output.content
    assert "media-card category-presentations" in output.content
    assert "media-card category-press" in output.content
    assert "media-card category-social" in output.content
    assert "media-card category-tv" in output.content
    assert "data-dissemination-filters" in output.content
    assert "Organizations" in output.content
    assert "data-organization-tabs" in output.content
    assert "data-organization-tab" in output.content
    assert "organization-hierarchy-list" in output.content
    assert "organization-children" in output.content
    assert "Contained organizations" in output.content
    assert "organization-relationship-chart" not in output.content
    assert "relationship-country-track" not in output.content
    assert "static.cloudflareinsights.com/beacon.min.js" not in output.content
    assert "undefined" not in output.content
    assert "null" not in output.content
    assert "None" not in output.content


def test_generate_site_includes_cloudflare_analytics_when_configured(tmp_path: Path) -> None:
    output = generate_site(output_dir=tmp_path, cloudflare_analytics_token="test-token")

    assert "https://static.cloudflareinsights.com/beacon.min.js" in output.content
    assert """data-cf-beacon='{"token": "test-token"}'""" in output.content


def test_generate_all_sites_includes_cloudflare_analytics_when_configured(tmp_path: Path) -> None:
    output = generate_all_sites(output_dir=tmp_path, cloudflare_analytics_token="test-token")

    for site_output in output.outputs:
        assert "https://static.cloudflareinsights.com/beacon.min.js" in site_output.content
        assert """data-cf-beacon='{"token": "test-token"}'""" in site_output.content


def test_generate_site_accepts_explicit_spanish_language(tmp_path: Path) -> None:
    output = generate_site(output_dir=tmp_path, language="es")

    assert output.language == "es"
    assert output.output_path == tmp_path / "es" / "index.html"
    assert '<html lang="es">' in output.content
    assert (tmp_path / "es" / "assets" / "site.css").exists()
    assert "Resumen del portafolio" in output.content
    assert "Investigador en inteligencia artificial y bioinformática" in output.content
    assert "Repositorio del ecosistema software GENECI" in output.content
    assert "Publicaciones por año" in output.content
    assert "visualizaciones" in output.content
    assert "acciones en redes sociales" in output.content
    assert "acción en televisión" in output.content or "acciones en televisión" in output.content
    assert ", y 1 acción en televisión" not in output.content
    assert "Puesto actual" in output.content
    assert "Selector de idioma" in output.content
    assert "Descargar CV" in output.content
    assert 'href="downloads/academic_rich_es.pdf" download' in output.content
    assert 'href="downloads/academic_sober_es.pdf" download' in output.content
    assert "Publicaciones y detalles" in output.content
    assert "Current position" not in output.content
    assert "Publication details" not in output.content


def test_generate_all_sites_writes_bilingual_routes_and_root_redirect(tmp_path: Path) -> None:
    output = generate_all_sites(output_dir=tmp_path)
    outputs_by_language = {site_output.language: site_output for site_output in output.outputs}

    assert set(outputs_by_language) == {"en", "es"}
    assert outputs_by_language["en"].output_path == tmp_path / "en" / "index.html"
    assert outputs_by_language["es"].output_path == tmp_path / "es" / "index.html"
    assert output.redirect_path == tmp_path / "index.html"
    assert output.redirect_path.exists()
    assert (tmp_path / "en" / "assets" / "site.css").exists()
    assert (tmp_path / "es" / "assets" / "site.css").exists()

    redirect_content = output.redirect_path.read_text(encoding="utf-8")
    assert '<meta http-equiv="refresh" content="0; url=en/">' in redirect_content
    assert 'window.location.replace("en/" + window.location.search + window.location.hash)' in (
        redirect_content
    )

    english_content = outputs_by_language["en"].content
    spanish_content = outputs_by_language["es"].content
    assert '<html lang="en">' in english_content
    assert '<html lang="es">' in spanish_content
    assert 'href="../es/" hreflang="es"' in english_content
    assert 'href="../en/" hreflang="en"' in spanish_content
    assert (
        urljoin("https://adrianseguraortiz.github.io/academic-portfolio/", "en/")
        == "https://adrianseguraortiz.github.io/academic-portfolio/en/"
    )
    assert (
        urljoin("https://adrianseguraortiz.github.io/academic-portfolio/en/", "../es/")
        == "https://adrianseguraortiz.github.io/academic-portfolio/es/"
    )


def test_generate_site_renders_localized_yaml_maps(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    shutil.copytree(Path("data"), data_dir)
    software_path = data_dir / "research" / "software_projects.yaml"
    document = yaml.safe_load(software_path.read_text(encoding="utf-8"))
    document["projects"][0]["description"] = {
        "en": "English localized software description.",
        "es": "Descripción localizada del software.",
    }
    software_path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    english = generate_site(output_dir=tmp_path / "site-en", data_dir=data_dir, language="en")
    spanish = generate_site(output_dir=tmp_path / "site-es", data_dir=data_dir, language="es")

    assert "English localized software description." in english.content
    assert "Descripción localizada del software." in spanish.content
    assert "English localized software description." not in spanish.content


def test_generate_site_rejects_unsupported_language(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported language"):
        generate_site(output_dir=tmp_path, language="fr")


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
