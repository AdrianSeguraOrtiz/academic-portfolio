# Academic Portfolio Data Schema

All structured data lives in `data/` as YAML files. Lists are ordered from oldest to newest; output scripts can reverse or filter them for CV and web views.

## Directory Layout

```text
data/
  profile.yaml

  entities/
    organizations.yaml

  career/
    certifications.yaml
    degrees.yaml
    experience.yaml
    grants.yaml
    honors.yaml
    research_stays.yaml

  research/
    publications.yaml
    research_projects.yaml
    reviewing.yaml
    software_packages.yaml
    software_projects.yaml

  activities/
    dissemination/
      presentations.yaml
      press.yaml
      scientific_dissemination_articles.yaml
      social_media.yaml
      tv_media.yaml
    teaching/
      academic_supervision.yaml
      teaching_innovation_projects.yaml
      university_classes.yaml
```

`entities/` contains reusable lookup records. The other folders group CV sections by domain. `activities/dissemination/` contains outreach and media activity; `activities/teaching/` contains teaching activity.

## Profile

`data/profile.yaml` stores personal details, contact information, external
profile links, current activity references, and research areas.

Current activity is stored only as IDs:

```yaml
current_position_ids:
- position_05
current_stay_ids:
- stay_02
```

The referenced records live in `career/experience.yaml` and
`career/research_stays.yaml`.

## Organizations

Organizations are standalone lookup records. They should not contain reverse links or relationship fields to publications, projects, awards, or other records. Use these fields consistently:

```yaml
id: organization_01
name: Universidad de Málaga
full_name: Universidad de Málaga
abbreviation: UMA
type: University
parent_organization_id: null
location:
  city: Málaga
  country: Spain
  coordinates:
    latitude: 36.7213
    longitude: -4.4214
website: https://www.uma.es/
```

`location.coordinates` stores decimal latitude and longitude when the location is
known. Site generators use these coordinates for collaboration map views; leave
both values as `null` only when the organization location is not specific enough.

`parent_organization_id` stores institutional containment, such as a research
group belonging to an institute or a laboratory belonging to a university. Use
`null` for root organizations.

## IDs

Referencable records use stable IDs with this pattern:

```text
type_01
type_02
```

Examples: `degree_01`, `award_01`, `software_01`, `organization_01`.

New records should be appended chronologically and assigned the next available number for that record type.

## Cross-References

Use explicit relationship fields instead of universal relationship blocks. Relationship fields always store IDs and use the `_ids` suffix for lists:

```yaml
organization_ids:
- organization_01
publication_ids:
- publication_01
software_project_ids:
- software_05
```

Profile-level current activity is also stored as references instead of duplicated records:

```yaml
current_position_ids:
- position_05
current_stay_ids:
- stay_02
```

Allowed relationship fields are intentionally limited by record type:

| File / group | Allowed relationship fields |
| --- | --- |
| `entities/organizations.yaml` / `organizations` | `parent_organization_id` |
| `activities/dissemination/press.yaml` / `press_items` | `publication_ids` |
| `activities/dissemination/social_media.yaml` / `social_media_items` | `publication_ids` |
| `activities/dissemination/tv_media.yaml` / `tv_items` | `publication_ids` |
| `activities/dissemination/scientific_dissemination_articles.yaml` / `scientific_dissemination_articles` | `publication_ids`, `software_package_ids` |
| `activities/dissemination/presentations.yaml` / `presentations` | `publication_ids`, `software_package_ids` |
| `activities/teaching/university_classes.yaml` / `university_classes` | `organization_ids` |
| `activities/teaching/academic_supervision.yaml` / `academic_supervision` | `organization_ids` |
| `activities/teaching/teaching_innovation_projects.yaml` / `teaching_innovation_projects` | `organization_ids` |
| `career/degrees.yaml` / `degrees` | `organization_ids`, `grant_ids` |
| `career/certifications.yaml` / `certifications` | `organization_ids` |
| `career/experience.yaml` / `positions` | `organization_ids` |
| `career/research_stays.yaml` / `stays` | `organization_ids`, `grant_ids` |
| `career/honors.yaml` / `honors` | `degree_ids` |
| `career/grants.yaml` / `grants` | `position_ids`, `stay_ids` |
| `research/publications.yaml` / `journal_papers` | `organization_ids`, `software_project_ids`, `research_project_ids`, `position_ids`, `stay_ids`, `grant_ids` |
| `research/publications.yaml` / `conference_papers` | `organization_ids`, `software_project_ids`, `research_project_ids`, `position_ids`, `stay_ids`, `grant_ids` |
| `research/research_projects.yaml` / `funded_projects` | `organization_ids` |
| `research/reviewing.yaml` / `reviewing` | none |
| `research/software_packages.yaml` / `software_packages` | none |
| `research/software_projects.yaml` / `projects` | none |

