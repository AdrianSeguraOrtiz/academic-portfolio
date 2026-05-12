from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from academic_portfolio.cv import generate_cv
from academic_portfolio.site import generate_site


SITE_ENGLISH_BASELINE_LABELS = (
    '<html lang="en">',
    'aria-label="Primary navigation"',
    "Profile",
    "Overview",
    "Collaborations",
    "Publications",
    "Software",
    "Career",
    "Projects",
    "Teaching",
    "Dissemination",
    "Organizations",
    "Portfolio Summary",
    "Research Stays and Publication Cities",
    "Publications by Year",
    "Software Projects",
    "Academic Trajectory",
    "Research and Teaching Innovation Projects",
    "Classes and Supervision",
    "Dissemination and Media",
    "Total publications",
    "Teaching hours",
    "Package downloads",
    "Known social views",
)

RICH_CV_ENGLISH_BASELINE_LABELS = (
    '<html lang="en">',
    "Portfolio Summary",
    "Research Stays and Publication Cities",
    "Publications",
    "Software",
    "Academic Trajectory",
    "Research and Teaching Innovation Projects",
    "Classes and Supervision",
    "Dissemination and Media",
    "Organizations",
    "Journal paper",
    "Conference paper",
    "Organizations:",
    "Research stays:",
    "Software:",
)

SOBER_CV_ENGLISH_BASELINE_LABELS = (
    '<html lang="en">',
    "Academic Curriculum Vitae",
    "Summary",
    "Education",
    "Experience",
    "Research Stays",
    "Publications",
    "Research Projects",
    "Honors",
    "Grants",
    "Certifications",
    "Teaching",
    "Software",
    "Dissemination",
    "Reviewing",
    "Date:",
    "Institution:",
    "Authors:",
    "Journal:",
    "Conference:",
    "Organizations:",
)


def test_site_default_output_uses_english_i18n_baseline(tmp_path: Path) -> None:
    output = generate_site(output_dir=tmp_path)

    missing = [label for label in SITE_ENGLISH_BASELINE_LABELS if label not in output.content]

    assert missing == []


@pytest.mark.parametrize(
    ("model", "labels"),
    (
        ("academic_rich", RICH_CV_ENGLISH_BASELINE_LABELS),
        ("academic_sober", SOBER_CV_ENGLISH_BASELINE_LABELS),
    ),
)
def test_cv_default_output_uses_english_i18n_baseline(
    tmp_path: Path,
    model: str,
    labels: tuple[str, ...],
) -> None:
    output = generate_cv(model=model, output_dir=tmp_path, output_format="html")

    assert output.model.language == "en"
    missing = [label for label in labels if label not in output.content]

    assert missing == []


def test_generated_artifacts_remain_gitignored() -> None:
    if not Path(".git").exists():
        pytest.skip("Git metadata is required to check ignored generated artifacts.")

    generated_artifacts = [
        "build/site/en/index.html",
        "build/site/en/assets/site.css",
        "build/cv/academic_rich_en.pdf",
        "build/cv/academic_rich_en.html",
        "build/cv/academic_sober_en.pdf",
        "build/cv/academic_sober_4p_en.pdf",
        "build/cv/assets/common.css",
        "build/cache/github_repositories.json",
        "build/cache/software_packages.json",
    ]
    result = subprocess.run(
        ["git", "check-ignore", *generated_artifacts],
        check=False,
        capture_output=True,
        text=True,
    )

    ignored = set(result.stdout.splitlines())

    assert result.returncode == 0
    assert ignored == set(generated_artifacts)
