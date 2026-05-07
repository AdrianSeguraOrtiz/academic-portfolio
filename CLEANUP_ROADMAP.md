# Cleanup and Refactoring Roadmap

This document defines the cleanup phases for the academic portfolio repository.
The goal is to reduce technical debt without changing portfolio content or
visual behavior unintentionally.

## Guiding Principles

- Keep YAML data as the source of truth.
- Avoid special-case logic tied to concrete record IDs, names, institutions, or
  dates.
- Prefer small refactors with tests over large rewrites.
- Keep generated outputs reproducible through `make` commands.
- Preserve the current website and CV behavior unless a phase explicitly changes
  it.

## Phase 0: Baseline and Safety Net

Purpose: make sure every cleanup starts from a measurable, safe baseline.

Tasks:

- Run and record the current baseline:
  - `make validate-data`
  - `make test`
  - `make lint`
  - `make site`
  - `make cv`
  - `node --check assets/site/dissemination.js`
  - `node --check assets/site/career-timeline.js`
  - `node --check assets/site/collaborations.js`
- Keep `git diff --check` clean.
- Confirm generated files do not contain `undefined`, `null`, or `None` where
  not expected.
- Take screenshots or visual references for the main website sections before
  major UI refactors.

Acceptance criteria:

- All checks pass.
- There is a known visual baseline for the website.
- The worktree is organized into logical commits before starting large changes.

## Phase 1: Data and Schema Cleanup

Purpose: remove redundant static fields and ensure the schema matches the data
model we actually want to maintain.

Tasks:

- Review redundant fields currently duplicated by `organization_ids`, especially:
  - `institution`
  - `institution_type`
- Decide whether templates still need fallback fields before removing them.
- Update `SCHEMA.md` and `scripts/validate_data.rb` together.
- Add validation rules for any field that should be deprecated.
- Keep IDs, relationships, and chronological ordering validated.

Acceptance criteria:

- No deprecated field remains unless explicitly documented.
- Validator fails clearly if deprecated fields are reintroduced.
- CV and website still render after schema cleanup.

## Phase 2: Shared View Helpers

Purpose: avoid duplicated record-loading and reference-resolution logic between
CV and website generation.

Tasks:

- Continue moving shared view helpers into `src/academic_portfolio/view_records.py`.
- Keep `cv.py` focused on CV-specific view assembly.
- Keep `site.py` focused on website-specific view assembly until it is split in
  later phases.
- Add tests for shared helpers if they gain non-trivial behavior.

Candidates:

- Resolved record loading.
- Related-record attachment.
- Sorting by date or field.
- Common display labels.

Acceptance criteria:

- No duplicated helper exists in both `cv.py` and `site.py`.
- Existing CV and site tests cover the shared behavior indirectly or directly.

## Phase 3: Split `site.py` by Domain

Purpose: reduce the largest maintenance hotspot in the repository.

Current issue:

- `src/academic_portfolio/site.py` contains website assembly, software metrics,
  publications, career timeline, teaching timeline, dissemination, organization
  networks, collaborations, and rendering infrastructure.

Target structure:

```text
src/academic_portfolio/site/
  __init__.py
  build.py
  career.py
  collaborations.py
  dissemination.py
  organizations.py
  projects.py
  software.py
  teaching.py
```

Suggested order:

1. Move pure helper sections first.
2. Move one visual section at a time.
3. Keep `build_site_view()` as the orchestration layer.
4. Run the full test suite after each module extraction.

Acceptance criteria:

- No module is excessively large compared with the others.
- Each visual section has a clear owner module.
- Imports do not create circular dependencies.
- Website output remains stable unless intentionally changed.

## Phase 4: Template Decomposition

Purpose: make the website template easier to modify without breaking unrelated
sections.

Tasks:

- Split `templates/site/index.html.j2` into macros or includes.
- Group reusable cards, links, and section headers.
- Keep section-specific markup close to the corresponding site view module.

Candidate structure:

```text
templates/site/
  index.html.j2
  macros/common.html.j2
  sections/career.html.j2
  sections/collaborations.html.j2
  sections/dissemination.html.j2
  sections/organizations.html.j2
  sections/projects.html.j2
  sections/publications.html.j2
  sections/software.html.j2
  sections/teaching.html.j2
```

Acceptance criteria:

- `index.html.j2` becomes mostly layout orchestration.
- Shared macros are reused instead of copied.
- Template changes remain easy to review by section.

## Phase 5: CSS Architecture Cleanup

Purpose: remove unused CSS, reduce selector conflicts, and make section styles
easier to reason about.

Tasks:

