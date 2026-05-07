import re
from pathlib import Path


PRODUCTION_PATHS = [
    Path("assets"),
    Path("scripts"),
    Path("src"),
    Path("templates"),
]
SOURCE_SUFFIXES = {".css", ".html", ".j2", ".js", ".py", ".rb"}

RECORD_ID_PATTERN = re.compile(
    r"\b(?:organization|publication|position|degree|grant|software|package)_[0-9]+\b"
)


def test_production_code_does_not_hardcode_record_ids() -> None:
    offenders = []
    for root in PRODUCTION_PATHS:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            for line_number, line in enumerate(lines, 1):
                if RECORD_ID_PATTERN.search(line):
                    offenders.append(f"{path}:{line_number}: {line.strip()}")

    assert offenders == []
