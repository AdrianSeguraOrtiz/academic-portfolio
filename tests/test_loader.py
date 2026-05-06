from pathlib import Path

from academic_portfolio.loader import load_data


def test_load_data_reads_yaml_files() -> None:
    loaded_data = load_data(Path("data"))

    assert "profile.yaml" in loaded_data.documents
    assert "research/publications.yaml" in loaded_data.documents
    assert loaded_data.file_count > 0
