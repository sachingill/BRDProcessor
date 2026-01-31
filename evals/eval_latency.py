import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.orchestrator import run_pipeline
from src.parser import parse_brd_text


BASE = Path(__file__).resolve().parent
DATA = BASE / "data"


def main():
    brd_text = (DATA / "brd_001.md").read_text(encoding="utf-8")
    brd_sections = parse_brd_text(brd_text)

    start = time.perf_counter()
    _ = run_pipeline(brd_sections)
    total = time.perf_counter() - start
    print(f"Total pipeline seconds: {total:.2f}")


if __name__ == "__main__":
    main()
