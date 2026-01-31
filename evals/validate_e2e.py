import argparse
import json
import sys
import time
from pathlib import Path

from jsonschema import ValidationError, validate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.orchestrator import run_pipeline
from src.parser import parse_brd_text

BASE = Path(__file__).resolve().parent
SCHEMAS = BASE.parent / "schemas"
DEFAULT_DATA_DIR = BASE / "data"

ARTIFACT_SCHEMAS = {
    "engineering_plan": "engineering_plan.schema.json",
    "schedule_estimate": "schedule_estimate.schema.json",
    "solution_architecture": "solution_architecture.schema.json",
    "poc_plan": "poc_plan.schema.json",
    "tech_stack_recommendations": "tech_stack.schema.json",
}


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def score_list(pred, gold):
    pred_set = {p.strip().lower() for p in pred}
    gold_set = {g.strip().lower() for g in gold}
    if not gold_set:
        return 1.0 if not pred_set else 0.0
    return len(pred_set & gold_set) / len(gold_set)


def score_sections(parsed: dict, expected: dict) -> float | None:
    scores = []
    for key, gold in expected.get("sections", {}).items():
        pred = parsed.get("sections", {}).get(key, [])
        if isinstance(gold, str):
            if not gold.strip():
                scores.append(1.0 if not str(pred).strip() else 0.0)
            else:
                scores.append(1.0 if gold.lower() in str(pred).lower() else 0.0)
        else:
            scores.append(score_list(pred, gold))
    if not scores:
        return None
    return sum(scores) / len(scores)


def load_expected(case_path: Path) -> dict | None:
    expected_path = case_path.with_name(f"{case_path.stem}_expected.json")
    if expected_path.exists():
        return json.loads(expected_path.read_text(encoding="utf-8"))
    return None


def iter_cases(data_dir: Path, pattern: str, explicit_cases: list[str]) -> list[Path]:
    if explicit_cases:
        return [Path(case).expanduser().resolve() for case in explicit_cases]
    return sorted(data_dir.glob(pattern))


def validate_instance(instance: dict, schema_name: str) -> str | None:
    try:
        validate(instance=instance, schema=load_schema(schema_name))
        return None
    except ValidationError as exc:
        return str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="End-to-end BRD processor validator")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Directory with BRD cases")
    parser.add_argument("--pattern", default="brd_*.md", help="Glob pattern for case files")
    parser.add_argument("--case", action="append", default=[], help="Specific case file path")
    parser.add_argument("--min-parser-score", type=float, default=0.6, help="Minimum parser score")
    parser.add_argument("--skip-pipeline", action="store_true", help="Skip pipeline validation")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    parser.add_argument("--cycles", type=int, default=1, help="Number of test cycles to run")
    parser.add_argument("--sleep-seconds", type=float, default=0, help="Pause between cycles")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    cases = iter_cases(data_dir, args.pattern, args.case)
    if not cases:
        print("No cases found.")
        return 1

    failures = 0
    cycles = max(args.cycles, 1)
    for cycle in range(1, cycles + 1):
        print(f"Cycle {cycle}/{cycles}")
        for case_path in cases:
            if not case_path.exists():
                print(f"Missing case: {case_path}")
                failures += 1
                if args.fail_fast:
                    return 1
                continue

            print(f"Case: {case_path.name}")
            brd_text = case_path.read_text(encoding="utf-8")
            parsed = parse_brd_text(brd_text)

            error = validate_instance(parsed, "brd_sections.schema.json")
            if error:
                print(f"  brd_sections_schema: FAIL ({error})")
                failures += 1
                if args.fail_fast:
                    return 1
            else:
                print("  brd_sections_schema: ok")

            expected = load_expected(case_path)
            if expected:
                score = score_sections(parsed, expected)
                if score is None:
                    print("  parser_score: n/a")
                else:
                    print(f"  parser_score: {score:.2f}")
                    if score < args.min_parser_score:
                        print("  parser_score: FAIL")
                        failures += 1
                        if args.fail_fast:
                            return 1
            else:
                print("  parser_score: n/a (no expected file)")

            if args.skip_pipeline:
                continue

            artifacts = run_pipeline(parsed)
            pipeline_errors = []
            for key, schema_name in ARTIFACT_SCHEMAS.items():
                error = validate_instance(artifacts.get(key, {}), schema_name)
                if error:
                    pipeline_errors.append(f"{key}: {error}")
            if pipeline_errors:
                print("  pipeline_schema: FAIL")
                for message in pipeline_errors:
                    print(f"    - {message}")
                failures += 1
                if args.fail_fast:
                    return 1
            else:
                print("  pipeline_schema: ok")
        if args.sleep_seconds > 0 and cycle < cycles:
            time.sleep(args.sleep_seconds)

    if failures:
        print(f"\nValidation failed: {failures} issue(s).")
        return 1
    print("\nValidation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
