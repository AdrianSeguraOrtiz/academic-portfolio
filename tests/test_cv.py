from pathlib import Path
from html.parser import HTMLParser
import re

import pytest

import academic_portfolio.cv as cv_module
from academic_portfolio.cv import build_cv_view, generate_cv, load_cv_model
from academic_portfolio.loader import load_data
from academic_portfolio.resolver import PortfolioResolver

NUCLEAR_LIMIT_OPTIONS = {
    "max_publications",
    "max_journal_papers",
    "max_conference_papers",
    "max_experience",
    "max_degrees",
    "max_research_stays",
    "max_honors",
    "max_grants",
    "max_research_projects",
}
DEFINITIVE_CV_MODELS = (
    "academic_rich",
    "academic_sober",
)
CV_TEMPLATE_ROOT = Path("templates/cv")
RICH_WEB_SECTIONS = [
    "Portfolio Summary",
    "Research Stays and Publication Cities",
    "Publications",
    "Software",
    "Academic Trajectory",
    "Research and Teaching Innovation Projects",
    "Classes and Supervision",
    "Dissemination and Media",
    "Organizations",
]
SOBER_ATOMIC_SECTIONS = [
    "Summary",
    "Education",
    "Experience",
    "Research Stays",
    "Publications",
    "Research Projects",
    "Honors",
    "Grants",
    "Certifications",
    "Teaching",
    "Software",
    "Dissemination",
    "Reviewing",
]
RICH_WEB_CHART_TITLES = {
    "Publication Collaboration",
    "Research Stays",
    "Publications by Year",
    "Commit Activity",
    "Languages",
    "Timeline Snapshot",
    "Classroom Hours by Academic Year",
    "Classroom Hours by Degree Programme",
    "Total Dissemination Items",
    "Items by Type",
}
CORE_BLOCKS = {
    "publications": lambda view: view["core"]["publications"]["items"],
    "degrees": lambda view: view["core"]["education"]["items"],
    "experience": lambda view: view["core"]["experience"]["items"],
    "research_stays": lambda view: view["core"]["research_stays"]["items"],
    "honors": lambda view: view["core"]["honors"]["items"],
    "grants": lambda view: view["core"]["grants"]["items"],
    "research_projects": lambda view: view["core"]["research_projects"]["items"],
}


class CVHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.internal_hrefs: list[str] = []
        self.stylesheets: list[str] = []
        self.classes: list[str] = []
        self.h2: list[str] = []
        self.h3: list[str] = []
        self._active_heading: str | None = None
        self._active_heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids.append(element_id)

        class_names = attributes.get("class")
        if class_names:
            self.classes.extend(class_names.split())

        href = attributes.get("href")
        if href and href.startswith("#") and len(href) > 1:
            self.internal_hrefs.append(href[1:])

        if tag == "link" and attributes.get("rel") == "stylesheet" and href:
            self.stylesheets.append(href)

        if tag in {"h2", "h3"}:
            self._active_heading = tag
            self._active_heading_parts = []

    def handle_data(self, data: str) -> None:
        if self._active_heading:
            self._active_heading_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != self._active_heading:
            return

        heading = " ".join("".join(self._active_heading_parts).split())
        if tag == "h2":
            self.h2.append(heading)
        elif tag == "h3":
            self.h3.append(heading)
        self._active_heading = None
        self._active_heading_parts = []


def _parse_cv_html(content: str) -> CVHTMLParser:
    parser = CVHTMLParser()
    parser.feed(content)
    return parser


def _chart_card_titles(content: str) -> list[str]:
    matches = re.findall(
        r'<article class="[^"]*\bcv-chart-card\b[^"]*"[^>]*>\s*<h3>(.*?)</h3>',
        content,
        flags=re.DOTALL,
    )
    return [" ".join(re.sub(r"<[^>]+>", "", match).split()) for match in matches]


def _assert_ordered_subset(actual: list[str], expected: list[str]) -> None:
    search_from = 0
    for expected_item in expected:
        try:
            found_at = actual.index(expected_item, search_from)
        except ValueError as error:
            raise AssertionError(
                f"{expected_item!r} was not found after {actual[:search_from]!r}"
            ) from error
        search_from = found_at + 1


