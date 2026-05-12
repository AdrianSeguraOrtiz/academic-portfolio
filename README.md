# Academic Portfolio

Structured academic portfolio data for CV generation, static personal websites,
and academic application workflows.

The repository keeps curated information in normalized YAML files under `data/`.
Records use stable IDs and explicit relationships so generators can build
different outputs without duplicating content.

## Repository Layout

```text
data/
  profile.yaml
  entities/
  career/
  research/
  activities/

assets/site/
cv_models/
scripts/
src/academic_portfolio/
templates/
tests/

SCHEMA.md
```

`SCHEMA.md` is the data contract. When changing YAML structure, update the
schema, validator, tests, and templates in the same change.

## Setup

Install the Python tooling in a virtual environment:

```bash
make install
```

If `uv` is available, this runs `uv sync --dev`. Otherwise it creates `.venv/`
and installs the project with development dependencies.

PDF generation also needs a local Chromium browser managed by Playwright:

```bash
make install-playwright
```

## Daily Workflow

Use this loop when editing portfolio data or generators:

```bash
make validate-data
make test
make lint
make site
make cv
```

For JavaScript-only changes, also run:

```bash
node --check assets/site/dissemination.js
node --check assets/site/collaborations.js
node --check assets/site/career-timeline.js
```

Before committing, keep whitespace clean:

```bash
git diff --check
```

## Data Inspection

Inspect loaded YAML files:

```bash
make data-summary
```

Resolve a record and inspect its outgoing references:

```bash
make data-resolve ID=publication_04
```

## Language Support

The project supports English (`en`) and Spanish (`es`) outputs from the same
YAML data. English is the default language for commands and generated routes.

Use `PORTFOLIO_LANG` from `make`:

```bash
make site PORTFOLIO_LANG=en
make site PORTFOLIO_LANG=es
make cv MODEL=academic_rich PORTFOLIO_LANG=es
make cv MODEL=academic_sober PORTFOLIO_LANG=es PAGES=4
```

Equivalent CLI flags:

```bash
portfolio site generate --lang es
portfolio site generate-all
portfolio cv generate --model academic_sober --lang es --pages 4
```

Generate both website languages:

```bash
make site-all
```

Generate the active CV outputs in both languages:

```bash
make cv-all-lang
```

Generate the website CV downloads used by GitHub Pages:

```bash
make cv-site-downloads
```

### Language Output Paths

Website outputs are language-scoped:

```text
build/site/index.html
build/site/en/index.html
build/site/es/index.html
build/site/en/assets/
build/site/es/assets/
build/site/en/downloads/academic_rich_en.pdf
build/site/en/downloads/academic_sober_en.pdf
build/site/es/downloads/academic_rich_es.pdf
build/site/es/downloads/academic_sober_es.pdf
```

CV outputs include the language suffix:

```text
build/cv/academic_rich_en.pdf
build/cv/academic_rich_es.pdf
build/cv/academic_sober_en.pdf
build/cv/academic_sober_es.pdf
```

Page-limited sober CVs include both the page limit and language:

```text
build/cv/academic_sober_4p_en.pdf
build/cv/academic_sober_4p_es.pdf
build/cv/academic_sober_3p_en.pdf
build/cv/academic_sober_3p_es.pdf
```

### Data Authoring Rules

Do not duplicate the dataset into separate English and Spanish folders. Keep one
canonical `data/` tree and use localized maps only for authored display text
that genuinely needs a language-specific rendering:

```yaml
description:
  en: Short curated description.
  es: Descripción breve curada.
```

Good candidates for localized maps are `description`, `summary`, `context`,
`purpose`, `notes`, `tasks`, `domains`, `type`, `role`, `participation`,
`employment_type`, `dedication`, and `work_mode`.

Preserve canonical/source values as scalars when translating them would be
misleading or would hide official wording:

- publication titles, venues, publishers, DOIs, and author names;
- journal names, conference names, media outlets, social platforms, and
  channels;
- legal organization names and official funder names;
- official degree, course, award, grant, project, press, dissemination article,
  and presentation titles unless a separate translated display value is useful;
- IDs, relationship fields, URLs, package coordinates, dates, and metrics.

