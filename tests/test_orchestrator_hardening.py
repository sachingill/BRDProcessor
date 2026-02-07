import unittest
import types
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

if "openai" not in sys.modules:
    openai_stub = types.ModuleType("openai")

    class _OpenAI:
        pass

    openai_stub.OpenAI = _OpenAI
    sys.modules["openai"] = openai_stub

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")

    def _load_dotenv(*_args, **_kwargs):
        return None

    dotenv_stub.load_dotenv = _load_dotenv
    sys.modules["dotenv"] = dotenv_stub

if "jsonschema" not in sys.modules:
    jsonschema_stub = types.ModuleType("jsonschema")

    class ValidationError(Exception):
        pass

    def _validate_type(instance, expected_type, path):
        if expected_type == "object" and not isinstance(instance, dict):
            raise ValidationError(f"{path} expected object")
        if expected_type == "array" and not isinstance(instance, list):
            raise ValidationError(f"{path} expected array")
        if expected_type == "string" and not isinstance(instance, str):
            raise ValidationError(f"{path} expected string")
        if expected_type == "number" and not isinstance(instance, (int, float)):
            raise ValidationError(f"{path} expected number")

    def _validate(instance, schema, path="$"):
        expected_type = schema.get("type")
        if expected_type:
            _validate_type(instance, expected_type, path)
        if expected_type == "object":
            for key in schema.get("required", []):
                if key not in instance:
                    raise ValidationError(f"{path}.{key} missing")
            properties = schema.get("properties", {})
            for key, value in instance.items():
                if key in properties:
                    _validate(value, properties[key], f"{path}.{key}")
        if expected_type == "array":
            min_items = schema.get("minItems")
            if min_items is not None and len(instance) < min_items:
                raise ValidationError(f"{path} minItems not met")
            item_schema = schema.get("items")
            if item_schema:
                for idx, item in enumerate(instance):
                    _validate(item, item_schema, f"{path}[{idx}]")

    def validate(instance, schema):
        _validate(instance, schema)

    jsonschema_stub.ValidationError = ValidationError
    jsonschema_stub.validate = validate
    sys.modules["jsonschema"] = jsonschema_stub

from src.orchestrator import PipelineExecutionError, run_pipeline


VALID_BRD_SECTIONS = {
    "schema": "brd_sections_v1",
    "sections": {
        "problem": "Manual ticket triage is slow.",
        "objectives": ["Reduce triage time"],
        "functional_requirements": ["Classify severity"],
        "non_functional_requirements": ["99.9% uptime"],
        "constraints": ["Deploy on AWS"],
        "dependencies": [],
        "assumptions": [],
    },
}

VALID_PLAN = {
    "project_overview": "Automate ticket triage.",
    "phases": [
        {
            "name": "Phase 1",
            "objectives": ["Ship MVP"],
            "key_deliverables": ["Prototype"],
            "dependencies": [],
            "acceptance_criteria": ["Reviewed"],
        }
    ],
    "team_composition": [{"role": "Engineer", "count": 1, "notes": "Builds MVP"}],
    "risks": [{"risk": "API outage", "impact": "Delay", "mitigation": "Retries"}],
    "assumptions": [],
}

VALID_SCHEDULE = {
    "timeline_weeks": 4,
    "phases": [{"name": "Phase 1", "duration_weeks": 4, "key_activities": ["Build"]}],
    "resource_matrix": [{"role": "Engineer", "count": 1, "allocation_percent": 100}],
    "assumptions": [],
    "notes": [],
}

VALID_ARCHITECTURE = {
    "summary": "Simple service architecture.",
    "components": [{"name": "Classifier", "responsibility": "Classify tickets", "interfaces": ["API"]}],
    "data_flows": [{"from": "Input", "to": "Classifier", "description": "Forward ticket"}],
    "non_functional_considerations": ["99.9% uptime"],
    "open_questions": [],
}

VALID_POC = {
    "poc_goal": "Validate basic ticket routing.",
    "in_scope_components": ["Classifier"],
    "out_of_scope": [],
    "success_criteria": ["Routes tickets correctly"],
    "timeline_weeks": 2,
    "risks": ["Limited sample size"],
}

VALID_TECH_STACK = {
    "options": [
        {
            "name": "Option A",
            "stack": {
                "frontend": "React",
                "backend": "FastAPI",
                "database": "PostgreSQL",
                "infra": "AWS",
                "observability": "CloudWatch",
            },
            "pros": ["Fast"],
            "cons": ["Learning curve"],
            "fit_notes": "Good default.",
        }
    ],
    "recommendation": "Option A",
}


