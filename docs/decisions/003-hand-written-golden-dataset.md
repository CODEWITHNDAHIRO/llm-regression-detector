# ADR 003: Golden dataset is hand-labeled by a human, never LLM-generated

## Status
Accepted

## Context
The eval suite's entire value depends on the correctness of its ground truth
labels. If the same model (or family of models) used to generate test cases
is also used to label them "correct," any systematic blind spot the model
has gets baked into the eval and can never be detected by it.

## Options considered
1. **Generate test cases and labels with an LLM** — fast, scales easily, but
   ground truth becomes circular: the eval can only ever confirm the model
   agrees with itself.
2. **Hand-write test cases and labels** — slower, doesn't scale past ~100-200
   cases without significant time investment, but ground truth is
   independent of the system under test.

## Decision
Hand-write all golden dataset cases. LLMs may be used later to help generate
*candidate* cases for human review (see Project 13's production-log mining
pattern), but never to assign the final label without human confirmation.

## Consequences
- Building the initial dataset takes real time (budgeted: 2 days).
- The eval suite can actually catch model blind spots, not just internal
  inconsistency.
- Dataset growth over time should be driven by production failures (real
  cases the model got wrong), not synthetic generation.
