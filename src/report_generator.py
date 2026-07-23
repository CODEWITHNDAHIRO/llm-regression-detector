"""
Phase 4,renders a RunDiff (from diff_runs.py) into a human-readable
HTML report, with full before/after detail for every regressed case.
"""
from pathlib import Path
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader

from diff_runs import (
    RunDiff,
    compare_runs,
    find_latest_run_for_version,
    load_run,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
REPORTS_DIR = Path(__file__).parent.parent / "reports"

SEVERITY_LABELS = {"none": "OK", "warning": "WARNING", "critical": "CRITICAL"}


def _delta_class(delta: float) -> str:
    """Returns a CSS class name based on whether a delta is good, bad, or flat."""
    if delta < 0:
        return "delta-negative"
    if delta > 0:
        return "delta-positive"
    return "delta-neutral"


def _build_case_details(baseline_data: dict, candidate_data: dict, case_ids: list[str]) -> list[dict]:
    """Pulls full before/after detail for a list of case_ids, for display
    in the report table (the diff itself only stores IDs, not full detail)."""
    baseline_by_id = {r["case_id"]: r for r in baseline_data["results"]}
    candidate_by_id = {r["case_id"]: r for r in candidate_data["results"]}

    details = []
    for case_id in case_ids:
        b = baseline_by_id[case_id]
        c = candidate_by_id[case_id]
        details.append({
            "case_id": case_id,
            "email": b["email"],
            "baseline_category": b["actual_category"],
            "candidate_category": c["actual_category"],
            "baseline_summary": b["actual_summary"],
            "candidate_summary": c["actual_summary"],
            "baseline_score": b["summary_score"],
            "candidate_score": c["summary_score"],
        })
    return details


def generate_html_report(baseline_path: Path, candidate_path: Path) -> Path:
    diff = compare_runs(baseline_path, candidate_path)
    baseline_data = load_run(baseline_path)
    candidate_data = load_run(candidate_path)

    regressed_details = _build_case_details(baseline_data, candidate_data, diff.regressed_cases)
    improved_details = _build_case_details(baseline_data, candidate_data, diff.improved_cases)

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("report_template.html")

    html = template.render(
        baseline_prompt_version=diff.baseline_prompt_version,
        candidate_prompt_version=diff.candidate_prompt_version,
        baseline_timestamp=diff.baseline_timestamp,
        candidate_timestamp=diff.candidate_timestamp,
        severity=diff.severity,
        severity_label=SEVERITY_LABELS[diff.severity],
        baseline_pass_rate=f"{diff.baseline_pass_rate:.0%}",
        candidate_pass_rate=f"{diff.candidate_pass_rate:.0%}",
        pass_rate_delta=f"{diff.pass_rate_delta:+.0%}",
        pass_rate_delta_class=_delta_class(diff.pass_rate_delta),
        baseline_avg_summary_score=f"{diff.baseline_avg_summary_score:.2f}",
        candidate_avg_summary_score=f"{diff.candidate_avg_summary_score:.2f}",
        summary_score_delta=f"{diff.summary_score_delta:+.2f}",
        summary_delta_class=_delta_class(diff.summary_score_delta),
        regressed_cases=regressed_details,
        improved_cases=improved_details,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = REPORTS_DIR / f"report_{timestamp}.html"
    out_path.write_text(html)
    return out_path


if __name__ == "__main__":
    import sys
    baseline_version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    candidate_version = sys.argv[2] if len(sys.argv) > 2 else "v2"

    baseline_path = find_latest_run_for_version(baseline_version)
    candidate_path = find_latest_run_for_version(candidate_version)

    out_path = generate_html_report(baseline_path, candidate_path)
    print(f"Report written to {out_path}")
    print("Open it in a browser to view.")