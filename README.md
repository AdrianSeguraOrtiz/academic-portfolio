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

## CV Generation

Generate the academic full Markdown CV:

```bash
make cv MODEL=academic_full FORMAT=md
```

The output is written to `build/cv/academic_full.md`.

CV models live in `cv_models/`. The current generator writes Markdown; later
PDF-specific renderers should reuse the same YAML data and model definitions.

## Static Website

Generate the static site:

```bash
make site
```

The site is written to `build/site/index.html`, with copied assets under
`build/site/assets/`.

`make site` refreshes dynamic GitHub and package data by default. To render from
YAML and cached data without network refresh:

```bash
make site SITE_ARGS="--no-refresh-github --no-refresh-packages"
```

Use custom cache paths when needed:

```bash
make site SITE_ARGS="--github-cache-path build/cache/github_repositories.json --package-cache-path build/cache/software_packages.json"
```

Set `GITHUB_TOKEN` before `make site` for a higher GitHub API limit.

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