class TestOrchestratorHardening(unittest.TestCase):
    @patch("src.orchestrator.poc_planner", return_value=VALID_POC)
    @patch("src.orchestrator.solution_architect", return_value=VALID_ARCHITECTURE)
    @patch("src.orchestrator.schedule_estimator", return_value=VALID_SCHEDULE)
    @patch("src.orchestrator.eng_plan_generator", return_value=VALID_PLAN)
    def test_tech_stack_uses_org_team_profile(
        self,
        _mock_plan,
        _mock_schedule,
        _mock_architecture,
        _mock_poc,
    ):
        captured = {}

        def _capture_tech_stack(brd_sections, org_team_profile):
            captured["frontend"] = org_team_profile["team_strengths"]["frontend"]
            captured["backend"] = org_team_profile["team_strengths"]["backend"]
            return VALID_TECH_STACK

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.orchestrator.tech_stack_recommender", side_effect=_capture_tech_stack):
                run_pipeline(
                    VALID_BRD_SECTIONS,
                    run_id="team-profile-1",
                    checkpoint_dir=temp_dir,
                    enable_lock=False,
                )
        self.assertIn("React", captured["frontend"])
        self.assertIn("Python", captured["backend"])

    @patch("src.orchestrator.tech_stack_recommender", return_value=VALID_TECH_STACK)
    @patch("src.orchestrator.poc_planner", return_value=VALID_POC)
    @patch("src.orchestrator.solution_architect", return_value=VALID_ARCHITECTURE)
    @patch("src.orchestrator.schedule_estimator", return_value=VALID_SCHEDULE)
    @patch(
        "src.orchestrator.eng_plan_generator",
        side_effect=[{"project_overview": "missing required fields"}, VALID_PLAN],
    )
    def test_retries_invalid_stage_and_succeeds(
        self,
        mock_plan,
        _mock_schedule,
        _mock_architecture,
        _mock_poc,
        _mock_stack,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = run_pipeline(
                VALID_BRD_SECTIONS,
                run_id="run-123",
                max_attempts=2,
                checkpoint_dir=temp_dir,
                enable_lock=False,
            )
        self.assertEqual(mock_plan.call_count, 2)
        self.assertEqual(artifacts["_debug"]["attempts"]["engineering_plan"], 2)
        self.assertEqual(artifacts["_debug"]["run"]["run_id"], "run-123")

    @patch("src.orchestrator.tech_stack_recommender", return_value={"options": [], "recommendation": ""})
    @patch("src.orchestrator.poc_planner", return_value=VALID_POC)
    @patch("src.orchestrator.solution_architect", return_value=VALID_ARCHITECTURE)
    @patch("src.orchestrator.schedule_estimator", return_value=VALID_SCHEDULE)
    @patch("src.orchestrator.eng_plan_generator", return_value=VALID_PLAN)
    def test_fail_closed_after_retries(
        self,
        _mock_plan,
        _mock_schedule,
        _mock_architecture,
        _mock_poc,
        mock_stack,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(PipelineExecutionError) as ctx:
                run_pipeline(
                    VALID_BRD_SECTIONS,
                    run_id="run-456",
                    max_attempts=2,
                    checkpoint_dir=temp_dir,
                    enable_lock=False,
                )
        self.assertEqual(mock_stack.call_count, 2)
        self.assertEqual(ctx.exception.stage, "tech_stack_recommendations")
        self.assertEqual(ctx.exception.attempts, 2)
        self.assertEqual(ctx.exception.run_id, "run-456")

    @patch("src.orchestrator.tech_stack_recommender", return_value=VALID_TECH_STACK)
    @patch("src.orchestrator.poc_planner", return_value=VALID_POC)
    @patch("src.orchestrator.solution_architect", return_value=VALID_ARCHITECTURE)
    @patch("src.orchestrator.schedule_estimator", return_value=VALID_SCHEDULE)
    @patch("src.orchestrator.eng_plan_generator", return_value=VALID_PLAN)
    def test_resume_uses_checkpoint_without_rerunning_stages(
        self,
        _mock_plan,
        _mock_schedule,
        _mock_architecture,
        _mock_poc,
        _mock_stack,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_pipeline(
                VALID_BRD_SECTIONS,
                run_id="resume-1",
                checkpoint_dir=temp_dir,
                enable_lock=False,
            )

            with patch("src.orchestrator.eng_plan_generator", side_effect=AssertionError("should not rerun")) as mock_again:
                resumed = run_pipeline(
                    VALID_BRD_SECTIONS,
                    run_id="resume-1",
                    checkpoint_dir=temp_dir,
                    enable_lock=False,
                    resume_from_checkpoint=True,
                )
            self.assertEqual(mock_again.call_count, 0)
            self.assertEqual(resumed["_debug"]["attempts"]["engineering_plan"], 1)
            checkpoint_file = Path(temp_dir) / "resume-1.json"
            checkpoint = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            self.assertEqual(checkpoint["status"], "success")
            self.assertIn("engineering_plan", checkpoint["stages"])

    @patch("src.orchestrator.tech_stack_recommender", return_value=VALID_TECH_STACK)
    @patch("src.orchestrator.poc_planner", return_value=VALID_POC)
    @patch("src.orchestrator.solution_architect", return_value=VALID_ARCHITECTURE)
    @patch("src.orchestrator.schedule_estimator", return_value=VALID_SCHEDULE)
    @patch("src.orchestrator.eng_plan_generator", return_value=VALID_PLAN)
    def test_lock_timeout_fails_fast(
        self,
        _mock_plan,
        _mock_schedule,
        _mock_architecture,
        _mock_poc,
        _mock_stack,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "pipeline.lock"
            lock_path.write_text("occupied", encoding="utf-8")
            with self.assertRaises(PipelineExecutionError) as ctx:
                run_pipeline(
                    VALID_BRD_SECTIONS,
                    run_id="lock-1",
                    lock_path=str(lock_path),
                    checkpoint_dir=temp_dir,
                    lock_timeout_seconds=0.0,
                    lock_poll_seconds=0.01,
                    enable_lock=True,
                )
            self.assertEqual(ctx.exception.stage, "lock")


if __name__ == "__main__":
    unittest.main()
