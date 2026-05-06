# Academic Portfolio

Structured academic portfolio data for CV generation, personal websites, and academic application workflows.

The repository stores the portfolio as normalized YAML records under `data/`. Records use stable IDs and explicit cross-references so scripts can generate different outputs without duplicating information.

## Structure

```text
data/
  profile.yaml
  entities/
  career/
  research/
  activities/

scripts/
  validate_data.rb

src/
  academic_portfolio/

SCHEMA.md
```

`SCHEMA.md` documents the data layout, ID conventions, allowed relationship fields, and validation rules.

## Python Environment

Install the Python tooling in a virtual environment:

```bash
make install
```

If `uv` is available, the command uses `uv sync --dev`. Otherwise it creates `.venv/` with `python3 -m venv` and installs the project with development dependencies.

## Validation

Run the data validator before using the data in generation scripts:

```bash
make validate-data
```

This runs:

```bash
ruby scripts/validate_data.rb
```

The validator checks YAML syntax, duplicate IDs, ID format, allowed relationship fields, unresolved references, deprecated relationship blocks, self-references, and chronological ordering.

## Data Inspection

After installing the Python environment, inspect the loaded YAML files with:

```bash
make data-summary
```

Resolve a record and inspect its outgoing references with:

```bash
make data-resolve ID=publication_04
```

Run the Python test and lint checks with:

```bash
make test
make lint
```

## CV Generation

Generate the first Markdown CV from the academic full model:

```bash
make cv MODEL=academic_full FORMAT=md
```

The generated file is written to `build/cv/academic_full.md`.

## Static Website

Generate the first static personal website:

```bash
make site
```

The generated homepage is written to `build/site/index.html`, with static assets under
`build/site/assets/`.

The homepage derives collaboration maps from organization coordinates, research
stays, and publication organization references. Add `location.coordinates` to new
organizations when they should appear in map-based views. The map is rendered in
the browser with D3, TopoJSON, and the public World Atlas dataset.

The website generator enriches software projects with public GitHub metadata by default.
Repository metrics and monthly commit activity are cached in `build/cache/` to reduce API
usage. Set `GITHUB_TOKEN` before running `make site` if you need a higher GitHub API limit.

Software package cards are also enriched dynamically. PyPI packages use PyPI metadata plus
ClickPy/ClickHouse download analytics, while Maven packages use Maven Central metadata and
published artifact data. These results are cached in `build/cache/software_packages.json`.

## Editing Guidelines

- Keep lists ordered from oldest to newest.
- Add new records with the next available stable ID for that type.
- Store relationships as explicit `*_ids` fields only where allowed by `SCHEMA.md`.
- Avoid reverse relationships that can be derived by scripts.
- Use URLs instead of embedding documents.
- Keep descriptions concise and factual.
