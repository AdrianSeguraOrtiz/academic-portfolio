from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from academic_portfolio.i18n import localized_value
from academic_portfolio.loader import LoadedData, load_data


REFERENCE_PREFIXES = {
    "organization_ids": "organization_",
    "parent_organization_id": "organization_",
    "degree_ids": "degree_",
    "position_ids": "position_",
    "origin_position_ids": "position_",
    "current_position_ids": "position_",
    "stay_ids": "stay_",
    "current_stay_ids": "stay_",
    "publication_ids": "publication_",
    "publication_id": "publication_",
    "software_project_ids": "software_",
    "software_project_id": "software_",
    "software_package_ids": "package_",
    "research_project_ids": "research_project_",
    "award_ids": "award_",
    "grant_ids": "grant_",
    "certification_ids": "certification_",
    "course_ids": "course_",
}


@dataclass(frozen=True)
class RecordPointer:
    """Location and value for a record with a stable ID."""

    record_id: str
    file_path: str
    group: str
    index: int
    record: dict[str, Any]

    @property
    def label(self) -> str:
        return record_label(self.record)


class DuplicateRecordIdError(ValueError):
    """Raised when two records share the same stable ID."""


class UnknownRecordIdError(KeyError):
    """Raised when a record ID cannot be resolved."""


class InvalidReferenceFieldError(ValueError):
    """Raised when a reference field does not contain the expected shape."""


def record_label(record: Mapping[str, Any]) -> str:
    """Return a compact human-readable label for a portfolio record."""

    for field in ("title", "name", "journal", "full_name"):
        value = record.get(field)
        if value:
            return str(localized_value(value))
    return str(record.get("id", "unknown"))


class PortfolioResolver:
    """Resolve portfolio records and relationships by stable ID."""

    def __init__(self, loaded_data: LoadedData) -> None:
        self.loaded_data = loaded_data
        self.records_by_id = self._build_record_index()

    @classmethod
    def from_data_dir(cls, data_dir: Path | str = "data") -> PortfolioResolver:
        return cls(load_data(data_dir))

    def pointer(self, record_id: str) -> RecordPointer:
        try:
            return self.records_by_id[record_id]
        except KeyError as error:
            raise UnknownRecordIdError(record_id) from error

    def resolve(self, record_id: str) -> dict[str, Any]:
        return self.pointer(record_id).record

    def resolve_many(self, record_ids: Sequence[str]) -> list[dict[str, Any]]:
        return [self.resolve(record_id) for record_id in record_ids]

    def records_in_group(self, file_path: str, group: str) -> list[dict[str, Any]]:
        document = self.loaded_data.documents[file_path]
        values = document[group] if isinstance(document, dict) else []
        return list(values) if isinstance(values, list) else []

    def reference_ids_for(self, record: Mapping[str, Any]) -> dict[str, list[str]]:
        references: dict[str, list[str]] = {}
        for field, value in record.items():
            if field not in REFERENCE_PREFIXES:
                continue

            if field.endswith("_ids"):
                if not isinstance(value, list):
                    raise InvalidReferenceFieldError(f"{field} must be a list")
                references[field] = [str(item) for item in value]
            elif value is None:
                references[field] = []
            else:
                references[field] = [str(value)]

        return references

    def references_for(self, record: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
        return {
            field: self.resolve_many(record_ids)
            for field, record_ids in self.reference_ids_for(record).items()
        }

    def reference_pointers_for(self, record: Mapping[str, Any]) -> dict[str, list[RecordPointer]]:
        return {
            field: [self.pointer(record_id) for record_id in record_ids]
            for field, record_ids in self.reference_ids_for(record).items()
        }

    def _build_record_index(self) -> dict[str, RecordPointer]:
        records_by_id: dict[str, RecordPointer] = {}

        for file_path, document in self.loaded_data.documents.items():
            if not isinstance(document, dict):
                continue

            for group, values in document.items():
                if not isinstance(values, list):
                    continue

                for index, record in enumerate(values):
                    if not isinstance(record, dict):
                        continue

                    record_id = record.get("id")
                    if not record_id:
                        continue

                    record_id = str(record_id)
                    if record_id in records_by_id:
                        existing = records_by_id[record_id]
                        raise DuplicateRecordIdError(
                            f"{record_id} appears in both {existing.file_path} and {file_path}"
                        )

                    records_by_id[record_id] = RecordPointer(
                        record_id=record_id,
                        file_path=file_path,
                        group=group,
                        index=index,
                        record=record,
                    )

        return records_by_id
