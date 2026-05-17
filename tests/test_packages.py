from academic_portfolio import packages as packages_module


def test_pypi_stats_keep_registry_metadata_when_clickhouse_fails(monkeypatch) -> None:
    def fake_http_json(url: str):
        assert url == "https://pypi.org/pypi/geneci/json"
        return {
            "info": {
                "summary": "GENECI package summary.",
                "license": "MIT",
                "requires_python": ">=3.10",
                "version": "1.0.0",
                "classifiers": [],
            },
            "releases": {
                "1.0.0": [{"upload_time_iso_8601": "2024-01-01T00:00:00Z"}],
            },
        }

    def fail_clickhouse(_query: str):
        raise RuntimeError("ClickHouse unavailable")

    monkeypatch.setattr(packages_module, "_http_json", fake_http_json)
    monkeypatch.setattr(packages_module, "_clickhouse_scalar", fail_clickhouse)
    monkeypatch.setattr(packages_module, "_clickhouse_rows", fail_clickhouse)

    stats = packages_module._fetch_pypi_stats({"package_name": "geneci"})

    assert stats["ecosystem"] == "PyPI"
    assert stats["package_name"] == "geneci"
    assert stats["package_url"] == "https://pypi.org/project/geneci/"
    assert stats["summary"] == "GENECI package summary."
    assert stats["latest_version"] == "1.0.0"
    assert stats["release_count"] == 1
    assert stats["total_downloads"] is None
    assert stats["download_chart"] == []
    assert stats["downloads_by_version"] == []
    assert stats["downloads_by_country"] == []
    assert stats["download_stats_error"] == "ClickHouse unavailable"
