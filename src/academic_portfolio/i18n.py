from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment
import yaml


DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("en", "es")


@dataclass(frozen=True)
class LocaleCatalog:
    language: str
    messages: dict[str, Any]


@dataclass(frozen=True)
class Translator:
    language: str
    catalog: LocaleCatalog
    fallback_catalog: LocaleCatalog

    def t(self, key: str, **values: Any) -> str:
        message = _lookup_message(self.catalog.messages, key)
        if message is None and self.language != self.fallback_catalog.language:
            message = _lookup_message(self.fallback_catalog.messages, key)
        if message is None:
            return key
        if isinstance(message, Mapping):
            return key
        return _interpolate(str(message), values)

    def plural(self, key: str, count: int | float, **values: Any) -> str:
        plural_key = "one" if count == 1 else "other"
        message = _lookup_message(self.catalog.messages, f"{key}.{plural_key}")
        if message is None and self.language != self.fallback_catalog.language:
            message = _lookup_message(self.fallback_catalog.messages, f"{key}.{plural_key}")
        if message is None:
            return self.t(key, count=count, **values)
        display_count = values.pop("display_count", count)
        interpolation_values = {"count": display_count, **values}
        return _interpolate(str(message), interpolation_values)

    def unit(self, unit_key: str, count: int | float, **values: Any) -> str:
        return self.plural(f"units.{unit_key}", count, **values)

    def date_range(self, start: Any, end: Any) -> str:
        start_text = _compact(start)
        end_text = _compact(end) or self.t("labels.present")
        if start_text:
            return f"{start_text} - {end_text}"
        return end_text if end else ""

    def duration(self, months: int | float) -> str:
        total_months = max(int(months), 0)
        years, remaining_months = divmod(total_months, 12)
        parts = []
        if years:
            parts.append(self.unit("year", years))
        if remaining_months:
            parts.append(self.unit("month", remaining_months))
        return self.format_list(parts) if parts else self.unit("month", 0)

    def number(self, value: Any) -> str:
        return format_number(value, self)

    def format_list(self, values: Sequence[Any] | None) -> str:
        items = [str(value) for value in values or [] if value not in (None, "")]
        if not items:
            return ""
        if len(items) == 1:
            return items[0]

        conjunction = self.t("lists.conjunction")
        if len(items) == 2:
            return f"{items[0]} {conjunction} {items[1]}"

        if self.language == "en":
            return f"{', '.join(items[:-1])}, {conjunction} {items[-1]}"
        return f"{', '.join(items[:-1])} {conjunction} {items[-1]}"

    def localized(self, value: Any) -> Any:
        return localized_value(value, self.language, self.fallback_catalog.language)


def load_locale(language: str, locale_dir: Path | str = "locales") -> LocaleCatalog:
    return _load_locale_cached(language, str(Path(locale_dir)))


@lru_cache(maxsize=None)
def _load_locale_cached(language: str, locale_dir: str) -> LocaleCatalog:
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {language}")

    path = Path(locale_dir) / f"{language}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Locale file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        messages = yaml.safe_load(handle) or {}

    if not isinstance(messages, dict):
        raise ValueError(f"Locale file must contain a mapping: {path}")

    declared_language = str(messages.get("language", {}).get("code", language))
    if declared_language != language:
        raise ValueError(
            f"Locale file {path} declares language {declared_language!r}, expected {language!r}"
        )

    return LocaleCatalog(language=language, messages=messages)


def load_translator(
    language: str = DEFAULT_LANGUAGE,
    locale_dir: Path | str = "locales",
    fallback_language: str = DEFAULT_LANGUAGE,
) -> Translator:
    catalog = load_locale(language, locale_dir)
    fallback_catalog = catalog
    if fallback_language != language:
        fallback_catalog = load_locale(fallback_language, locale_dir)
    return Translator(language=language, catalog=catalog, fallback_catalog=fallback_catalog)


def missing_translation_keys(
    language: str,
    reference_language: str = DEFAULT_LANGUAGE,
    locale_dir: Path | str = "locales",
) -> list[str]:
    catalog = load_locale(language, locale_dir)
    reference_catalog = load_locale(reference_language, locale_dir)

    return sorted(
        key
        for key in _leaf_paths(reference_catalog.messages)
        if _lookup_message(catalog.messages, key) is None
    )


def configure_jinja_i18n(environment: Environment, translator: Translator | None = None) -> None:
    active_translator = translator or load_translator()
    environment.globals["t"] = active_translator.t
    environment.globals["plural"] = active_translator.plural
    environment.globals["unit"] = active_translator.unit
    environment.globals["duration"] = active_translator.duration
    environment.globals["format_list"] = active_translator.format_list
    environment.globals["localized"] = active_translator.localized
    environment.filters["unit"] = (
        lambda count, unit_key, **values: active_translator.unit(unit_key, count, **values)
    )
    environment.filters["duration"] = active_translator.duration
    environment.filters["number"] = active_translator.number
    environment.filters["localized"] = active_translator.localized
    environment.filters["format_list"] = active_translator.format_list


def is_localized_mapping(value: Any) -> bool:
    if not isinstance(value, Mapping) or not value:
        return False

    keys = {str(key) for key in value}
    return keys.issubset(set(SUPPORTED_LANGUAGES))


def localized_value(
    value: Any,
    language: str = DEFAULT_LANGUAGE,
    fallback_language: str = DEFAULT_LANGUAGE,
) -> Any:
    if not is_localized_mapping(value):
        return value

    if language in value and value[language] not in (None, ""):
        return value[language]
    if fallback_language in value and value[fallback_language] not in (None, ""):
        return value[fallback_language]

    for candidate_value in value.values():
        if candidate_value not in (None, ""):
            return candidate_value
    return ""


def resolve_localized_values(
    value: Any,
    translator: Translator,
) -> Any:
    localized = translator.localized(value)
    if localized is not value:
        return localized

    if isinstance(value, Mapping):
        return {
            key: resolve_localized_values(item, translator)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [resolve_localized_values(item, translator) for item in value]
    if isinstance(value, tuple):
        return tuple(resolve_localized_values(item, translator) for item in value)
    return value


def format_date_range(start: Any, end: Any, translator: Translator | None = None) -> str:
    return (translator or load_translator()).date_range(start, end)


def format_duration(months: int | float, translator: Translator | None = None) -> str:
    return (translator or load_translator()).duration(months)


def format_number(value: Any, translator: Translator | None = None) -> str:
    active_translator = translator or load_translator()
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return str(value)

    if numeric_value.is_integer():
        formatted = f"{int(numeric_value):,}"
    else:
        formatted = f"{numeric_value:,.1f}".rstrip("0").rstrip(".")

    if active_translator.language == "es":
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted


def format_unit(
    unit_key: str,
    count: int | float,
    translator: Translator | None = None,
    **values: Any,
) -> str:
    return (translator or load_translator()).unit(unit_key, count, **values)


def _lookup_message(messages: Mapping[str, Any], key: str) -> Any:
    current: Any = messages
    for part in key.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _leaf_paths(value: Any, prefix: str = "") -> set[str]:
    if not isinstance(value, Mapping):
        return {prefix} if prefix else set()

    paths: set[str] = set()
    for key, item in value.items():
        child_prefix = f"{prefix}.{key}" if prefix else str(key)
        paths.update(_leaf_paths(item, child_prefix))
    return paths


def _interpolate(template: str, values: Mapping[str, Any]) -> str:
    if not values:
        return template
    return template.format_map(_SafeFormatMapping(values))


class _SafeFormatMapping(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _compact(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
