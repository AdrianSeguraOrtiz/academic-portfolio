.PHONY: install validate-data data-summary data-resolve cv site test lint

PYTHON ?= python3
VENV ?= .venv
MODEL ?= academic_full
FORMAT ?= md
SITE_ARGS ?=

install:
	@if command -v uv >/dev/null 2>&1; then \
		uv sync --dev; \
	else \
		$(PYTHON) -m venv $(VENV); \
		$(VENV)/bin/python -m pip install --upgrade pip; \
		$(VENV)/bin/python -m pip install -e ".[dev]"; \
	fi

validate-data:
	ruby scripts/validate_data.rb

data-summary:
	@if command -v uv >/dev/null 2>&1; then \
		uv run portfolio data summary; \
	else \
		$(VENV)/bin/portfolio data summary; \
	fi

data-resolve:
	@if command -v uv >/dev/null 2>&1; then \
		uv run portfolio data resolve $(ID); \
	else \
		$(VENV)/bin/portfolio data resolve $(ID); \
	fi

cv:
	@if command -v uv >/dev/null 2>&1; then \
		uv run portfolio cv generate --model $(MODEL) --format $(FORMAT); \
	else \
		$(VENV)/bin/portfolio cv generate --model $(MODEL) --format $(FORMAT); \
	fi

site:
	@if command -v uv >/dev/null 2>&1; then \
		uv run portfolio site generate $(SITE_ARGS); \
	else \
		$(VENV)/bin/portfolio site generate $(SITE_ARGS); \
	fi

test:
	@if command -v uv >/dev/null 2>&1; then \
		uv run pytest; \
	else \
		$(VENV)/bin/python -m pytest; \
	fi

lint:
	@if command -v uv >/dev/null 2>&1; then \
		uv run ruff check .; \
	else \
		$(VENV)/bin/python -m ruff check .; \
	fi
