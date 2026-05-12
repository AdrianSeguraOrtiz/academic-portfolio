from __future__ import annotations

from pathlib import Path

import pytest

from academic_portfolio.cv import generate_cv
from academic_portfolio.site import generate_site


CANONICAL_PUBLICATION_TITLE = (
    "GENECI: A novel evolutionary machine learning consensus-based approach for the "
    "inference of gene regulatory networks"
)


@pytest.mark.parametrize(
    ("language", "expected_labels", "unexpected_labels"),
    [
        (
            "en",
            ("Academic Portfolio", "Portfolio Summary", "Current position"),
            ("Portafolio académico", "Resumen del portafolio", "Puesto actual"),
        ),
        (
            "es",
            ("Portafolio académico", "Resumen del portafolio", "Puesto actual"),
            ("Academic Portfolio", "Portfolio Summary", "Current position"),
        ),
    ],
)
def test_site_generation_has_language_specific_labels(
    tmp_path: Path,
    language: str,
    expected_labels: tuple[str, ...],
    unexpected_labels: tuple[str, ...],
) -> None:
    output = generate_site(output_dir=tmp_path, language=language)

    assert output.language == language
    assert output.output_path == tmp_path / language / "index.html"
    assert f'<html lang="{language}">' in output.content
    assert all(label in output.content for label in expected_labels)
    assert all(label not in output.content for label in unexpected_labels)


@pytest.mark.parametrize(
    ("model", "language", "expected_labels", "unexpected_labels"),
    [
        (
            "academic_rich",
            "en",
            ("Academic Portfolio", "Portfolio Summary", "Journal paper"),
            ("Portafolio académico", "Resumen del portafolio", "Artículo de revista"),
        ),
        (
            "academic_rich",
            "es",
            ("Portafolio académico", "Resumen del portafolio", "Artículo de revista"),
            ("Academic Portfolio", "Portfolio Summary", "Journal paper"),
        ),
        (
            "academic_sober",
            "en",
            ("Academic Curriculum Vitae", "Summary", "Institution:"),
            ("Curriculum vitae académico", "Resumen", "Institución:"),
        ),
        (
            "academic_sober",
            "es",
            ("Curriculum vitae académico", "Resumen", "Institución:"),
            ("Academic Curriculum Vitae", "Summary", "Institution:"),
        ),
    ],
)
def test_cv_generation_has_language_specific_labels(
    tmp_path: Path,
    model: str,
    language: str,
    expected_labels: tuple[str, ...],
    unexpected_labels: tuple[str, ...],
) -> None:
    output = generate_cv(
        model=model,
        output_dir=tmp_path,
        output_format="html",
        language=language,
    )

    assert output.model.language == language
    assert output.output_path == tmp_path / f"{model}_{language}.html"
    assert f'<html lang="{language}">' in output.content
    assert all(label in output.content for label in expected_labels)
    assert all(label not in output.content for label in unexpected_labels)


@pytest.mark.parametrize("language", ["en", "es"])
def test_canonical_publication_titles_are_preserved_across_languages(
    tmp_path: Path,
    language: str,
) -> None:
    site_output = generate_site(output_dir=tmp_path / "site", language=language)
    cv_output = generate_cv(
        output_dir=tmp_path / "cv",
        output_format="html",
        language=language,
    )

    assert CANONICAL_PUBLICATION_TITLE in site_output.content
    assert CANONICAL_PUBLICATION_TITLE in cv_output.content


@pytest.mark.parametrize("language", ["en", "es"])
@pytest.mark.parametrize("page_limit", [3, 4])
def test_page_limited_cv_names_include_page_limit_and_language(
    tmp_path: Path,
    page_limit: int,
    language: str,
) -> None:
    output = generate_cv(
        model="academic_sober",
        output_dir=tmp_path,
        output_format="html",
        page_limit=page_limit,
        language=language,
    )

    expected_path = tmp_path / f"academic_sober_{page_limit}p_{language}.html"
    assert output.model.language == language
    assert output.model.page_limit == page_limit
    assert output.output_path == expected_path
    assert output.html_path == expected_path
