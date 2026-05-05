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

SCHEMA.md
```

`SCHEMA.md` documents the data layout, ID conventions, allowed relationship fields, and validation rules.

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

## Editing Guidelines

- Keep lists ordered from oldest to newest.
- Add new records with the next available stable ID for that type.
- Store relationships as explicit `*_ids` fields only where allowed by `SCHEMA.md`.
- Avoid reverse relationships that can be derived by scripts.
- Use URLs instead of embedding documents.
- Keep descriptions concise and factual.