Fallback behavior is intentional:

- Generated UI text is read from `locales/<lang>.yaml`; missing target-language
  keys fall back to English, and tests require key parity so missing keys are
  easy to catch.
- Localized YAML maps use the requested language when present, otherwise fall
  back to English, then to the first non-empty value.
- Scalar YAML values are displayed unchanged in every language.

After changing localization data or locale files, run:

```bash
make validate-data
make test
```

## CV Generation

The CV pipeline generates print-safe HTML and exports PDF with Playwright. The
default model is `academic_rich`:

```bash
make cv
```

Equivalent explicit PDF command:

```bash
make cv-pdf
```

The output is written to `build/cv/<model>_<lang>.pdf`. The generator also keeps
`build/cv/<model>_<lang>.html` as an intermediate artifact for visual debugging,
copies CV-specific static assets to `build/cv/assets/`, and prints the generated
page count.

CV styles are split by editorial responsibility: `common.css` contains shared
print/page rules, `rich.css` contains the visual portfolio layout, and
`sober.css` contains the institutional document layout. Each CV loads only the
common stylesheet plus the stylesheet matching its model style.

To generate only the intermediate HTML:

```bash
make cv-html
```

Use a different CV model by setting `MODEL`:

```bash
make cv MODEL=academic_rich
make cv MODEL=academic_sober
make cv MODEL=academic_sober PAGES=4
make cv MODEL=academic_sober PAGES=3
make cv MODEL=academic_sober PORTFOLIO_LANG=es
make cv-pdf MODEL=academic_sober
make cv-html MODEL=academic_sober
make cv-html MODEL=academic_sober PAGES=4
```

Generate all configured PDFs:

```bash
make cv-all
```

This writes:

- `build/cv/academic_rich_en.pdf`
- `build/cv/academic_sober_en.pdf`
- `build/cv/academic_sober_4p_en.pdf`
- `build/cv/academic_sober_3p_en.pdf`

Generate the same active set in both languages:

```bash
make cv-all-lang
```

Run the full CV check before committing CV-related changes:

```bash
make cv-check
```

`make cv-check` runs `make lint`, `make test`, `make cv-all`, and
`git diff --check`.

Clean generated CV artifacts:

```bash
make clean-cv
```

### CV Models

CV models live in `cv_models/`. The active model set is intentionally small:
there is one visual full model and one institutional model. Shorter outputs are
generated by passing a page constraint to the institutional model, not by adding
new model identities.

| Model | Use case | Editorial contract | Page limit | Content strategy |
| --- | --- | --- | --- | --- |
| `academic_rich` | Complete academic CV for sharing with researchers or as a portfolio PDF. | Visual PDF equivalent of the website. It keeps the website section order and reuses website-style dashboards, cards, charts, and snapshots. | None | Full detail for core and aggregate sections. No chart should exist here unless it has a clear website equivalent. |
| `academic_sober` | Complete academic CV for formal calls and institutional applications. | Institutional and atomic. No dashboards, portfolio cards, charts, profile photo, or research-focus panels. Positions are grouped by institution when several roles belong to the same organization. | None by default; optional with `PAGES`. | Full detail unless a page limit requests compact rendering. URLs and internal anchors remain enabled. |

Models without a page limit report only the generated page count, for example
`Pages: 12`.

Every active CV model includes the profile summary. Page-limited variants use a
shorter summary level automatically, but they do not remove the summary.

### Page Limits

Dedicated short-model TOML files are no longer part of the active model set.
Page-limited sober variants are handled as output constraints rather than as
separate model identities. The underlying generator still supports page fitting
for page-limited renders and reports page usage and fit status, for example:

```bash
make cv MODEL=academic_sober PAGES=4
portfolio cv generate --model academic_sober --pages 4
```

Page limits are only supported for `academic_sober`. The rich model is a full
visual portfolio PDF and is not compressed into a fixed page count.

When `PAGES` or `--pages` is provided, the output filename includes the page
limit and language suffixes, for example `build/cv/academic_sober_4p_en.pdf`.

```text
Pages: 3/3
Fit status: fits
```

