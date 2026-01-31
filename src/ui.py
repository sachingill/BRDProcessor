import json
import sys
from io import BytesIO

import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from jsonschema import validate, ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.orchestrator import run_pipeline
from src.parser import parse_brd_text


env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

st.set_page_config(page_title="BRD-to-Engineering (Python)", layout="wide")
st.title("BRD-to-Engineering System Generator (Python)")
st.caption("UI build: v2-debug-enabled")

with st.sidebar:
    st.header("Upload BRD")
    brd_file = st.file_uploader("BRD file (.md/.txt)", type=["md", "txt"])
    st.info("PDF parsing not enabled in the Python version yet.")
    process = st.button("Process")


def read_text(file_obj: BytesIO) -> str:
    return file_obj.getvalue().decode("utf-8", errors="ignore")

def load_schema(name: str) -> dict:
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / name
    return json.loads(schema_path.read_text(encoding="utf-8"))

def compute_parser_metrics(brd_sections: dict) -> dict:
    sections = brd_sections.get("sections", {})
    non_empty = 0
    total = 0
    for key, value in sections.items():
        total += 1
        if isinstance(value, str) and value.strip():
            non_empty += 1
        if isinstance(value, list) and len(value) > 0:
            non_empty += 1
    coverage_pct = round((non_empty / total) * 100, 1) if total else 0.0
    return {
        "non_empty_sections": non_empty,
        "total_sections": total,
        "coverage_pct": coverage_pct,
    }

def validate_schema(payload: dict, schema_name: str) -> dict:
    try:
        validate(instance=payload, schema=load_schema(schema_name))
        return {"valid": True, "error": ""}
    except ValidationError as exc:
        return {"valid": False, "error": str(exc).splitlines()[0]}

def compute_quality_metrics(artifacts: dict) -> dict:
    total_fields = 0
    non_empty_fields = 0

    def count_value(value):
        nonlocal total_fields, non_empty_fields
        total_fields += 1
        if isinstance(value, str) and value.strip():
            non_empty_fields += 1
        if isinstance(value, list) and len(value) > 0:
            non_empty_fields += 1

    for key in [
        "engineering_plan",
        "schedule_estimate",
        "solution_architecture",
        "poc_plan",
        "tech_stack_recommendations",
    ]:
        obj = artifacts.get(key, {})
        if isinstance(obj, dict):
            for _, value in obj.items():
                if isinstance(value, dict):
                    for _, nested in value.items():
                        count_value(nested)
                else:
                    count_value(value)

    coverage_pct = round((non_empty_fields / total_fields) * 100, 1) if total_fields else 0.0
    return {"non_empty_fields": non_empty_fields, "total_fields": total_fields, "coverage_pct": coverage_pct}

def compute_faithfulness_metrics(raw_text: str, artifacts: dict) -> dict:
    if not raw_text:
        return {"groundedness_pct": 0.0, "faithfulness_pct": 0.0, "helpfulness_pct": 0.0}
    text = raw_text.lower()
    total_lines = 0
    grounded_lines = 0
    for key in [
        "engineering_plan",
        "schedule_estimate",
        "solution_architecture",
        "poc_plan",
        "tech_stack_recommendations",
    ]:
        obj = artifacts.get(key, {})
        if isinstance(obj, dict):
            for _, value in obj.items():
                if isinstance(value, list):
                    for item in value:
                        total_lines += 1
                        if isinstance(item, str) and item.lower() in text:
                            grounded_lines += 1
                elif isinstance(value, str):
                    total_lines += 1
                    if value and value.lower() in text:
                        grounded_lines += 1
    groundedness_pct = round((grounded_lines / total_lines) * 100, 1) if total_lines else 0.0
    error_count = 0
    for key in [
        "engineering_plan",
        "schedule_estimate",
        "solution_architecture",
        "poc_plan",
        "tech_stack_recommendations",
    ]:
        if isinstance(artifacts.get(key), dict) and artifacts[key].get("_error"):
            error_count += 1
    faithfulness_pct = max(0.0, groundedness_pct - (error_count * 5.0))
    helpfulness = compute_quality_metrics(artifacts).get("coverage_pct", 0.0)
    return {
        "groundedness_pct": groundedness_pct,
        "faithfulness_pct": faithfulness_pct,
        "helpfulness_pct": helpfulness,
    }

if "artifacts" not in st.session_state:
    st.session_state["artifacts"] = None
if "brd_sections" not in st.session_state:
    st.session_state["brd_sections"] = None
if "raw_text" not in st.session_state:
    st.session_state["raw_text"] = ""

