"""
Loads and validates the hand-labeled golden dataset. See
docs/decisions/003-hand-written-golden-dataset.md for why this data is
human-written rather than LLM-generated.
"""
import json
from pathlib import Path
from typing import Literal
from pydantic import BaseModel

DATASET_PATH = Path(__file__).parent.parent / "eval_data" / "golden_dataset.json"


class GoldenTestCase(BaseModel):
    id: str
    email: str
    expected_category: Literal["billing", "technical", "account", "general"]
    expected_summary: str
    difficulty: Literal["easy", "ambiguous", "edge_case"]
    notes: str  # why this case matters -- forces the author to justify inclusion


def load_golden_dataset() -> list[GoldenTestCase]:
    raw = json.loads(DATASET_PATH.read_text())
    return [GoldenTestCase(**case) for case in raw]


if __name__ == "__main__":
    cases = load_golden_dataset()
    print(f"Loaded {len(cases)} golden test cases.")
    by_difficulty: dict[str, int] = {}
    for c in cases:
        by_difficulty[c.difficulty] = by_difficulty.get(c.difficulty, 0) + 1
    print("Breakdown by difficulty:", by_difficulty)