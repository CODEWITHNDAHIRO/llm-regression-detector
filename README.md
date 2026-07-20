# MODEL REGRESSION DETECTION SYSTEM

A CI/CD-style pipeline that tests an LLM-powered feature against a hand-labeled golden dataset whenever its prompt changes, detects quality regressions before they reach production,and alerts the team with a diff report.

## The Problem
Most teams shipping LLM-powered features change prompts the same way they'd edit a config value:push it, watch for complaints. There is no equivalent of a unit test suite for "does this prompt still produce correct outputs?" This project builds that missing piece - CI for prompt/model behavior,not just code correctness.

## ARCHITECTURE

* **prompts/** Versioned prompt configs (the "code" under test)
* **eval_data/** Hand-labeled golden dataset (ground truth)
* **src/classifier.py** The LLM feature under test ... (eval engine, reporting — added in later phases)
* **docs/decisions/** Architecture Decision Records — why, not just what
* **reports/** Generated HTML diff reports

## KEY DESIGN DECISIONS

Full reasoning in docs/decisions/. Highlights:

* **a. ADR 001** - structured output is enforced via forced tool-use,not prompted JSON,eliminating an entire class of malformed-output bugs.
* **b. ADR 002** - prompts are versioned YAMLL files,not inline strings, so a prompt change is a data change, not a code change.
* **c. ADR 003** - the golden dataset is hand-labeled by a human,never LLM-generated, so the eval suite can catch model blind spots instead of just confirming the model agrees with itself.

## Setup

```bash
git clone
cd regression-detector
pip install -r requirements.txt
cp .env
# then fill in ANTHROPIC_API_KEY
python src/classifier.py # test