if process:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        st.error("OPENAI_API_KEY is not set. Add it to your .env and restart Streamlit.")
        st.stop()
    if api_key in {"YOUR_KEY", "sk-your-key"} or not api_key.startswith("sk-"):
        st.error("OPENAI_API_KEY looks invalid. Update your .env with a real key and restart.")
        st.stop()
    if not brd_file:
        st.warning("Upload a .md or .txt BRD file to continue.")
    else:
        with st.spinner("Processing BRD and generating artifacts..."):
            raw_text = read_text(brd_file)
            brd_sections = parse_brd_text(raw_text)
            artifacts = run_pipeline(brd_sections)
        st.session_state["brd_sections"] = brd_sections
        st.session_state["artifacts"] = artifacts
        st.session_state["raw_text"] = raw_text
        st.success("Artifacts generated.")

if st.session_state.get("brd_sections"):
    st.subheader("Parsed BRD Sections")
    st.json(st.session_state["brd_sections"])
    st.subheader("Parsing Metrics")
    st.json(compute_parser_metrics(st.session_state["brd_sections"]))

if st.session_state.get("artifacts"):
    artifacts = st.session_state["artifacts"]
    errors = []
    debug = artifacts.get("_debug", {})
    for key in [
        "engineering_plan",
        "schedule_estimate",
        "solution_architecture",
        "poc_plan",
        "tech_stack_recommendations",
    ]:
        if isinstance(artifacts.get(key), dict) and artifacts[key].get("_error"):
            errors.append(f"{key}: {artifacts[key]['_error']}")

    if errors:
        st.error("One or more agents failed and returned fallbacks:")
        for err in errors:
            st.write(f"- {err}")
    else:
        st.success("All agents returned non-error outputs.")

    with st.expander("Debug Details (raw agent outputs)"):
        st.json(debug)

    st.subheader("Agent Status")
    status_rows = []
    timings = debug.get("timings", {}) if isinstance(debug, dict) else {}
    for key in [
        "engineering_plan",
        "schedule_estimate",
        "solution_architecture",
        "poc_plan",
        "tech_stack_recommendations",
    ]:
        value = artifacts.get(key, {})
        status = "ok"
        detail = ""
        if isinstance(value, dict) and value.get("_error"):
            status = "error"
            detail = value["_error"]
        timing = timings.get(f"{key}_seconds", "")
        status_rows.append({"agent": key, "status": status, "seconds": timing, "detail": detail})
    st.table(status_rows)

    st.subheader("Schema Validation")
    brd_validation = validate_schema(st.session_state.get("brd_sections", {}), "brd_sections.schema.json")
    plan_validation = validate_schema(artifacts.get("engineering_plan", {}), "engineering_plan.schema.json")
    schedule_validation = validate_schema(artifacts.get("schedule_estimate", {}), "schedule_estimate.schema.json")
    architecture_validation = validate_schema(artifacts.get("solution_architecture", {}), "solution_architecture.schema.json")
    poc_validation = validate_schema(artifacts.get("poc_plan", {}), "poc_plan.schema.json")
    tech_stack_validation = validate_schema(artifacts.get("tech_stack_recommendations", {}), "tech_stack.schema.json")
    st.json(
        {
            "brd_sections": brd_validation,
            "engineering_plan": plan_validation,
            "schedule_estimate": schedule_validation,
            "solution_architecture": architecture_validation,
            "poc_plan": poc_validation,
            "tech_stack_recommendations": tech_stack_validation,
        }
    )

    if isinstance(debug, dict) and debug.get("timings"):
        st.subheader("Latency Metrics")
        total_latency = round(sum(debug["timings"].values()), 3)
        st.json({"total_seconds": total_latency, **debug["timings"]})

    st.subheader("Quality Metrics")
    st.json(compute_quality_metrics(artifacts))

    st.subheader("Faithfulness & Groundedness")
    st.json(compute_faithfulness_metrics(st.session_state.get("raw_text", ""), artifacts))

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Engineering Plan")
        st.json(artifacts.get("engineering_plan", {}))
        st.subheader("Schedule Estimate")
        st.json(artifacts.get("schedule_estimate", {}))
        st.subheader("PoC Plan")
        st.json(artifacts.get("poc_plan", {}))
    with col2:
        st.subheader("Solution Architecture")
        st.json(artifacts.get("solution_architecture", {}))
        st.subheader("Tech Stack Recommendations")
        st.json(artifacts.get("tech_stack_recommendations", {}))

    st.download_button(
        "Download JSON",
        data=json.dumps(artifacts, indent=2),
        file_name="brd_artifacts.json",
        mime="application/json",
    )