Organizations are stored in `data/entities/organizations.yaml` and referenced by ID from other files.
Records should not reference themselves; inverse relationships should be derived by scripts instead of duplicated manually.

Record-level organization names and organization types are resolved through
`organization_ids`. Names, abbreviations, websites, locations, and types live in
`data/entities/organizations.yaml`.

## Field Consistency

Items inside the same top-level YAML group must use the same fields. Use `null`
or an empty list when a field is not applicable for a specific record. This keeps
scripts simple and avoids ad hoc field checks.

Lists with date-bearing records are ordered from oldest to newest. Output
generators can reverse, group, or filter records for a specific CV or website
view.

## Software Projects

Software project records keep only curated portfolio information. GitHub-derived
metadata is collected dynamically by the website generator and cached under
`build/cache/`, so do not duplicate repository activity fields in YAML.

Use these fields consistently:

```yaml
id: software_01
name: GENECI
full_name: GEne NEtwork Consensus Inference
type: Research software project
description: Short curated description.
domains:
- Gene regulatory network inference
- Bioinformatics
urls:
  github: https://github.com/owner/repository
```

Repository dates, commit activity, languages, stars, forks, issues, license, and
last push are derived from GitHub when generating the website.

## Software Packages

Software package records keep only registry identifiers. Registry metadata,
release information, and package analytics are derived dynamically by the
website generator and cached under `build/cache/`.

Use ecosystem-specific identifiers:

```yaml
id: package_01
name: GENECI
ecosystem: PyPI
package_name: geneci
```

```yaml
id: package_02
name: MOEBA-BIO
ecosystem: Maven
group_id: io.github.adrianseguraortiz
artifact_id: moeba-bio
```

For PyPI, total downloads, time series, versions, countries, Python versions,
systems, and file types are derived from PyPI and ClickPy/ClickHouse. For Maven,
versions, POM metadata, dependencies, and published artifacts are derived from
Maven Central.

## Dynamic Website Metadata

Dynamic data is generated for the website only and is not written back to YAML.

| Source | Used for | Cache |
| --- | --- | --- |
| GitHub REST API | Repository metadata, language breakdown, commit counts, commit activity, stars, forks, issues, license, first/last commit, latest push | `build/cache/github_repositories.json` |
| PyPI JSON API | Package metadata and releases for PyPI packages | `build/cache/software_packages.json` |
| ClickPy / ClickHouse public data | PyPI downloads, monthly time series, versions, countries, Python versions, operating systems, file types | `build/cache/software_packages.json` |
| Maven Central | Maven versions, POM metadata, dependencies, licenses, published artifacts | `build/cache/software_packages.json` |
| World Atlas, D3, TopoJSON | Browser-rendered collaboration map | Browser runtime |

The site CLI supports `--refresh-github/--no-refresh-github`,
`--refresh-packages/--no-refresh-packages`, `--github-cache-path`, and
`--package-cache-path`.

## Validation

Run:

```bash
make validate-data
```

This delegates to `ruby scripts/validate_data.rb`.

The validator checks YAML syntax, duplicate IDs, ID format, allowed relationship
fields, unresolved references, self-references, consistent fields within each
top-level group, and chronological order for dated lists.
