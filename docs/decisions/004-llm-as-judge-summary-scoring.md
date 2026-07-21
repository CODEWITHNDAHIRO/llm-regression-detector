# ADR 004: Use LLM-as-judge with an explicit rubric for summary scoring

## Status
Accepted

## Context
Category correctness is checked with simple string equality. Summary
quality can't be checked that way -- two different wordings can both
correctly capture an email's intent, so exact/fuzzy string matching would
produce false negatives on perfectly good summaries.

## Options considered
1. **Fuzzy string matching** (e.g. Levenshtein distance, ROUGE score) --
   cheap, deterministic, but penalizes correct paraphrases and rewards
   near-verbatim copying, which isn't what we actually want to measure.
2. **LLM-as-judge with a free-form "rate this 1-5" prompt** -- flexible,
   but produces noisy, inconsistent scores across runs without an explicit
   standard to grade against.
3. **LLM-as-judge with an explicit written rubric**, given the original
   email, the reference summary, and the candidate summary, instructed to
   grade content/meaning equivalence rather than wording similarity.

## Decision
Use option 3. See `src/judge.py` for the rubric.

## Consequences
- Adds one extra LLM call per test case (cost and latency), run via
  `asyncio.to_thread` inside the async eval runner so it doesn't block
  concurrent classification calls.
- Judge scores are directionally reliable but not perfectly deterministic
  run-to-run -- acceptable for regression *detection* (large deltas matter),
  worth revisiting if fine-grained score stability becomes important later.
- Validated on a manual smoke test: a deliberately correct paraphrase
  scored 4-5, a deliberately wrong summary scored 1 (see judge.py's
  `__main__` block).