def _assert_core_record_anchors(content: str, reference_view: dict) -> None:
    ids = set(_parse_cv_html(content).ids)
    missing = {
        block_name: [
            record_id
            for record_id in _ids(records_for_block(reference_view))
            if record_id not in ids
        ]
        for block_name, records_for_block in CORE_BLOCKS.items()
    }
    missing = {block_name: record_ids for block_name, record_ids in missing.items() if record_ids}

    assert missing == {}


def _cv_model_paths() -> list[Path]:
    return sorted(Path("cv_models").glob("*.toml"))


def _load_cv_view(model_name: str) -> dict:
    return build_cv_view(
        load_cv_model(Path(f"cv_models/{model_name}.toml")),
        PortfolioResolver(load_data(Path("data"))),
    )


def _ids(records: list[dict]) -> list[str]:
    return [str(record["id"]) for record in records]


def _read_cv_asset(output_dir: Path, filename: str) -> str:
    return (output_dir / "assets" / filename).read_text(encoding="utf-8")


def _active_cv_text_files() -> list[Path]:
    text_suffixes = {".py", ".j2", ".toml", ".css", ".yml", ".yaml"}
    files: list[Path] = []
    for root in (
        Path("src"),
        Path("templates/cv"),
        Path("cv_models"),
        Path(".github/workflows"),
    ):
        files.extend(
            path for path in root.rglob("*") if path.is_file() and path.suffix in text_suffixes
        )
    files.extend([Path("Makefile"), Path("pyproject.toml")])
    files.extend(path for path in Path("assets/cv").glob("*.css") if path.is_file())
    return sorted(files)


def _portfolio_specific_terms() -> set[str]:
    data = load_data(Path("data"))
    keys_with_portfolio_values = {
        "abbreviation",
        "artifact_id",
        "email",
        "full_name",
        "name",
        "orcid",
        "package_name",
        "title",
    }
    generic_terms = {
        "Academic",
        "Artificial intelligence",
        "Bioinformatics",
        "Conference",
        "Education",
        "Experience",
        "Full-time",
        "Journal",
        "Part-time",
        "Research",
        "Software",
        "Spain",
        "Teaching",
        "University",
    }
    terms: set[str] = set()

    def collect(value: object, key: str | None = None) -> None:
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                collect(child_value, str(child_key))
        elif isinstance(value, list):
            for child_value in value:
                collect(child_value, key)
        elif isinstance(value, str) and key in keys_with_portfolio_values:
            term = value.strip()
            if len(term) > 4 and term not in generic_terms:
                terms.add(term)

    collect(data.documents)
    return terms


def test_build_cv_view_resolves_current_activity() -> None:
    model = load_cv_model(Path("cv_models/academic_rich.toml"))
    resolver = PortfolioResolver(load_data(Path("data")))

    view = build_cv_view(model, resolver)

    assert [position["id"] for position in view["core"]["profile"]["current_positions"]] == [
        "position_05",
        "position_06",
    ]
    assert [stay["id"] for stay in view["core"]["profile"]["current_stays"]] == ["stay_02"]


def test_build_cv_view_resolves_publication_references() -> None:
    model = load_cv_model(Path("cv_models/academic_rich.toml"))
    resolver = PortfolioResolver(load_data(Path("data")))

    view = build_cv_view(model, resolver)
    publication = next(
        item
        for item in view["core"]["publications"]["items"]
        if item["id"] == "publication_04"
    )
    publication_record = publication["record"]

    assert [item["id"] for item in publication_record["resolved"]["software_project_ids"]] == [
        "software_10"
    ]
    assert [item["id"] for item in publication_record["resolved"]["grant_ids"]] == [
        "grant_01",
        "grant_02",
    ]
    assert [
        item["id"] for item in view["core"]["publications"]["groups"]["conference_papers"]
    ] == [
        "publication_02"
    ]
    assert "publication_02" not in [
        item["id"] for item in view["core"]["publications"]["groups"]["journal_papers"]
    ]


def test_build_cv_view_resolves_research_stay_grants() -> None:
    model = load_cv_model(Path("cv_models/academic_rich.toml"))
    resolver = PortfolioResolver(load_data(Path("data")))

    view = build_cv_view(model, resolver)
    stay = next(
        item for item in view["core"]["research_stays"]["items"] if item["id"] == "stay_01"
    )
    stay_record = stay["record"]

    assert [item["id"] for item in stay_record["resolved"]["grant_ids"]] == ["grant_02"]
    assert [item["id"] for item in stay_record["related_grants"]] == ["grant_02"]


