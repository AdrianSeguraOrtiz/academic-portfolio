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
            output_path=Path("build/cv/academic_sober_3p.pdf"),
            html_path=Path("build/cv/academic_sober_3p.html"),
            page_count=3,
            page_limit=3,
            fit_status="fits",
        )

    monkeypatch.setattr(cli_module, "generate_cv", fake_generate_cv)

    result = runner.invoke(app, ["cv", "generate", "--model", "academic_sober", "--pages", "3"])

    assert result.exit_code == 0
    assert seen_kwargs["page_limit"] == 3
    assert "Generated Academic Sober CV: build/cv/academic_sober_3p.pdf" in result.stdout
    assert "Intermediate HTML: build/cv/academic_sober_3p.html" in result.stdout
    assert "Pages: 3/3" in result.stdout
    assert "Fit status: fits (minimal)" in result.stdout


def test_cv_generate_omits_page_status_for_html(monkeypatch) -> None:
    runner = CliRunner()
    seen_kwargs = {}

    def fake_generate_cv(**kwargs):
        seen_kwargs.update(kwargs)
        return SimpleNamespace(
            model=SimpleNamespace(title="Academic Rich CV", layout={}),
            output_path=Path("build/cv/academic_rich.html"),
            html_path=Path("build/cv/academic_rich.html"),
            page_count=None,
            page_limit=None,
            fit_status="not_checked",
        )

    monkeypatch.setattr(cli_module, "generate_cv", fake_generate_cv)

    result = runner.invoke(app, ["cv", "generate", "--format", "html"])

    assert result.exit_code == 0
    assert seen_kwargs["page_limit"] is None
    assert "Generated Academic Rich CV: build/cv/academic_rich.html" in result.stdout
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
