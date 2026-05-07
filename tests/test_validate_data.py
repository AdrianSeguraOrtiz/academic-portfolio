from collections.abc import Callable
from pathlib import Path
import shutil
import subprocess
from typing import Any

import yaml


def _run_validator_with_mutation(
    tmp_path: Path,
    mutation: Callable[[Path], None],
) -> subprocess.CompletedProcess[str]:
    data_dir = tmp_path / "data"
    shutil.copytree(Path("data"), data_dir)
    mutation(data_dir)

    return subprocess.run(
        ["ruby", "scripts/validate_data.rb", str(data_dir)],
        check=False,
        capture_output=True,
        text=True,
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_yaml(path: Path, document: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def test_validate_data_rejects_disallowed_relationship_fields(tmp_path: Path) -> None:
    def add_relationship_to_software_project(data_dir: Path) -> None:
        path = data_dir / "research" / "software_projects.yaml"
        document = _load_yaml(path)
        for project in document["projects"]:
            project["publication_ids"] = []
        _write_yaml(path, document)

    result = _run_validator_with_mutation(tmp_path, add_relationship_to_software_project)

    assert result.returncode == 1
    assert (
        "research/software_projects.yaml: projects does not allow relationship fields"
        in result.stderr
    )
    assert "publication_ids" in result.stderr


def test_validate_data_rejects_broken_parent_organization_references(tmp_path: Path) -> None:
    def break_parent_reference(data_dir: Path) -> None:
        path = data_dir / "entities" / "organizations.yaml"
        document = _load_yaml(path)
        document["organizations"][0]["parent_organization_id"] = "organization_99"
        _write_yaml(path, document)

    result = _run_validator_with_mutation(tmp_path, break_parent_reference)

    assert result.returncode == 1
    assert "Unresolved refs: organization_99" in result.stderr


def test_validate_data_rejects_self_references(tmp_path: Path) -> None:
    def add_self_reference(data_dir: Path) -> None:
        path = data_dir / "entities" / "organizations.yaml"
        document = _load_yaml(path)
        record_id = document["organizations"][0]["id"]
        document["organizations"][0]["parent_organization_id"] = record_id
        _write_yaml(path, document)

    result = _run_validator_with_mutation(tmp_path, add_self_reference)

    assert result.returncode == 1
    assert "should not reference itself" in result.stderr


def test_validate_data_rejects_unsorted_dated_lists(tmp_path: Path) -> None:
    def break_date_order(data_dir: Path) -> None:
        path = data_dir / "career" / "experience.yaml"
        document = _load_yaml(path)
        document["positions"][0]["start_date"] = "2999-01-01"
        _write_yaml(path, document)

    result = _run_validator_with_mutation(tmp_path, break_date_order)

    assert result.returncode == 1
    assert (
        "career/experience.yaml: positions is not sorted ascending by start_date"
        in result.stderr
    )