def test_build_cv_view_adds_derived_honors_and_grants() -> None:
    model = load_cv_model(Path("cv_models/academic_rich.toml"))
    resolver = PortfolioResolver(load_data(Path("data")))

    view = build_cv_view(model, resolver)
    degree = next(
        item for item in view["core"]["education"]["items"] if item["id"] == "degree_01"
    )
    position = next(
        item for item in view["core"]["experience"]["items"] if item["id"] == "position_04"
    )

    assert [item["id"] for item in degree["record"]["related_honors"]] == [
        "award_03",
        "award_02",
    ]
    assert [item["id"] for item in position["record"]["related_grants"]] == ["grant_01"]


def test_build_cv_view_adds_rich_web_snapshots() -> None:
    model = load_cv_model(Path("cv_models/academic_rich.toml"))
    resolver = PortfolioResolver(load_data(Path("data")))

    view = build_cv_view(model, resolver)
    rich_view = view["rich_view"]
    site = rich_view["site"]
    snapshots = rich_view["snapshots"]

    assert "site" not in view
    assert "cv_charts" not in view
    assert "sober_view" not in view
    assert site["publication_chart"]
    assert site["publication_chart"][0]["year"] == "2025"
    assert site["publication_chart"][0]["total"] == 3
    assert site["software_timeline"]["rows"]
    assert site["software_language_chart"]
    assert site["collaborations"]["metrics"]["international_papers"] >= 1
    assert site["career_timeline"]["items"]
    assert site["teaching_hours_chart"]["by_academic_year"]
    assert snapshots["publications"]["chart"] == site["publication_chart"]
    assert snapshots["software"]["timeline"] == site["software_timeline"]
    assert snapshots["teaching"]["hours_chart"] == site["teaching_hours_chart"]


def test_build_cv_view_exposes_core_and_aggregate_blocks() -> None:
    model = load_cv_model(Path("cv_models/academic_rich.toml"))
    resolver = PortfolioResolver(load_data(Path("data")))

    view = build_cv_view(model, resolver)

    assert set(view["core"]) >= {
        "profile",
        "education",
        "experience",
        "research_stays",
        "honors",
        "grants",
        "publications",
        "research_projects",
    }
    assert set(view["aggregates"]) >= {
        "software",
        "teaching",
        "dissemination",
        "reviewing",
        "highlights",
    }
    assert "publications" not in view
    assert "site" not in view
    assert "cv_charts" not in view
    assert view["aggregates"]["software"]["summary"]["metrics"]
    assert view["aggregates"]["teaching"]["summary"]["metrics"]
    assert view["aggregates"]["dissemination"]["summary"]["metrics"]


def test_sober_cv_view_exposes_atomic_data_without_visual_snapshots() -> None:
    view = _load_cv_view("academic_sober")
    sober_view = view["sober_view"]

    assert "rich_view" not in view
    assert "site" not in view
    assert "cv_charts" not in view
    assert sober_view["atomic_sections"]["publications"] == view["core"]["publications"]["items"]
    assert sober_view["atomic_sections"]["research_projects"] == view["core"]["research_projects"]["items"]
    assert sober_view["experience_groups"] == view["core"]["experience"]["groups"]
    assert sober_view["aggregate_sections"]["software_projects"] == (
        view["aggregates"]["software"]["projects"]["items"]
    )
    assert all("css_class" not in item for item in sober_view["atomic_sections"]["degrees"])
    assert all("css_class" not in item for item in sober_view["atomic_sections"]["publications"])


def test_build_cv_view_adds_summary_levels() -> None:
    view = _load_cv_view("academic_rich")
    summary = view["summary"]

    assert summary["active_level"] == "full"
    assert set(summary["levels"]) == {"full", "compact", "micro"}
    assert summary["summary_full"]["level"] == "full"
    assert summary["summary_compact"]["level"] == "compact"
    assert summary["summary_micro"]["level"] == "micro"
    assert len(summary["summary_full"]["paragraphs"]) > len(
        summary["summary_compact"]["paragraphs"]
    )
    assert len(summary["summary_compact"]["paragraphs"]) > len(
        summary["summary_micro"]["paragraphs"]
    )
    assert "Researcher in artificial intelligence and bioinformatics" in summary["active"]["text"]
    assert "Package usage records" in summary["summary_full"]["text"]


