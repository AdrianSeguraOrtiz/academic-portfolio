.PHONY: install install-playwright validate-data data-summary data-resolve cv cv-pdf cv-html cv-all cv-check clean-cv site clean-site test lint

PYTHON ?= python3
VENV ?= .venv
MODEL ?= academic_rich
FORMAT ?= pdf
PAGES ?=
SITE_ARGS ?=
PLAYWRIGHT_INSTALL_ARGS ?= chromium
CV_PAGE_ARGS = $(if $(PAGES),--pages $(PAGES),)

install:
	@if command -v uv >/dev/null 2>&1; then \
		uv sync --dev; \
	else \
		$(PYTHON) -m venv $(VENV); \
		$(VENV)/bin/python -m pip install --upgrade pip; \
		$(VENV)/bin/python -m pip install -e ".[dev]"; \
	fi

install-playwright:
	@if command -v uv >/dev/null 2>&1; then \
		uv run playwright install $(PLAYWRIGHT_INSTALL_ARGS); \
	else \
		$(VENV)/bin/playwright install $(PLAYWRIGHT_INSTALL_ARGS); \
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
		uv run portfolio cv generate --model $(MODEL) --format $(FORMAT) $(CV_PAGE_ARGS); \
	else \
		$(VENV)/bin/portfolio cv generate --model $(MODEL) --format $(FORMAT) $(CV_PAGE_ARGS); \
	fi

cv-pdf:
	$(MAKE) cv MODEL=$(MODEL) FORMAT=pdf PAGES=$(PAGES)

cv-html:
	$(MAKE) cv MODEL=$(MODEL) FORMAT=html PAGES=$(PAGES)

cv-all:
	$(MAKE) cv MODEL=academic_rich FORMAT=pdf PAGES=
	$(MAKE) cv MODEL=academic_sober FORMAT=pdf PAGES=
	$(MAKE) cv MODEL=academic_sober FORMAT=pdf PAGES=4
	$(MAKE) cv MODEL=academic_sober FORMAT=pdf PAGES=3

cv-check:
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) cv-all
	git diff --check

clean-cv:
	rm -rf build/cv

site:
	@if command -v uv >/dev/null 2>&1; then \
		uv run portfolio site generate $(SITE_ARGS); \
	else \
		$(VENV)/bin/portfolio site generate $(SITE_ARGS); \
	fi

clean-site:
	rm -rf build/site

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
