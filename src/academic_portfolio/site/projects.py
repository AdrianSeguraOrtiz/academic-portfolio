from __future__ import annotations

from typing import Any

from academic_portfolio.render import record_name

def _project_records(
    research_projects: list[dict[str, Any]],
    teaching_projects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    projects = [
        _project_record(
            project,
            project_type="research",
            project_type_label="Research project",
            display_title=_research_project_title(project),
            project_funders=project.get("funders", []),
        )
        for project in research_projects
    ]
    projects.extend(
        _project_record(
            project,
            project_type="teaching",
            project_type_label="Teaching innovation project",
            display_title=project.get("title"),
            project_funders=[project["funding_entity"]] if project.get("funding_entity") else [],
        )
        for project in teaching_projects
    )
    return sorted(projects, key=_project_sort_key, reverse=True)



def _project_record(
    project: dict[str, Any],
    *,
    project_type: str,
    project_type_label: str,
    display_title: Any,
    project_funders: list[Any],
) -> dict[str, Any]:
    item = dict(project)
    item["project_type"] = project_type
    item["project_type_label"] = project_type_label
    item["display_title"] = str(display_title or record_name(project))
    item["project_funders"] = [str(funder) for funder in project_funders if funder]
    item["participation_class"] = _project_participation_class(project.get("participation"))
    return item



def _research_project_title(project: dict[str, Any]) -> str:
    title = str(project.get("title") or record_name(project))
    acronym = str(project.get("acronym") or "").strip()
    return f"{acronym}: {title}" if acronym else title



def _project_participation_class(participation: Any) -> str:
    role_text = str(participation or "").lower()
    normalized_role = f" {role_text.replace('/', ' ').replace('-', ' ').replace('.', ' ')} "
    if (
        "principal investigator" in role_text
        or "investigador principal" in role_text
        or " co pi " in normalized_role
        or " co ip " in normalized_role
        or " pi " in normalized_role
        or " ip " in normalized_role
    ):
        return "lead"
    if "research team" in role_text or "researcher" in role_text:
        return "research"
    return "working"



def _project_sort_key(project: dict[str, Any]) -> tuple[str, str, str]:
    date_value = str(
        project.get("end_date")
        or project.get("start_date")
        or project.get("issue_date")
        or "",
    )
    return (date_value, str(project.get("project_type") or ""), str(project.get("display_title") or ""))
