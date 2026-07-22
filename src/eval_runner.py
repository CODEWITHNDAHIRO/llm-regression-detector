"""
Phase 3, the test runner.

Runs every case in the golden dataset through the classifier concurrently
(async), scores each one on category correctness, and saves the full run
to disk as a timestamped JSON file. This saved file is what Phase 3 step 3
(the diff logic) will compare against the *next* run.
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel

from classifier import classify_email_async
from golden_dataset import load_golden_dataset, GoldenTestCase
from judge import judge_summary

RUNS_DIR = Path(__file__).parent.parent / "reports" / "runs"

# Caps how many API calls are in flight at once. Without this,
# asyncio.gather would fire every case simultaneously -- fine for 18 cases,
# risky for 100+, since the API enforces rate limits per account.
MAX_CONCURRENT_REQUESTS = 5


class CaseResult(BaseModel):
    """One golden dataset case, after being run through the classifier."""
    case_id: str
    email: str
    expected_category: str
    actual_category: str
    category_match: bool
    expected_summary: str
    actual_summary: str
    summary_score: int  # 1-5, from LLM-as-judge
    summary_score_reasoning: str
    difficulty: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


async def run_single_case(
    case: GoldenTestCase, prompt_version: str, semaphore: asyncio.Semaphore
) -> CaseResult:
    """Runs one case through the classifier, gated by the semaphore so we
    never exceed MAX_CONCURRENT_REQUESTS calls in flight at once."""
    async with semaphore:
        run = await classify_email_async(case.email, prompt_version)
        # judge_summary is a blocking (sync) call; run it in a background
        # thread so it doesn't freeze the whole event loop while judging.
        judgment = await asyncio.to_thread(
            judge_summary, case.email, case.expected_summary, run.classification.summary
        )

    return CaseResult(
        case_id=case.id,
        email=case.email,
        expected_category=case.expected_category,
        actual_category=run.classification.category,
        category_match=(run.classification.category == case.expected_category),
        expected_summary=case.expected_summary,
        actual_summary=run.classification.summary,
        summary_score=judgment.score,
        summary_score_reasoning=judgment.reasoning,
        difficulty=case.difficulty,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        latency_ms=run.latency_ms,
    )


async def run_eval(prompt_version: str = "v1") -> list[CaseResult]:
    """Runs the entire golden dataset concurrently and returns all results."""
    cases = load_golden_dataset()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    # Build one coroutine per case, don't await yet -- just describe the work.
    tasks = [run_single_case(case, prompt_version, semaphore) for case in cases]

    # Now run all of them concurrently (respecting the semaphore limit) and
    # wait for every single one to finish before continuing.
    results = await asyncio.gather(*tasks)
    return list(results)


def save_run(results: list[CaseResult], prompt_version: str) -> Path:
    """Persists a run to disk as JSON, so future runs can diff against it."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    run_data = {
        "timestamp": timestamp,
        "prompt_version": prompt_version,
        "results": [r.model_dump() for r in results],
    }

    out_path = RUNS_DIR / f"run_{timestamp}.json"
    out_path.write_text(json.dumps(run_data, indent=2))
    return out_path

if __name__ == "__main__":
    import sys
    prompt_version = sys.argv[1] if len(sys.argv) > 1 else "v1"

    results = asyncio.run(run_eval(prompt_version=prompt_version))

    passed = sum(1 for r in results if r.category_match)
    total = len(results)
    avg_summary_score = sum(r.summary_score for r in results) / total
    print(f"Ran {total} cases against prompt {prompt_version}.")
    print(f"  Category matches: {passed}/{total} ({passed/total:.0%})")
    print(f"  Avg summary score: {avg_summary_score:.2f}/5\n")

    for r in results:
        status = "PASS" if r.category_match else "FAIL"
        print(f"  [{status}] {r.case_id}  category={r.actual_category}  summary_score={r.summary_score}/5")

    out_path = save_run(results, prompt_version=prompt_version)
    print(f"\nSaved run to {out_path}")