def test_sober_cv_groups_experience_by_institution() -> None:
    view = _load_cv_view("academic_sober")
    groups = view["core"]["experience"]["groups"]

    khaos_group = next(group for group in groups if group["title"] == "Khaos Research")

    assert [role["entry"]["id"] for role in khaos_group["roles"]] == [
        "position_05",
        "position_03",
        "position_02",
    ]
    assert khaos_group["period"] == "2021-07 - Present"
    assert khaos_group["location"] == "Málaga, Andalusia, Spain"
    assert (
        khaos_group["progression"]
        == "Associate Team Coordinator <- Associate Software Engineer <- Junior Software Engineer"
    )


@pytest.mark.parametrize("model_name", DEFINITIVE_CV_MODELS)
def test_cv_models_keep_all_core_records(model_name: str) -> None:
    view = _load_cv_view(model_name)
    reference_view = _load_cv_view("academic_rich")

    for block_name, records_for_block in CORE_BLOCKS.items():
        assert _ids(records_for_block(view)) == _ids(records_for_block(reference_view)), block_name


def test_cv_model_uses_editorial_schema() -> None:
    model = load_cv_model(Path("cv_models/academic_rich.toml"))

    assert model.style == "rich"
    assert model.page_limit is None
    assert model.template_name == "rich.html.j2"
    assert model.density == "normal"
    assert model.font_scale == "normal"
    assert model.sections["publications"] == "full"
    assert model.sections["research_projects"] == "full"
    assert model.layout["include_charts"] is True
    assert model.limits == {}


def test_cv_models_do_not_limit_nuclear_records() -> None:
    for model_path in _cv_model_paths():
        model = load_cv_model(model_path)

        assert NUCLEAR_LIMIT_OPTIONS.isdisjoint(model.limits)


def test_definitive_cv_models_exist() -> None:
    models = {model_path.stem: load_cv_model(model_path) for model_path in _cv_model_paths()}

    assert set(models) == set(DEFINITIVE_CV_MODELS)
    assert models["academic_rich"].style == "rich"
    assert models["academic_rich"].density == "normal"
    assert models["academic_rich"].font_scale == "normal"
    assert models["academic_rich"].page_limit is None
    assert models["academic_sober"].style == "sober"
    assert models["academic_sober"].sections["experience"] == "full"
    assert models["academic_sober"].sections["publications"] == "full"
    assert models["academic_sober"].layout["include_charts"] is False
    assert models["academic_sober"].layout["include_dashboard"] is False
    assert models["academic_sober"].layout["include_profile_section"] is True
    assert models["academic_sober"].page_limit is None


def test_cv_templates_are_editorially_separated() -> None:
    rich_model = load_cv_model(Path("cv_models/academic_rich.toml"))
    sober_model = load_cv_model(Path("cv_models/academic_sober.toml"))
    components_root = CV_TEMPLATE_ROOT / "components"

    assert rich_model.template_name == "rich.html.j2"
    assert sober_model.template_name == "sober.html.j2"
    assert (components_root / "common").is_dir()
    assert (components_root / "rich").is_dir()
    assert (components_root / "sober").is_dir()
    assert not list(components_root.glob("*.j2"))

    rich_root = (CV_TEMPLATE_ROOT / rich_model.template_name).read_text(encoding="utf-8")
    sober_root = (CV_TEMPLATE_ROOT / sober_model.template_name).read_text(encoding="utf-8")

    assert "components/rich/" in rich_root
    assert "components/sober/" not in rich_root
    assert "components/sober/" in sober_root
    assert "components/rich/" not in sober_root

    for template_path in (components_root / "rich").glob("*.j2"):
        assert "components/sober/" not in template_path.read_text(encoding="utf-8")

    for template_path in (components_root / "sober").glob("*.j2"):
        assert "components/rich/" not in template_path.read_text(encoding="utf-8")


def test_cv_css_is_editorially_separated() -> None:
    common_css = Path("assets/cv/common.css").read_text(encoding="utf-8")
    rich_css = Path("assets/cv/rich.css").read_text(encoding="utf-8")
    sober_css = Path("assets/cv/sober.css").read_text(encoding="utf-8")

    assert not Path("assets/cv/cv.css").exists()
    assert ".cv-density-compact" in common_css
    assert ".cv-dashboard" not in common_css
    assert ".cv-card-grid" not in common_css
    assert ".sober-" not in common_css
    assert ".cv-style-rich" in rich_css
    assert ".cv-dashboard" in rich_css
    assert ".cv-card-grid" in rich_css
    assert ".sober-" not in rich_css
    assert ".cv-style-sober" not in rich_css
    assert ".cv-style-sober" in sober_css
    assert ".sober-section" in sober_css
    assert ".sober-field" in sober_css
    assert ".cv-dashboard" not in sober_css
    assert ".cv-card-grid" not in sober_css
    assert ".cv-style-rich" not in sober_css


