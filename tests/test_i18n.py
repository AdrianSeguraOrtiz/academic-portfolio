from __future__ import annotations

from pathlib import Path

import pytest

from academic_portfolio.i18n import (
    SUPPORTED_LANGUAGES,
    format_date_range,
    format_duration,
    format_number,
    format_unit,
    is_localized_mapping,
    load_locale,
    load_translator,
    localized_value,
    missing_translation_keys,
)
from academic_portfolio.render import create_environment, record_name


def test_locale_files_load_with_expected_language_codes() -> None:
    loaded_languages = [load_locale(language).language for language in SUPPORTED_LANGUAGES]

    assert loaded_languages == ["en", "es"]


def test_translator_resolves_interpolated_messages_and_plural_forms() -> None:
    english = load_translator("en")
    spanish = load_translator("es")

    assert english.t("labels.date") == "Date"
    assert spanish.t("labels.date") == "Fecha"
    assert english.t("summary.baseline_interpolation_example", count=6) == "6 publications"
    assert spanish.t("summary.baseline_interpolation_example", count=6) == "6 publicaciones"
    assert english.plural("units.paper", 1) == "1 paper"
    assert english.plural("units.paper", 2) == "2 papers"
    assert spanish.plural("units.paper", 1) == "1 artículo"
    assert spanish.plural("units.paper", 2) == "2 artículos"


def test_translator_falls_back_to_english_when_key_is_missing(tmp_path: Path) -> None:
    (tmp_path / "en.yaml").write_text(
        """
language:
  code: en
labels:
  date: Date
  journal: Journal
units:
  paper:
    one: "{count} paper"
    other: "{count} papers"
lists:
  conjunction: and
""",
        encoding="utf-8",
    )
    (tmp_path / "es.yaml").write_text(
        """
language:
  code: es
labels:
  date: Fecha
lists:
  conjunction: y
""",
        encoding="utf-8",
    )
    translator = load_translator("es", locale_dir=tmp_path)

    assert translator.t("labels.date") == "Fecha"
    assert translator.t("labels.journal") == "Journal"
    assert translator.plural("units.paper", 2) == "2 papers"
    assert translator.t("labels.missing") == "labels.missing"


def test_missing_translation_keys_are_reported_as_dotted_paths(tmp_path: Path) -> None:
    (tmp_path / "en.yaml").write_text(
        """
language:
  code: en
  name: English
labels:
  date: Date
  journal: Journal
units:
  paper:
    one: "{count} paper"
    other: "{count} papers"
lists:
  conjunction: and
""",
        encoding="utf-8",
    )
    (tmp_path / "es.yaml").write_text(
        """
language:
  code: es
labels:
  date: Fecha
units:
  paper:
    one: "{count} artículo"
lists:
  conjunction: y
""",
        encoding="utf-8",
    )

    assert missing_translation_keys("es", locale_dir=tmp_path) == [
        "labels.journal",
        "language.name",
        "units.paper.other",
    ]


def test_locale_files_keep_translation_key_parity() -> None:
    assert missing_translation_keys("es") == []
    assert missing_translation_keys("en", reference_language="es") == []


def test_translator_formats_lists_by_language() -> None:
    english = load_translator("en")
    spanish = load_translator("es")

    assert english.format_list(["A", "B"]) == "A and B"
    assert english.format_list(["A", "B", "C"]) == "A, B, and C"
    assert spanish.format_list(["A", "B"]) == "A y B"
    assert spanish.format_list(["A", "B", "C"]) == "A, B y C"


def test_translator_formats_shared_dates_durations_and_units() -> None:
    english = load_translator("en")
    spanish = load_translator("es")

    assert english.date_range("2024-01", "") == "2024-01 - Present"
    assert spanish.date_range("2024-01", "") == "2024-01 - Actualidad"
    assert format_date_range("2024-01", "2024-03", english) == "2024-01 - 2024-03"
    assert format_duration(25, english) == "2 years and 1 month"
    assert format_duration(25, spanish) == "2 años y 1 mes"
    assert format_duration(0, spanish) == "0 meses"
    assert format_number(68300, english) == "68,300"
    assert format_number(68300, spanish) == "68.300"
    assert format_number(180.5, spanish) == "180,5"
    assert format_unit("paper", 2, spanish) == "2 artículos"
    assert format_unit("paper", 0.5, english, display_count="0.5") == "0.5 papers"


def test_localized_value_supports_scalar_and_localized_maps() -> None:
    assert localized_value("Canonical", "es") == "Canonical"
    assert localized_value({"en": "English", "es": "Español"}, "es") == "Español"
    assert localized_value({"en": "English"}, "es") == "English"
    assert localized_value({"name": "Structural map"}, "es") == {"name": "Structural map"}
    assert localized_value({"fr": "Francais"}, "es") == {"fr": "Francais"}
    assert is_localized_mapping({"en": "English", "es": "Español"})
    assert not is_localized_mapping({"fr": "Francais"})
    assert not is_localized_mapping({"name": "Structural map"})


def test_record_name_uses_localized_display_values() -> None:
    translator = load_translator("es")

    assert record_name({"title": {"en": "English title", "es": "Título español"}}, translator) == (
        "Título español"
    )


def test_jinja_environment_exposes_i18n_helpers(tmp_path: Path) -> None:
    (tmp_path / "template.html.j2").write_text(
        """
{{ t("labels.date") }}
{{ plural("units.paper", 2) }}
{{ "2024-01" | date_range("") }}
{{ 25 | duration }}
{{ 2 | unit("paper") }}
{{ ["A", "B", "C"] | format_list }}
{{ {"en": "English", "es": "Español"} | localized }}
{{ {"en": "Finalized English", "es": "Finalizado español"} }}
""",
        encoding="utf-8",
    )
    environment = create_environment(tmp_path, load_translator("es"))

    output = environment.get_template("template.html.j2").render()

    assert "Fecha" in output
    assert "2 artículos" in output
    assert "2024-01 - Actualidad" in output
    assert "2 años y 1 mes" in output
    assert "A, B y C" in output
    assert "Español" in output
    assert "Finalizado español" in output


def test_unsupported_locale_fails_clearly() -> None:
    with pytest.raises(ValueError, match="Unsupported language"):
        load_locale("fr")
