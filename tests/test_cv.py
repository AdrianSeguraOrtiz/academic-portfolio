from pathlib import Path

from academic_portfolio.cv import build_cv_view, generate_cv, load_cv_model
from academic_portfolio.loader import load_data
from academic_portfolio.resolver import PortfolioResolver


def test_build_cv_view_resolves_current_activity() -> None:
    model = load_cv_model(Path("cv_models/academic_full.toml"))
    resolver = PortfolioResolver(load_data(Path("data")))

    view = build_cv_view(model, resolver)

    assert [position["id"] for position in view["profile"]["current_positions"]] == [
        "position_05",
        "position_06",
    ]
    assert [stay["id"] for stay in view["profile"]["current_stays"]] == ["stay_02"]


def test_build_cv_view_resolves_publication_references() -> None:
    model = load_cv_model(Path("cv_models/academic_full.toml"))
    resolver = PortfolioResolver(load_data(Path("data")))

    view = build_cv_view(model, resolver)
    publication = next(
        item for item in view["publications"] if item["id"] == "publication_04"
    )

    assert [item["id"] for item in publication["resolved"]["software_project_ids"]] == [
        "software_10"
    ]
    assert [item["id"] for item in publication["resolved"]["grant_ids"]] == [
        "grant_01",
        "grant_02",
    ]
    assert [item["id"] for item in view["publication_groups"]["conference_papers"]] == [
        "publication_02"
    ]
    assert "publication_02" not in [
        item["id"] for item in view["publication_groups"]["journal_papers"]
    ]


def test_build_cv_view_resolves_research_stay_grants() -> None:
    model = load_cv_model(Path("cv_models/academic_full.toml"))
    resolver = PortfolioResolver(load_data(Path("data")))

    view = build_cv_view(model, resolver)
    stay = next(item for item in view["research_stays"] if item["id"] == "stay_01")

    assert [item["id"] for item in stay["resolved"]["grant_ids"]] == ["grant_02"]
    assert [item["id"] for item in stay["related_grants"]] == ["grant_02"]


def test_build_cv_view_adds_derived_honors_and_grants() -> None:
    model = load_cv_model(Path("cv_models/academic_full.toml"))
    resolver = PortfolioResolver(load_data(Path("data")))

    view = build_cv_view(model, resolver)
    degree = next(item for item in view["degrees"] if item["id"] == "degree_01")
    position = next(item for item in view["experience"] if item["id"] == "position_04")

    assert [item["id"] for item in degree["related_honors"]] == ["award_03", "award_02"]
    assert [item["id"] for item in position["related_grants"]] == ["grant_01"]


def test_generate_cv_writes_markdown(tmp_path: Path) -> None:
    output = generate_cv(output_dir=tmp_path)

    assert output.output_path == tmp_path / "academic_full.md"
    assert output.output_path.exists()
    assert "# Adrián Segura Ortiz" in output.content
    assert "## Publications" in output.content
    assert "### Journal Papers" in output.content
    assert "### Conference Papers" in output.content
    assert "Research areas:" in output.content
    assert "[Docker Hub](https://hub.docker.com/u/adriansegura99)" in output.content
    assert "[Universidad de Málaga](https://www.uma.es/)" in output.content
    assert "[PhD candidate - FPU Fellowship](#position_04)" in output.content
    assert "(#grant_02)" in output.content
    assert "#### External internship tutoring" in output.content
    assert "External extracurricular internship tutoring" in output.content
    assert "MOEBA-BIO" in output.content
    assert "undefined" not in output.content
    assert "null" not in output.content