def test_cv_implementation_has_no_data_specific_literals_or_record_ids() -> None:
    record_id_pattern = re.compile(
        r"\b(?:award|degree|grant|organization|position|publication|software|stay)_\d{2}\b"
    )
    data_specific_terms = _portfolio_specific_terms()

    for path in _active_cv_text_files():
        content = path.read_text(encoding="utf-8")

        assert record_id_pattern.search(content) is None, path
        for term in data_specific_terms:
            assert term not in content, path


def test_generate_cv_writes_html(tmp_path: Path) -> None:
    output = generate_cv(output_dir=tmp_path, output_format="html")
    parser = _parse_cv_html(output.content)

    assert output.output_path == tmp_path / "academic_rich.html"
    assert output.html_path == tmp_path / "academic_rich.html"
    assert output.output_path.exists()
    assert tmp_path / "assets" / "common.css" in output.asset_paths
    assert tmp_path / "assets" / "rich.css" in output.asset_paths
    assert tmp_path / "assets" / "sober.css" in output.asset_paths
    assert tmp_path / "assets" / "profile.jpg" in output.asset_paths
    assert (tmp_path / "assets" / "common.css").exists()
    assert (tmp_path / "assets" / "rich.css").exists()
    assert not (tmp_path / "assets" / "cv.css").exists()
    assert (tmp_path / "assets" / "profile.jpg").exists()
    common_css = _read_cv_asset(tmp_path, "common.css")
    rich_css = _read_cv_asset(tmp_path, "rich.css")
    sober_css = _read_cv_asset(tmp_path, "sober.css")
    assert "@page" in common_css
    assert "print-color-adjust" in common_css
    assert "--cv-font-size" in common_css
    assert "--cv-line-height" in common_css
    assert "--cv-section-gap" in common_css
    assert "--cv-card-padding" in common_css
    assert ".cv-density-compact" in common_css
    assert ".cv-density-micro" in common_css
    assert ".cv-font-scale-xsmall" in common_css
    assert "overflow-wrap: anywhere" in common_css
    assert ".cv-style-rich" in rich_css
    assert ".cv-dashboard" in rich_css
    assert ".cv-card-grid" in rich_css
    assert ".cv-style-sober" in sober_css
    assert ".sober-field" in sober_css
    assert '<link rel="stylesheet" href="assets/common.css">' in output.content
    assert '<link rel="stylesheet" href="assets/rich.css">' in output.content
    assert '<link rel="stylesheet" href="assets/sober.css">' not in output.content
    assert (
        'class="cv-document cv-style-rich cv-density-normal cv-font-scale-normal"'
        in output.content
    )
    assert 'class="cv-cover cv-cover-with-photo"' in output.content
    assert 'src="assets/profile.jpg"' in output.content
    assert "<h1>Adrián Segura Ortiz</h1>" in output.content
    assert "Academic Portfolio" in output.content
    assert 'data-summary-level="full"' in output.content
    assert "<h2>Portfolio Summary</h2>" in output.content
    assert "My academic background comprises" in output.content
    assert 'class="cv-summary"' not in output.content
    assert "<h2>Research Stays and Publication Cities</h2>" in output.content
    assert "<h2>Publications</h2>" in output.content
    assert "Journal paper" in output.content
    assert "Conference paper" in output.content
    assert 'class="cv-chip-list"' in output.content
    assert "cv-dashboard" in output.content
    assert "cv-chart-grid" in output.content
    assert "Publications by Year" in output.content
    assert "Commit Activity" in output.content
    assert "Languages" in output.content
    assert "<h2>Software</h2>" in output.content
    assert "<h2>Academic Trajectory</h2>" in output.content
    assert "<h2>Research and Teaching Innovation Projects</h2>" in output.content
    assert "<h2>Classes and Supervision</h2>" in output.content
    assert "Classroom Hours by Academic Year" in output.content
    assert "Classroom Hours by Degree Programme" in output.content
    assert "<h2>Dissemination and Media</h2>" in output.content
    assert "By Research Output" in output.content
    assert "<h2>Organizations</h2>" in output.content
    assert "Visual Summary" not in output.content
    assert "<h2>Current Activity</h2>" not in output.content
    assert "<h2>Reviewing</h2>" not in output.content
    assert "<h3>Journal Papers</h3>" not in output.content
    assert "<h3>Conference Papers</h3>" not in output.content
    assert "Gene regulatory network inference" in output.content
    assert '<a href="https://hub.docker.com/u/adriansegura99">Docker Hub</a>' in output.content
    assert '<a href="https://www.uma.es/">Universidad de Málaga</a>' in output.content
    assert '<span id="position_04" class="cv-anchor"></span>' in output.content
    assert "PhD candidate - FPU Fellowship" in output.content
    assert 'href="#grant_02"' in output.content
    assert "External internship tutoring" in output.content
    assert "External extracurricular internship tutoring" in output.content
    assert "MOEBA-BIO" in output.content
    assert "@nath.biohack, @adriansegura.99" in output.content
    assert parser.stylesheets == ["assets/common.css", "assets/rich.css"]
    assert "undefined" not in output.content
    assert "null" not in output.content


