.PHONY: install install-playwright validate-data data-summary data-resolve cv cv-pdf cv-html cv-all cv-all-lang cv-site-downloads cv-check clean-cv site site-all clean-site test lint

PYTHON ?= python3
VENV ?= .venv
MODEL ?= academic_rich
FORMAT ?= pdf
PAGES ?=
PORTFOLIO_LANG ?= $(if $(filter en es,$(LANG)),$(LANG),en)
SITE_ARGS ?=
CLOUDFLARE_WEB_ANALYTICS_TOKEN ?=
SITE_ANALYTICS_ARGS = $(if $(CLOUDFLARE_WEB_ANALYTICS_TOKEN),--cloudflare-analytics-token $(CLOUDFLARE_WEB_ANALYTICS_TOKEN),)
PLAYWRIGHT_INSTALL_ARGS ?= chromium
CV_PAGE_ARGS = $(if $(PAGES),--pages $(PAGES),)
CV_LANG_ARGS = --lang $(PORTFOLIO_LANG)
SITE_LANG_ARGS = --lang $(PORTFOLIO_LANG)

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
		uv run portfolio cv generate --model $(MODEL) --format $(FORMAT) $(CV_LANG_ARGS) $(CV_PAGE_ARGS); \
	else \
		$(VENV)/bin/portfolio cv generate --model $(MODEL) --format $(FORMAT) $(CV_LANG_ARGS) $(CV_PAGE_ARGS); \
	fi

cv-pdf:
	$(MAKE) cv MODEL=$(MODEL) FORMAT=pdf PORTFOLIO_LANG=$(PORTFOLIO_LANG) PAGES=$(PAGES)

cv-html:
	$(MAKE) cv MODEL=$(MODEL) FORMAT=html PORTFOLIO_LANG=$(PORTFOLIO_LANG) PAGES=$(PAGES)

cv-all:
	$(MAKE) cv MODEL=academic_rich FORMAT=pdf PAGES=
	$(MAKE) cv MODEL=academic_sober FORMAT=pdf PAGES=
	$(MAKE) cv MODEL=academic_sober FORMAT=pdf PAGES=4
	$(MAKE) cv MODEL=academic_sober FORMAT=pdf PAGES=3

cv-all-lang:
	$(MAKE) cv-all PORTFOLIO_LANG=en
	$(MAKE) cv-all PORTFOLIO_LANG=es

cv-site-downloads:
	$(MAKE) cv MODEL=academic_rich FORMAT=pdf PORTFOLIO_LANG=en PAGES=
	$(MAKE) cv MODEL=academic_sober FORMAT=pdf PORTFOLIO_LANG=en PAGES=
	$(MAKE) cv MODEL=academic_rich FORMAT=pdf PORTFOLIO_LANG=es PAGES=
	$(MAKE) cv MODEL=academic_sober FORMAT=pdf PORTFOLIO_LANG=es PAGES=
	mkdir -p build/site/en/downloads build/site/es/downloads
	cp build/cv/academic_rich_en.pdf build/site/en/downloads/academic_rich_en.pdf
	cp build/cv/academic_sober_en.pdf build/site/en/downloads/academic_sober_en.pdf
	cp build/cv/academic_rich_es.pdf build/site/es/downloads/academic_rich_es.pdf
	cp build/cv/academic_sober_es.pdf build/site/es/downloads/academic_sober_es.pdf

cv-check:
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) cv-all
	git diff --check

clean-cv:
	rm -rf build/cv

site:
	@if command -v uv >/dev/null 2>&1; then \
		uv run portfolio site generate $(SITE_LANG_ARGS) $(SITE_ANALYTICS_ARGS) $(SITE_ARGS); \
	else \
		$(VENV)/bin/portfolio site generate $(SITE_LANG_ARGS) $(SITE_ANALYTICS_ARGS) $(SITE_ARGS); \
	fi

site-all:
	@if command -v uv >/dev/null 2>&1; then \
		uv run portfolio site generate-all $(SITE_ANALYTICS_ARGS) $(SITE_ARGS); \
	else \
		$(VENV)/bin/portfolio site generate-all $(SITE_ANALYTICS_ARGS) $(SITE_ARGS); \
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
