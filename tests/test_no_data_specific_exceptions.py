import re
from pathlib import Path


PRODUCTION_PATHS = [
    Path("assets"),
    Path("scripts"),
    Path("src"),
    Path("templates"),
]
SITE_VISUALIZATION_PATHS = [
    Path("assets/site"),
    Path("src/academic_portfolio/site"),
    Path("templates/site"),
]
SOURCE_SUFFIXES = {".css", ".html", ".j2", ".js", ".py", ".rb"}

RECORD_ID_PATTERN = re.compile(
    r"\b(?:organization|publication|position|degree|grant|software|package)_[0-9]+\b"
)
CALENDAR_YEAR_LITERAL_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")


def _source_files(roots: list[Path]) -> list[Path]:
    return [
        path
        for root in roots
        for path in root.rglob("*")
        if path.is_file() and path.suffix in SOURCE_SUFFIXES
    ]


def test_production_code_does_not_hardcode_record_ids() -> None:
    offenders = []
    for path in _source_files(PRODUCTION_PATHS):
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, 1):
            if RECORD_ID_PATTERN.search(line):
                offenders.append(f"{path}:{line_number}: {line.strip()}")

    assert offenders == []


def test_site_visualizations_do_not_hardcode_calendar_years() -> None:
    offenders = []
    for path in _source_files(SITE_VISUALIZATION_PATHS):
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, 1):
            if CALENDAR_YEAR_LITERAL_PATTERN.search(line):
                offenders.append(f"{path}:{line_number}: {line.strip()}")

    assert offenders == []