def test_rich_cv_follows_web_equivalent_editorial_contract(tmp_path: Path) -> None:
    output = generate_cv(
        model="academic_rich",
        output_dir=tmp_path,
        output_format="html",
    )
    parser = _parse_cv_html(output.content)
    chart_titles = _chart_card_titles(output.content)

    assert output.model.template_name == "rich.html.j2"
    assert output.model.style == "rich"
    assert parser.stylesheets == ["assets/common.css", "assets/rich.css"]
    assert "cv-style-rich" in parser.classes
    assert "cv-dashboard" in parser.classes
    assert "cv-card-grid" in parser.classes
    assert "cv-chart-card" in parser.classes
    assert "cv-overview-copy" in parser.classes
    assert "Researcher in artificial intelligence and bioinformatics" in output.content
    _assert_ordered_subset(parser.h2, RICH_WEB_SECTIONS)
    assert set(chart_titles) <= RICH_WEB_CHART_TITLES
    assert {
        "Publications by Year",
        "Commit Activity",
        "Languages",
        "Classroom Hours by Academic Year",
        "Classroom Hours by Degree Programme",
    } <= set(chart_titles)
    assert "Visual Summary" not in output.content
    assert "Activity Mix" not in output.content
    assert "Research Domains" not in output.content


def test_generate_cv_writes_formal_full_sober_html(tmp_path: Path) -> None:
    output = generate_cv(
        model="academic_sober",
        output_dir=tmp_path,
        output_format="html",
    )

    assert output.model.name == "academic_sober"
    assert output.model.style == "sober"
    assert output.output_path == tmp_path / "academic_sober.html"
    parser = _parse_cv_html(output.content)

    assert parser.stylesheets == ["assets/common.css", "assets/sober.css"]
    assert '<link rel="stylesheet" href="assets/common.css">' in output.content
    assert '<link rel="stylesheet" href="assets/sober.css">' in output.content
    assert '<link rel="stylesheet" href="assets/rich.css">' not in output.content
    assert (
        'class="cv-document cv-style-sober cv-sober-document cv-density-normal cv-font-scale-normal"'
        in output.content
    )
    assert 'data-summary-level="full"' in output.content
    assert "<h2>Summary</h2>" in output.content
    assert "Researcher in artificial intelligence and bioinformatics" in output.content
    assert "My academic background comprises" in output.content
    assert "<h2>Academic Profile</h2>" not in output.content
    assert "<h3>Research Areas</h3>" not in output.content
    assert "<h3>Profiles and Identifiers</h3>" not in output.content
    assert 'class="cv-dashboard"' not in output.content
    assert 'class="cv-chart-grid"' not in output.content
    assert 'class="cv-card-grid"' not in output.content
    assert 'class="cv-chip-list"' not in output.content
    assert 'class="cv-entry ' not in output.content
    assert "Visual Summary" not in output.content
    assert "Selected Highlights" not in output.content
    assert 'class="cv-cover cv-cover-with-photo"' not in output.content
    assert 'src="assets/profile.jpg"' not in output.content
    assert "Designed evolutionary algorithms" in output.content
    assert "Institution:" in output.content
    assert 'class="sober-experience-group"' in output.content
    assert "Associate Team Coordinator &lt;- Associate Software Engineer" in output.content
    assert "<h2>Current Activity</h2>" not in output.content
    assert "<h2>Education</h2>" in output.content
    assert "2017-10 - 2021-07" in output.content
    assert "<h2>Experience</h2>" in output.content
    assert "<h2>Research Stays</h2>" in output.content
    assert "<h2>Software</h2>" in output.content
    assert "<h2>Research Projects</h2>" in output.content
    assert "<h2>Teaching</h2>" in output.content
    assert "<h2>Dissemination</h2>" in output.content
    assert "<h2>Reviewing</h2>" in output.content
    assert "<h2>Certifications</h2>" in output.content
    assert "<h2>Honors</h2>" in output.content
    assert "<h2>Grants</h2>" in output.content
    assert "Authors:" in output.content
    assert "Journal:" in output.content
    assert "Conference:" in output.content
    assert "Venue:" not in output.content


