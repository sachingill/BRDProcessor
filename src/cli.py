import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.parser import parse_brd_text
from src.orchestrator import run_pipeline


def main():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=env_path)
    parser = argparse.ArgumentParser(description="BRD-to-Engineering Generator (Python)")
    parser.add_argument("--input", required=True, help="Path to BRD text/markdown file")
    parser.add_argument("--output", default="output.json", help="Output JSON path")
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    brd_sections = parse_brd_text(text)
    artifacts = run_pipeline(brd_sections)
    Path(args.output).write_text(json.dumps(artifacts, indent=2), encoding="utf-8")
    print(f"Wrote output to {args.output}")


if __name__ == "__main__":
    main()
