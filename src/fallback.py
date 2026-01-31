def brd_sections_fallback() -> dict:
    return {
        "schema": "brd_sections_v1",
        "sections": {
            "problem": "",
            "objectives": [],
            "functional_requirements": [],
            "non_functional_requirements": [],
            "constraints": [],
            "dependencies": [],
            "assumptions": [],
        },
    }


def eng_plan_fallback() -> dict:
    return {
        "project_overview": "",
        "phases": [],
        "team_composition": [],
        "risks": [],
        "assumptions": [],
    }


def schedule_fallback() -> dict:
    return {
        "timeline_weeks": 0,
        "phases": [],
        "resource_matrix": [],
        "assumptions": [],
        "notes": [],
    }


def architecture_fallback() -> dict:
    return {
        "summary": "",
        "components": [],
        "data_flows": [],
        "non_functional_considerations": [],
        "open_questions": [],
    }


def poc_fallback() -> dict:
    return {
        "poc_goal": "",
        "in_scope_components": [],
        "out_of_scope": [],
        "success_criteria": [],
        "timeline_weeks": 0,
        "risks": [],
    }


def tech_stack_fallback() -> dict:
    return {
        "options": [],
        "recommendation": "",
    }