Page-limited renders must never satisfy page limits by dropping core records.
Instead, the generator tries progressively denser print styles. If all required
core records cannot fit, generation fails explicitly with a message that names
the limit, the minimum render size, and the blocks contributing most to the
overflow:

```text
academic_sober cannot fit all required core records in 3 pages.
Minimum compact render requires 5 pages.
Largest contributors:
- publications: ...
```

In that case, reduce prose/detail levels in the model, improve CSS density, or
move non-core material into aggregate summaries. Do not add `max_*` limits for
core records.

### Core vs Aggregate Content

Core records must appear in every CV model:

- Publications.
- Professional positions.
- Degrees.
- Honors.
- Research stays.
- Grants.
- Research projects.

Page-limited variants may compact these records, but they do not remove any of
them.

Aggregate sections can be summarized with counts, metrics, and short highlights:

- Certifications.
- Software projects.
- Software packages.
- Teaching activity.
- Dissemination and media.
- Reviewing.

Aggregate item limits such as `max_social_media` only affect how many individual
items are listed. Summary metrics and highlights are calculated from the full
dataset.

When space is tight, prefer compact prose for aggregate sections while still
mentioning the most relevant highlights textually where possible: highly viewed
social media items, package downloads, television appearances, dissemination
articles, teaching innovation projects, and comparable evidence-backed items.

### Editing CV Models

Each TOML model defines:

- `style`: `rich` or `sober`.
- `page_limit`: optional output constraint.
- `[sections]`: detail level per section.
- `[layout]`: density, font scale, charts, dashboard, profile photo, URLs, and
  anchors.
- `[limits]`: optional limits for aggregate item lists only.

Allowed section detail levels are:

- `hidden`: omit the section.
- `aggregate`: show only summary metrics/highlights.
- `micro`: one-line or very dense entry.
- `compact`: compact card with essential metadata.
- `standard`: richer card with references and selected details.
- `full`: full card with all relevant details.

When editing model TOML files:

- Do not hide or limit core sections.
- Use `micro` or `compact` for page-limited core sections instead of item limits.
- Use `[limits]` only for aggregate sections.
- Keep `include_charts = false` for sober models.
- Keep rich charts aligned with website charts. If a new chart is needed in
  `academic_rich`, first define the same visualization concept for the website
  or document why the PDF needs a static equivalent.
- Keep sober sections atomic: each formal category should be rendered as its own
  section rather than as a mixed dashboard.
- Run `make cv-check` after changes.

## Static Website

Generate the static site:

```bash
make site
```

The site is written to `build/site/<lang>/index.html`, with copied assets under
`build/site/<lang>/assets/`. English is the default language.

```bash
make site PORTFOLIO_LANG=es
make site-all
```

`make site-all` writes both `build/site/en/` and `build/site/es/`, then creates
`build/site/index.html` as a relative redirect to `build/site/en/`. The language
switcher links between the equivalent language routes.

The public website can also expose the full rich and sober CVs for the active
language. Generate and copy those PDFs into the language-specific site folders
with:

```bash
make cv-site-downloads
```

`make site` refreshes dynamic GitHub and package data by default. To render from
YAML and cached data without network refresh:

```bash
make site SITE_ARGS="--no-refresh-github --no-refresh-packages"
```

Use custom cache paths when needed:

```bash
make site SITE_ARGS="--github-cache-path build/cache/github_repositories.json --package-cache-path build/cache/software_packages.json"
```

Set `GITHUB_TOKEN` before `make site` or `make site-all` for a higher GitHub
API limit.

## Website vs CV

Both outputs use the same curated YAML data, but they serve different purposes.

- The website is interactive, responsive, and enriched with dynamic public data
  from GitHub, PyPI, Maven Central, ClickPy, and map datasets.
- The CV is a static print artifact. It uses the curated YAML data and
  print-safe HTML/CSS so the generated PDF is stable, portable, and suitable for
  academic applications.

Generated outputs are intentionally kept under `build/`:

```text
build/site/
build/cv/
```

## Dynamic Data Sources

The YAML stores curated facts and registry identifiers. The website enriches
some sections dynamically:

- GitHub repositories: repository metadata, stars, forks, open issues, license,
  primary language, language breakdown, commit counts, first and last commit,
  latest push, and monthly commit activity. Source: GitHub REST API.
