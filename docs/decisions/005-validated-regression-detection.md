# ADR 005: Validate the diff/severity logic against a real, deliberately induced regression

## Status
Accepted (validated)

## Context
A regression-detection system that has never actually caught a regression is
unproven. Before trusting the severity thresholds (ADR-level decision:
warning at 3% delta, critical at 8%, per the original build spec), we needed
evidence the system correctly flags a real quality drop rather than just
running cleanly on well-behaved inputs.

## Method
Created `prompts/email_classifier_v2.yaml`: a deliberately degraded prompt
with no category definitions and no few-shot examples (vs. `v1`'s full
definitions + examples). Ran the full 18-case golden dataset against both
versions and diffed the results with `src/diff_runs.py`.

## Result
- Category pass rate: 100% (v1) -> 83% (v2), a -17% delta
- Avg summary score: 4.78 -> 4.72 (summary quality held up better than
  categorization -- the model still writes coherent summaries even when
  its categorization taxonomy is undefined)
- Severity correctly escalated to CRITICAL (17% >> 8% threshold)
- 3 specific regressions identified with case-level detail:
  - account-001 (login lockout) misclassified as technical
  - general-002 (sarcastic UI complaint) misclassified as technical
  - general-003 (sales inquiry) misclassified as billing

All three failures are explainable: without explicit category boundaries in
the prompt, the model fell back to topic/keyword association (e.g. "seats"
and "discounts" -> billing) rather than the intended taxonomy. This confirms
the golden dataset's category-boundary test cases (see ADR 003) are doing
real discriminative work, not just padding case count.

## Consequences
- The severity threshold system (3%/8%) is now empirically validated, not
  just implemented on spec.
- This result is the core portfolio evidence for this project: it
  demonstrates the system detects a real regression with the correct
  severity and identifies root-cause-legible failures, not just an
  aggregate score drop.
