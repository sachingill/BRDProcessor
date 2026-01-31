import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.parser import parse_brd_text


BASE = Path(__file__).resolve().parent
DATA = BASE / "data"


def score_list(pred, gold):
    pred_set = {p.strip().lower() for p in pred}
    gold_set = {g.strip().lower() for g in gold}
    if not gold_set:
        return 1.0 if not pred_set else 0.0
    return len(pred_set & gold_set) / len(gold_set)


def main():
    brd_text = (DATA / "brd_001.md").read_text(encoding="utf-8")
    expected = json.loads((DATA / "brd_001_expected.json").read_text(encoding="utf-8"))
    parsed = parse_brd_text(brd_text)

    scores = {}
    for key in expected["sections"]:
        pred = parsed["sections"].get(key, [])
        gold = expected["sections"][key]
        if isinstance(gold, str):
            scores[key] = 1.0 if gold.lower() in str(pred).lower() else 0.0
        else:
            scores[key] = score_list(pred, gold)

    print("Parser scores:")
    for key, score in scores.items():
        print(f"- {key}: {score:.2f}")


if __name__ == "__main__":
    main()