def test_sober_cv_follows_institutional_editorial_contract(tmp_path: Path) -> None:
    output = generate_cv(
        model="academic_sober",
        output_dir=tmp_path,
        output_format="html",
    )
    parser = _parse_cv_html(output.content)
    forbidden_classes = {
        "cv-dashboard",
        "cv-chart-card",
        "cv-chart-grid",
        "cv-card-grid",
        "cv-chip-list",
        "cv-cover",
        "cv-entry",
    }

    assert output.model.template_name == "sober.html.j2"
    assert output.model.style == "sober"
    assert parser.stylesheets == ["assets/common.css", "assets/sober.css"]
    assert "cv-style-sober" in parser.classes
    assert "sober-section" in parser.classes
    assert "sober-field" in parser.classes
    assert "sober-experience-group" in parser.classes
    assert forbidden_classes.isdisjoint(parser.classes)
    assert _chart_card_titles(output.content) == []
    assert "Researcher in artificial intelligence and bioinformatics" in output.content
    assert "Research Focus" not in output.content
    assert "Research Areas" not in output.content
    assert "Areas of Specialization" not in output.content
    assert "Visual Summary" not in output.content
    assert "Selected Highlights" not in output.content
    assert "Associate Team Coordinator &lt;- Associate Software Engineer" in output.content
    _assert_ordered_subset(parser.h2, SOBER_ATOMIC_SECTIONS)
    _assert_core_record_anchors(output.content, _load_cv_view("academic_rich"))


def test_sober_page_limits_select_summary_level(tmp_path: Path) -> None:
    compact_output = generate_cv(
        model="academic_sober",
        output_dir=tmp_path / "compact",
        output_format="html",
        page_limit=4,
    )
    micro_output = generate_cv(
        model="academic_sober",
        output_dir=tmp_path / "micro",
        output_format="html",
        page_limit=3,
    )

    assert compact_output.model.page_limit == 4
    assert micro_output.model.page_limit == 3
    assert 'data-summary-level="compact"' in compact_output.content
    assert 'data-summary-level="micro"' in micro_output.content
    assert "Researcher in artificial intelligence and bioinformatics" in compact_output.content
    assert "Researcher in artificial intelligence and bioinformatics" in micro_output.content
    assert "My academic background" in compact_output.content
    assert "My academic background" not in micro_output.content


def test_cv_models_generate_html_with_required_assets(tmp_path: Path) -> None:
    for model_path in _cv_model_paths():
        output = generate_cv(
            model=str(model_path),
            output_dir=tmp_path / model_path.stem,
            output_format="html",
        )
        parser = _parse_cv_html(output.content)

        assert output.output_path.exists()
        assert output.html_path.exists()
        assert output.html_path.parent / "assets" / "common.css" in output.asset_paths
        assert output.html_path.parent / "assets" / "rich.css" in output.asset_paths
        assert output.html_path.parent / "assets" / "sober.css" in output.asset_paths
        assert output.html_path.parent / "assets" / "profile.jpg" in output.asset_paths
        assert all(path.exists() for path in output.asset_paths)
        assert parser.stylesheets == [
            "assets/common.css",
            f"assets/{output.model.style}.css",
        ]
        assert "cv-document" in output.content
        assert "<h1>Adrián Segura Ortiz</h1>" in output.content


