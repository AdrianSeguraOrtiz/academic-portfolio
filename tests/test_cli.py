from pathlib import Path
import subprocess
from types import SimpleNamespace

from typer.testing import CliRunner

import academic_portfolio.cli as cli_module
from academic_portfolio.cli import app


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_cv_generate_prints_pdf_page_status(monkeypatch) -> None:
    runner = CliRunner()
    seen_kwargs = {}

    def fake_generate_cv(**kwargs):
        seen_kwargs.update(kwargs)
        return SimpleNamespace(
            model=SimpleNamespace(
                title="Academic Sober CV",
                layout={"compression_stage": "minimal"},
            ),
            output_path=Path("build/cv/academic_sober_3p_es.pdf"),
            html_path=Path("build/cv/academic_sober_3p_es.html"),
            page_count=3,
            page_limit=3,
            fit_status="fits",
        )

    monkeypatch.setattr(cli_module, "generate_cv", fake_generate_cv)

    result = runner.invoke(
        app,
        ["cv", "generate", "--model", "academic_sober", "--lang", "es", "--pages", "3"],
    )

    assert result.exit_code == 0
    assert seen_kwargs["page_limit"] == 3
    assert seen_kwargs["language"] == "es"
    assert "Generated Academic Sober CV: build/cv/academic_sober_3p_es.pdf" in result.stdout
    assert "Intermediate HTML: build/cv/academic_sober_3p_es.html" in result.stdout
    assert "Pages: 3/3" in result.stdout
    assert "Fit status: fits (minimal)" in result.stdout


def test_cv_generate_omits_page_status_for_html(monkeypatch) -> None:
    runner = CliRunner()
    seen_kwargs = {}

    def fake_generate_cv(**kwargs):
        seen_kwargs.update(kwargs)
        return SimpleNamespace(
            model=SimpleNamespace(title="Academic Rich CV", layout={}),
            output_path=Path("build/cv/academic_rich_en.html"),
            html_path=Path("build/cv/academic_rich_en.html"),
            page_count=None,
            page_limit=None,
            fit_status="not_checked",
        )

    monkeypatch.setattr(cli_module, "generate_cv", fake_generate_cv)

    result = runner.invoke(app, ["cv", "generate", "--format", "html"])

    assert result.exit_code == 0
    assert seen_kwargs["page_limit"] is None
    assert seen_kwargs["language"] == "en"
    assert "Generated Academic Rich CV: build/cv/academic_rich_en.html" in result.stdout
    assert "Pages:" not in result.stdout
    assert "Fit status:" not in result.stdout


def test_make_cv_all_declares_definitive_outputs() -> None:
    result = subprocess.run(
        ["make", "--dry-run", "--no-print-directory", "cv-all"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "make cv MODEL=academic_rich FORMAT=pdf PAGES=" in result.stdout
    assert "make cv MODEL=academic_sober FORMAT=pdf PAGES=" in result.stdout
    assert "make cv MODEL=academic_sober FORMAT=pdf PAGES=4" in result.stdout
    assert "make cv MODEL=academic_sober FORMAT=pdf PAGES=3" in result.stdout


def test_site_generate_passes_language_to_generator(monkeypatch) -> None:
    runner = CliRunner()
    seen_kwargs = {}

    def fake_generate_site(**kwargs):
        seen_kwargs.update(kwargs)
        return SimpleNamespace(
            output_path=Path("build/site/es/index.html"),
            content="",
            asset_paths=[],
            language="es",
        )

    monkeypatch.setattr(cli_module, "generate_site", fake_generate_site)

    result = runner.invoke(app, ["site", "generate", "--lang", "es"])

    assert result.exit_code == 0
    assert seen_kwargs["language"] == "es"
    assert "Generated site: build/site/es/index.html" in result.stdout


def test_site_generate_all_uses_bilingual_generator(monkeypatch) -> None:
    runner = CliRunner()
    seen_kwargs = {}

    def fake_generate_all_sites(**kwargs):
        seen_kwargs.update(kwargs)
        return SimpleNamespace(
            outputs=[
                SimpleNamespace(language="en", output_path=Path("build/site/en/index.html")),
                SimpleNamespace(language="es", output_path=Path("build/site/es/index.html")),
            ],
            redirect_path=Path("build/site/index.html"),
        )

    monkeypatch.setattr(cli_module, "generate_all_sites", fake_generate_all_sites)

    result = runner.invoke(app, ["site", "generate-all", "--no-refresh-github"])

    assert result.exit_code == 0
    assert seen_kwargs["refresh_github"] is False
    assert "Generated site en: build/site/en/index.html" in result.stdout
    assert "Generated site es: build/site/es/index.html" in result.stdout
    assert "Generated site redirect: build/site/index.html" in result.stdout


def test_make_targets_pass_language_arguments() -> None:
    default_cv_result = subprocess.run(
        ["make", "--dry-run", "--no-print-directory", "cv"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    cv_result = subprocess.run(
        ["make", "--dry-run", "--no-print-directory", "cv", "LANG=es"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    site_result = subprocess.run(
        ["make", "--dry-run", "--no-print-directory", "site", "PORTFOLIO_LANG=es"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    site_all_result = subprocess.run(
        ["make", "--dry-run", "--no-print-directory", "site-all"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    cv_all_lang_result = subprocess.run(
        ["make", "--dry-run", "--no-print-directory", "cv-all-lang"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    cv_site_downloads_result = subprocess.run(
        ["make", "--dry-run", "--no-print-directory", "cv-site-downloads"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--lang en" in default_cv_result.stdout
    assert "--lang es" in cv_result.stdout
    assert "--lang es" in site_result.stdout
    assert "site generate-all" in site_all_result.stdout
    assert "make cv-all PORTFOLIO_LANG=en" in cv_all_lang_result.stdout
    assert "make cv-all PORTFOLIO_LANG=es" in cv_all_lang_result.stdout
    assert "academic_rich_en.pdf" in cv_site_downloads_result.stdout
    assert "academic_sober_en.pdf" in cv_site_downloads_result.stdout
    assert "academic_rich_es.pdf" in cv_site_downloads_result.stdout
    assert "academic_sober_es.pdf" in cv_site_downloads_result.stdout


def test_pages_workflow_builds_bilingual_site() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "deploy-site.yml").read_text(
        encoding="utf-8",
    )

    assert "make site-all" in workflow
    assert "make cv-site-downloads" in workflow
    assert "path: build/site" in workflow