- Group CSS by section in a consistent order.
- Remove selectors not referenced by templates, JS, or generated class patterns.
- Merge duplicate selectors where the later rule only overwrites the earlier one.
- Document intentionally dynamic class families such as:
  - `rel-*`
  - `category-*`
  - `depth-*`
  - `side-*`
- Avoid broad selectors that accidentally affect nested elements.
- Keep responsive overrides explicit and near related section styles where
  practical.

Useful checks:

```bash
rg -n "selector-name" templates assets src tests
git diff --check
```

Acceptance criteria:

- No known dead CSS remains.
- No accidental selector override is required for normal rendering.
- Section styles are easy to locate.
- Visual output remains stable.

## Phase 6: JavaScript Cleanup

Purpose: make interactive visualizations maintainable and less coupled to DOM
details.

Tasks:

- Review each JS file independently:
  - `assets/site/career-timeline.js`
  - `assets/site/collaborations.js`
  - `assets/site/dissemination.js`
- Extract repeated SVG or layout helpers only when duplication is real.
- Keep data parsing and drawing logic separate.
- Avoid hardcoded visual dimensions unless documented as layout constants.
- Add minimal DOM guards for optional sections.

Acceptance criteria:

- `node --check` passes for every JS file.
- Interactive components fail gracefully if data or external map assets are
  unavailable.
- Constants are named and documented by usage.

## Phase 7: Detect Data-Specific Exceptions

Purpose: identify and remove code that only works because the current data has
specific IDs, names, cities, dates, or organizations.

This is important because the portfolio must scale as new records are added.
Rendering logic should depend on schema fields, record types, relationships, and
derived metrics, not on concrete values like `organization_01`, `UMA`, `GENECI`,
or a specific publication ID.

Tasks:

- Search for hardcoded record IDs:

```bash
rg -n "organization_[0-9]+|publication_[0-9]+|position_[0-9]+|degree_[0-9]+|grant_[0-9]+|software_[0-9]+|package_[0-9]+" src templates assets tests
```

- Search for hardcoded domain names used as control flow:

```bash
rg -n "UMA|Khaos|GENECI|MOEBA|IBIMA|Lille|Málaga|Athens|Spain|France|Greece" src templates assets
```

- Classify each match:
  - Acceptable: tests asserting known fixture data.
  - Acceptable: display text coming from YAML.
  - Acceptable: documented examples in docs.
  - Suspicious: branching, sorting, layout, colors, or labels based on a concrete
    ID or name.
  - Suspicious: hardcoded coordinates, dates, or organization-specific layout
    fixes outside YAML.

- Replace suspicious matches with generic mechanisms:
  - Schema fields.
  - Relationship types.
  - Organization hierarchy.
  - Record dates.
  - Derived metrics.
  - CSS classes generated from record category, not record ID.

Acceptance criteria:

- No production code branches on a concrete record ID or literal organization
  name.
- Tests may reference known IDs, but production behavior must not depend on them.
- Any remaining literal domain value is documented as a label, example, or
  external API parameter.

## Phase 8: Validation and Test Expansion

Purpose: make cleanup safer by catching regressions earlier.

Tasks:

- Add tests for schema constraints that have caused previous issues:
  - Deprecated fields.
  - Invalid relationship fields.
  - Broken parent organization links.
  - Missing dynamic metadata fallbacks.
- Add tests for organization hierarchy aggregation.
- Add tests for data-specific exception prevention where practical.
- Keep generated site smoke tests checking for key section markers.

Acceptance criteria:

- Tests cover new validation rules.
- A future accidental reintroduction of deprecated fields fails fast.
- Organization and publication aggregation behavior is protected.

## Phase 9: Documentation and Developer Workflow

Purpose: keep maintenance easy after the refactor.

Tasks:

- Update `README.md` with the recommended workflow.
- Keep `SCHEMA.md` synchronized with validator behavior.
- Document dynamic data sources:
  - GitHub
  - PyPI / ClickPy / ClickHouse
  - Maven Central
- Document cache locations and refresh flags.
- Add a short "How to add a new record" section for each major data type.

Acceptance criteria:

- A future contributor can add data without reading implementation code.
- The generation workflow is clear from `README.md`.
- Schema, validator, and examples agree.

## Phase 10: Commit Organization

Purpose: keep the history reviewable.

Recommended commit groups:

1. Data/schema cleanup.
2. Shared Python helper extraction.
3. Site module split.
4. Template decomposition.
5. CSS cleanup.
6. JS cleanup.
7. Data-specific exception removal.
8. Test and documentation updates.

Acceptance criteria:

- Each commit passes the full check suite.
- Each commit has a single reviewable purpose.
- Generated outputs are updated only when relevant.
