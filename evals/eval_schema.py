import json
import sys
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.orchestrator import run_pipeline
from src.parser import parse_brd_text


BASE = Path(__file__).resolve().parent
SCHEMAS = BASE.parent / "schemas"
DATA = BASE / "data"


def load_schema(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def main():
    brd_text = (DATA / "brd_001.md").read_text(encoding="utf-8")
    brd_sections = parse_brd_text(brd_text)
    artifacts = run_pipeline(brd_sections)

    validate(instance=brd_sections, schema=load_schema("brd_sections.schema.json"))
    validate(instance=artifacts["engineering_plan"], schema=load_schema("engineering_plan.schema.json"))

    print("Schema validation passed.")


if __name__ == "__main__":
    main()
