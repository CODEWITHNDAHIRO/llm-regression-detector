# ADR 002: Store prompts as versioned YAML files, not inline Python strings

## Status
Accepted

## Context
Prompts change frequently during development and in production. The entire
purpose of this system is to detect when a prompt change causes a quality
regression, which requires being able to run the same test suite against
multiple prompt versions and diff the results.

## Options considered
1. **Inline strings in Python** — simplest to write, but a prompt change
   requires a code change, and there's no clean way to run "the old prompt"
   and "the new prompt" side by side without duplicating functions or using
   git history archaeology.
2. **Versioned YAML files** (`prompts/email_classifier_v1.yaml`,
   `..._v2.yaml`, etc.) — prompts become data, loaded at runtime by version
   string. Running an eval against two prompt versions is a parameter, not a
   code change.

## Decision
Store prompts as versioned YAML files under `/prompts`.

## Consequences
- Slightly more indirection when reading the code (must open the YAML to see
  the actual prompt).
- Prompt history lives in git alongside code, satisfying the "prompts are the
  code under test" framing this whole project is built on.
- Enables the eval engine (Phase 3) to treat `prompt_version` as a simple
  input parameter.