- PyPI packages: package metadata and releases from the PyPI JSON API; total
  downloads, monthly downloads, version splits, countries, Python versions,
  operating systems, and file types from ClickPy/ClickHouse public data.
- Maven packages: versions, latest release metadata, POM metadata,
  dependencies, Java release, licenses, and published artifacts from Maven
  Central.
- Collaboration map: generated from `location.coordinates` in organizations,
  publication organization references, and research-stay organization
  references. The browser renders the map with D3, TopoJSON, and the public
  World Atlas dataset.

Dynamic caches:

```text
build/cache/github_repositories.json
build/cache/software_packages.json
```

These files are generated artifacts and can be removed to force a clean refresh.

## GitHub Pages Deployment

The repository includes `.github/workflows/deploy-site.yml`. On every push to
`main`, GitHub Actions installs the project, validates the YAML data, runs tests
and linting, generates the static site, and deploys
`build/site/` to GitHub Pages.

The bilingual deployment contract is:

```text
/academic-portfolio/en/  English site
/academic-portfolio/es/  Spanish site
/academic-portfolio/     redirects to /academic-portfolio/en/
```

The workflow runs `make site-all` and `make cv-site-downloads`, so the static
site artifact contains both language folders, the root redirect page, and the
full rich/sober CV downloads for each language. It also writes `.nojekyll` so
GitHub Pages serves the generated assets without Jekyll processing.

To enable deployment for this repository:

1. Push `main` to GitHub.
2. Open the repository on GitHub.
3. Go to `Settings` > `Pages`.
4. Set `Build and deployment` > `Source` to `GitHub Actions`.
5. Run the workflow manually from the `Actions` tab, or push to `main`.

For this project repository, the default URL is:

```text
https://AdrianSeguraOrtiz.github.io/academic-portfolio/
```

For a root personal website at `https://AdrianSeguraOrtiz.github.io`, create a
repository named `AdrianSeguraOrtiz.github.io` and reuse the same generated
`build/site/` deployment target there.

## Adding Records

General rules:

- Add records to the appropriate YAML group in `data/`.
- Keep each list ordered from oldest to newest.
- Use the next available ID for the record type.
- Use only relationship fields allowed by `SCHEMA.md`.
- Add organizations first, then reference them from other records.
- Do not duplicate inverse relationships; generators derive them.
- Use URLs for external documents and pages.
- Keep descriptions concise and factual.
- Run `make validate-data`, `make test`, and the relevant generator.

Major record types:

- Organization: add it to `data/entities/organizations.yaml`; include
  `name`, `full_name`, `abbreviation`, `type`, `parent_organization_id`,
  `location`, coordinates when known, and `website`.
- Degree or certification: add it under `data/career/`; link institutions with
  `organization_ids`; link degree funding with `grant_ids` when applicable.
- Position or research stay: add it under `data/career/`; link organizations
  with `organization_ids`; link grants with `grant_ids` for stays or through
  grant `position_ids`.
- Honor or grant: add it under `data/career/`; honors link to `degree_ids`;
  grants link to `position_ids` and/or `stay_ids`.
- Publication: add journal papers or conference papers under
  `data/research/publications.yaml`; link organizations, software projects,
  research projects, positions, stays, and grants only when directly relevant.
- Research or teaching innovation project: add it under `data/research/` or
  `data/activities/teaching/`; link only `organization_ids`.
- Software project: add curated metadata and the GitHub URL under
  `data/research/software_projects.yaml`; do not store GitHub statistics in
  YAML.
- Software package: add the registry identifiers under
  `data/research/software_packages.yaml`; do not store registry statistics in
  YAML.
- Dissemination or media item: add it under
  `data/activities/dissemination/`; press, social media, and TV media link only
  `publication_ids`; scientific dissemination articles and presentations may
  also link `software_package_ids`.
- Teaching class or supervision: add it under `data/activities/teaching/`; link
  only `organization_ids`.

## Validation

Run:

```bash
make validate-data
```

The validator checks YAML syntax, duplicate IDs, ID format, allowed relationship
fields, unresolved references, self-references, consistent fields within each
group, and chronological ordering for dated lists.
