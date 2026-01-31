import json
import sys
from pathlib import Path

from jsonschema import validate, ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.parser import parse_brd_text


SAMPLE_DIR = ROOT / "sample_inputs"
SCHEMA_PATH = ROOT / "schemas" / "brd_sections.schema.json"
RESULTS_PATH = Path(__file__).resolve().parent / "results" / "parser_batch_results.json"


def compute_coverage(brd_sections: dict) -> dict:
    sections = brd_sections.get("sections", {})
    non_empty = 0
    total = 0
    for _, value in sections.items():
        total += 1
        if isinstance(value, str) and value.strip():
            non_empty += 1
        if isinstance(value, list) and len(value) > 0:
            non_empty += 1
    coverage_pct = round((non_empty / total) * 100, 1) if total else 0.0
    return {"non_empty": non_empty, "total": total, "coverage_pct": coverage_pct}


def main():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    results = []
    for path in sorted(SAMPLE_DIR.glob("sample_brd_*.md")):
        text = path.read_text(encoding="utf-8")
        parsed = parse_brd_text(text)
        coverage = compute_coverage(parsed)
        valid = True
        error = ""
        try:
            validate(instance=parsed, schema=schema)
        except ValidationError as exc:
            valid = False
            error = str(exc).splitlines()[0]
        results.append(
            {
                "file": path.name,
                "schema_valid": valid,
                "schema_error": error,
                "llm_fallback_used": parsed.get("_llm_fallback_used", False),
                "coverage": coverage,
            }
        )

    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote batch results to {RESULTS_PATH}")
    for item in results:
        print(
            f"{item['file']}: schema_valid={item['schema_valid']} "
            f"coverage={item['coverage']['coverage_pct']}% "
            f"llm_fallback={item['llm_fallback_used']}"
        )


if __name__ == "__main__":
    main()