@pytest.mark.parametrize("model_name", DEFINITIVE_CV_MODELS)
def test_cv_models_generate_pdf_with_page_contracts(tmp_path: Path, model_name: str) -> None:
    output = generate_cv(
        model=model_name,
        output_dir=tmp_path / model_name,
        output_format="pdf",
    )

    assert output.output_path == tmp_path / model_name / f"{model_name}.pdf"
    assert output.html_path == tmp_path / model_name / f"{model_name}.html"
    assert output.output_path.exists()
    assert output.html_path.exists()
    assert output.output_path.read_bytes().startswith(b"%PDF")
    assert output.page_count is not None
    assert output.page_limit is None
    assert output.fit_status == "not_limited"


def test_cv_internal_anchor_links_resolve(tmp_path: Path) -> None:
    output = generate_cv(output_dir=tmp_path, output_format="html")
    parser = _parse_cv_html(output.content)
    ids = set(parser.ids)

    assert len(parser.ids) == len(ids)
    assert parser.internal_hrefs
    assert set(parser.internal_hrefs) <= ids


def test_generate_cv_writes_pdf(tmp_path: Path) -> None:
    output = generate_cv(output_dir=tmp_path)

    assert output.output_path == tmp_path / "academic_rich.pdf"
    assert output.html_path == tmp_path / "academic_rich.html"
    assert output.output_path.exists()
    assert output.html_path.exists()
    assert tmp_path / "assets" / "common.css" in output.asset_paths
    assert tmp_path / "assets" / "rich.css" in output.asset_paths
    assert tmp_path / "assets" / "sober.css" in output.asset_paths
    assert tmp_path / "assets" / "profile.jpg" in output.asset_paths
    assert output.output_path.read_bytes().startswith(b"%PDF")
    assert output.output_path.stat().st_size > 50_000
    assert output.page_count is not None
    assert output.page_limit is None
    assert output.fit_status == "not_limited"
    assert '<link rel="stylesheet" href="assets/common.css">' in output.content
    assert '<link rel="stylesheet" href="assets/rich.css">' in output.content


def test_generate_cv_compresses_until_it_fits_page_limit(tmp_path: Path) -> None:
    output = generate_cv(
        model="academic_sober",
        output_dir=tmp_path,
        output_format="pdf",
        page_limit=99,
    )

    assert output.output_path == tmp_path / "academic_sober_99p.pdf"
    assert output.html_path == tmp_path / "academic_sober_99p.html"
    assert output.page_limit == 99
    assert output.page_count is not None
    assert output.page_count <= output.page_limit
    assert output.fit_status == "fits"
    if output.model.layout.get("compression_stage"):
        assert f'cv-fit-{output.model.layout["compression_stage"]}' in output.content
    assert "<h2>Publications</h2>" in output.content
    assert "<h2>Experience</h2>" in output.content
    assert "<h2>Research Stays</h2>" in output.content
    assert "<h2>Honors</h2>" in output.content
    assert "<h2>Grants</h2>" in output.content


@pytest.mark.parametrize(
    ("page_limit", "summary_level"),
    [
        (4, "compact"),
        (3, "micro"),
    ],
)
def test_sober_page_limited_pdfs_fit_without_dropping_core_records(
    tmp_path: Path,
    page_limit: int,
    summary_level: str,
) -> None:
    output = generate_cv(
        model="academic_sober",
        output_dir=tmp_path / f"{page_limit}p",
        output_format="pdf",
        page_limit=page_limit,
    )

    assert output.page_limit == page_limit
    assert output.page_count is not None
    assert output.page_count <= page_limit
    assert output.fit_status == "fits"
    assert f'data-summary-level="{summary_level}"' in output.content
    _assert_core_record_anchors(output.content, _load_cv_view("academic_rich"))


def test_page_limit_failure_reports_core_contributors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_pdf_export(_html_path: Path, output_path: Path) -> int:
        output_path.write_bytes(b"%PDF-1.4\n/Type /Page\n%%EOF")
        return 99

    monkeypatch.setattr(cv_module, "_export_pdf_from_html", fake_pdf_export)

    with pytest.raises(RuntimeError) as error:
        generate_cv(
            model="academic_sober",
            output_dir=tmp_path,
            output_format="pdf",
            page_limit=3,
        )

    message = str(error.value)
    assert "academic_sober cannot fit all required core records in 3 pages." in message
    assert "Minimum compact render requires 99 pages." in message
    assert "Largest contributors:" in message
    assert "- publications:" in message


def test_dynamic_page_limits_are_sober_only(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="only supported for sober CV models"):
        generate_cv(
            model="academic_rich",
            output_dir=tmp_path,
            output_format="html",
            page_limit=4,
        )
