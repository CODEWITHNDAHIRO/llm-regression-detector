# ADR 001: Use forced tool-use for structured output, not prompted JSON

## Status
Accepted

## Context
The classifier needs to return machine-parseable output (category + summary)
that downstream code (eval engine, dashboard, alerting) can rely on without
defensive parsing.

## Options considered
1. **Prompt engineering only** — ask the model in plain language to "respond
   in JSON format." Simple, but the model occasionally adds preamble text,
   uses inconsistent field names, or produces malformed JSON, especially
   under prompt changes made later by someone unfamiliar with the original
   intent.
2. **Forced tool-use** — define a JSON Schema as a "tool" and force the model
   to call it via `tool_choice`. The model is trained to fill tool arguments
   precisely, and the SDK returns a structured object rather than a raw
   string.

## Decision
Use forced tool-use (option 2), validated on receipt with a Pydantic model.

## Consequences
- Adds a small amount of schema-definition overhead per feature.
- Removes an entire class of "the model almost returned valid JSON" bugs.
- Makes the output contract explicit and versionable — the schema itself
  becomes documentation.
