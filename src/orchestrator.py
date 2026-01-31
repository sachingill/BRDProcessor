import time

from src.agents import (
    eng_plan_generator,
    schedule_estimator,
    solution_architect,
    poc_planner,
    tech_stack_recommender,
)
from src.guardrails import apply_guardrails


def run_pipeline(brd_sections: dict) -> dict:
    timings = {}
    start = time.perf_counter()
    plan_raw = eng_plan_generator(brd_sections)
    timings["engineering_plan_seconds"] = round(time.perf_counter() - start, 3)
    plan = apply_guardrails(
        plan_raw,
        ["project_overview", "phases", "team_composition", "risks", "assumptions"],
    )
    start = time.perf_counter()
    schedule_raw = schedule_estimator(plan)
    timings["schedule_estimate_seconds"] = round(time.perf_counter() - start, 3)
    schedule = apply_guardrails(
        schedule_raw,
        ["timeline_weeks", "phases", "resource_matrix", "assumptions", "notes"],
    )
    start = time.perf_counter()
    architecture_raw = solution_architect(brd_sections)
    timings["solution_architecture_seconds"] = round(time.perf_counter() - start, 3)
    architecture = apply_guardrails(
        architecture_raw,
        ["summary", "components", "data_flows", "non_functional_considerations", "open_questions"],
    )
    start = time.perf_counter()
    poc_raw = poc_planner(architecture)
    timings["poc_plan_seconds"] = round(time.perf_counter() - start, 3)
    poc = apply_guardrails(
        poc_raw,
        ["poc_goal", "in_scope_components", "out_of_scope", "success_criteria", "timeline_weeks", "risks"],
    )
    start = time.perf_counter()
    tech_stack_raw = tech_stack_recommender(brd_sections)
    timings["tech_stack_seconds"] = round(time.perf_counter() - start, 3)
    tech_stack = apply_guardrails(
        tech_stack_raw,
        ["options", "recommendation"],
    )
    return {
        "brd_sections": brd_sections,
        "engineering_plan": plan,
        "schedule_estimate": schedule,
        "solution_architecture": architecture,
        "poc_plan": poc,
        "tech_stack_recommendations": tech_stack,
        "_debug": {
            "engineering_plan_raw": plan_raw,
            "schedule_estimate_raw": schedule_raw,
            "solution_architecture_raw": architecture_raw,
            "poc_plan_raw": poc_raw,
            "tech_stack_recommendations_raw": tech_stack_raw,
            "timings": timings,
        },
    }
