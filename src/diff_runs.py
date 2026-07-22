"""
Phase 3, compare two saved eval runs and produce a diff report.

This is the core value of the whole system: given a baseline run (e.g. the
currently-deployed prompt) and a candidate run (e.g. a proposed prompt
change), identify exactly which cases got worse, which got better, and
whether the overall delta crosses a warning or critical threshold.
"""
import json
import sys
from pathlib import Path
from pydantic import BaseModel

RUNS_DIR = Path(__file__).parent.parent / "reports" / "runs"

# Per the guide: flag as warning if a delta exceeds 3%, critical if it
# exceeds 8%. These are deliberately configurable, not hardcoded assumptions
# about what "significant" means for every use case.
WARNING_THRESHOLD = 0.03
CRITICAL_THRESHOLD = 0.08

# A summary score drop of this many points (out of 5) on an individual case
# counts as a regression on that case, even if its category still matches.
SUMMARY_REGRESSION_THRESHOLD = 2


class CaseDelta(BaseModel):
    case_id: str
    baseline_category_match: bool
    candidate_category_match: bool
    baseline_summary_score: int
    candidate_summary_score: int


class RunDiff(BaseModel):
    baseline_timestamp: str
    candidate_timestamp: str
    baseline_prompt_version: str
    candidate_prompt_version: str

    baseline_pass_rate: float
    candidate_pass_rate: float
    pass_rate_delta: float  # candidate - baseline; negative = got worse

    baseline_avg_summary_score: float
    candidate_avg_summary_score: float
    summary_score_delta: float  # candidate - baseline

    regressed_cases: list[str]   # flipped pass->fail, or summary score dropped a lot
    improved_cases: list[str]    # flipped fail->pass
    unchanged_failures: list[str]  # failed in both runs

    severity: str  # "none", "warning", or "critical"


def load_run(path: Path) -> dict:
    return json.loads(path.read_text())


def find_latest_run_for_version(prompt_version: str) -> Path:
    """Finds the most recent saved run for a given prompt version."""
    candidates = sorted(RUNS_DIR.glob("run_*.json"))
    for path in reversed(candidates):  # newest first, since timestamps sort lexically
        data = load_run(path)
        if data["prompt_version"] == prompt_version:
            return path
    raise FileNotFoundError(f"No saved run found for prompt version '{prompt_version}'")


def compare_runs(baseline_path: Path, candidate_path: Path) -> RunDiff:
    baseline = load_run(baseline_path)
    candidate = load_run(candidate_path)

    baseline_by_id = {r["case_id"]: r for r in baseline["results"]}
    candidate_by_id = {r["case_id"]: r for r in candidate["results"]}

    # Both runs should cover the same golden dataset, so their case_ids
    # should match exactly. If they don't, something upstream changed
    # (e.g. the golden dataset itself) and the diff isn't meaningful.
    if set(baseline_by_id) != set(candidate_by_id):
        raise ValueError(
            "Baseline and candidate runs cover different case sets -- "
            "did the golden dataset change between runs?"
        )

    total = len(baseline_by_id)
    baseline_passed = sum(1 for r in baseline_by_id.values() if r["category_match"])
    candidate_passed = sum(1 for r in candidate_by_id.values() if r["category_match"])
    baseline_pass_rate = baseline_passed / total
    candidate_pass_rate = candidate_passed / total

    baseline_avg_score = sum(r["summary_score"] for r in baseline_by_id.values()) / total
    candidate_avg_score = sum(r["summary_score"] for r in candidate_by_id.values()) / total

    regressed, improved, unchanged_failures = [], [], []

    for case_id in baseline_by_id:
        b = baseline_by_id[case_id]
        c = candidate_by_id[case_id]

        category_regressed = b["category_match"] and not c["category_match"]
        category_improved = (not b["category_match"]) and c["category_match"]
        summary_regressed = (b["summary_score"] - c["summary_score"]) >= SUMMARY_REGRESSION_THRESHOLD

        if category_regressed or summary_regressed:
            regressed.append(case_id)
        elif category_improved:
            improved.append(case_id)
        elif not b["category_match"] and not c["category_match"]:
            unchanged_failures.append(case_id)

    pass_rate_delta = candidate_pass_rate - baseline_pass_rate
    summary_score_delta = candidate_avg_score - baseline_avg_score
    # Normalize the summary score delta onto the same 0-1 scale as pass
    # rate (max possible score is 5) so both deltas can be judged against
    # the same percentage thresholds.
    normalized_summary_delta = summary_score_delta / 5

    worst_delta_magnitude = max(abs(pass_rate_delta), abs(normalized_summary_delta))
    if worst_delta_magnitude >= CRITICAL_THRESHOLD and (pass_rate_delta < 0 or summary_score_delta < 0):
        severity = "critical"
    elif worst_delta_magnitude >= WARNING_THRESHOLD and (pass_rate_delta < 0 or summary_score_delta < 0):
        severity = "warning"
    else:
        severity = "none"

    return RunDiff(
        baseline_timestamp=baseline["timestamp"],
        candidate_timestamp=candidate["timestamp"],
        baseline_prompt_version=baseline["prompt_version"],
        candidate_prompt_version=candidate["prompt_version"],
        baseline_pass_rate=baseline_pass_rate,
        candidate_pass_rate=candidate_pass_rate,
        pass_rate_delta=pass_rate_delta,
        baseline_avg_summary_score=baseline_avg_score,
        candidate_avg_summary_score=candidate_avg_score,
        summary_score_delta=summary_score_delta,
        regressed_cases=regressed,
        improved_cases=improved,
        unchanged_failures=unchanged_failures,
        severity=severity,
    )


def print_diff_report(diff: RunDiff) -> None:
    print(f"Baseline:  {diff.baseline_prompt_version} ({diff.baseline_timestamp})")
    print(f"Candidate: {diff.candidate_prompt_version} ({diff.candidate_timestamp})\n")

    print(f"Category pass rate:  {diff.baseline_pass_rate:.0%} -> {diff.candidate_pass_rate:.0%} "
          f"({diff.pass_rate_delta:+.0%})")
    print(f"Avg summary score:   {diff.baseline_avg_summary_score:.2f} -> {diff.candidate_avg_summary_score:.2f} "
          f"({diff.summary_score_delta:+.2f})\n")

    severity_label = {"none": "OK", "warning": "WARNING", "critical": "CRITICAL"}[diff.severity]
    print(f"Severity: {severity_label}\n")

    if diff.regressed_cases:
        print(f"Regressed cases ({len(diff.regressed_cases)}):")
        for case_id in diff.regressed_cases:
            print(f"  - {case_id}")
    if diff.improved_cases:
        print(f"Improved cases ({len(diff.improved_cases)}):")
        for case_id in diff.improved_cases:
            print(f"  - {case_id}")
    if not diff.regressed_cases and not diff.improved_cases:
        print("No individual case flips detected.")


if __name__ == "__main__":
    # Usage: python src/diff_runs.py v1 v2
    # Compares the latest saved run for each prompt version.
    baseline_version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    candidate_version = sys.argv[2] if len(sys.argv) > 2 else "v2"

    baseline_path = find_latest_run_for_version(baseline_version)
    candidate_path = find_latest_run_for_version(candidate_version)

    diff = compare_runs(baseline_path, candidate_path)
    print_diff_report(diff)