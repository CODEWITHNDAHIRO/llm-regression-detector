"""
The LLM feature under test: a customer support email classifier.

This module is intentionally small and isolated. Everything the eval
pipeline needs to know about "the feature" flows through classify_email().
That isolation is what makes this testable later.
"""
import time
from dataclasses import dataclass
import yaml
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import anthropic

load_dotenv()  # reads .env in the project root and sets env vars from it
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
async_client = anthropic.AsyncAnthropic()  # async twin, used by the eval runner

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class EmailClassification(BaseModel):
    """The structured output contract. This is what every part of the
    system (eval engine, dashboard, alerting) can rely on."""
    category: Literal["billing", "technical", "account", "general"]
    summary: str = Field(description="One-sentence summary of the request")


class PromptConfig(BaseModel):
    """Loaded from a versioned YAML file. Swapping prompt versions means
    swapping which PromptConfig gets loaded -- no code changes."""
    version: str
    system_prompt: str


def load_prompt(version: str) -> PromptConfig:
    path = PROMPTS_DIR / f"email_classifier_{version}.yaml"
    data = yaml.safe_load(path.read_text())
    return PromptConfig(version=data["version"], system_prompt=data["system_prompt"])


# The "tool" schema. We're not actually giving Claude a tool to call --
# we're exploiting tool-use to force it to emit arguments matching this
# exact shape. This is the standard trick for structured output.
CLASSIFY_TOOL = {
    "name": "submit_classification",
    "description": "Submit the email classification result.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["billing", "technical", "account", "general"],
            },
            "summary": {
                "type": "string",
                "description": "One-sentence summary of the customer's request",
            },
        },
        "required": ["category", "summary"],
    },
}


def classify_email(email_text: str, prompt_version: str = "v1") -> EmailClassification:
    """Runs one email through the classifier feature and returns a
    validated, structured result."""
    config = load_prompt(prompt_version)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=config.system_prompt,
        tools=[CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "submit_classification"},
        messages=[{"role": "user", "content": email_text}],
    )

    # response.content is a list of blocks; with tool_choice forced,
    # the first (only) block is the tool_use block with our arguments.
    tool_call = next(b for b in response.content if b.type == "tool_use")
    return EmailClassification(**tool_call.input)


@dataclass
class ClassificationRun:
    """Everything the eval engine needs beyond the classification itself:
    how much this call cost (tokens) and how long it took (latency)."""
    classification: EmailClassification
    input_tokens: int
    output_tokens: int
    latency_ms: float


async def classify_email_async(email_text: str, prompt_version: str = "v1") -> ClassificationRun:
    """Async twin of classify_email. Used by the eval runner so many test
    cases can be in flight to the API at once instead of one at a time."""
    config = load_prompt(prompt_version)

    start = time.perf_counter()
    response = await async_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=config.system_prompt,
        tools=[CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "submit_classification"},
        messages=[{"role": "user", "content": email_text}],
    )
    latency_ms = (time.perf_counter() - start) * 1000

    tool_call = next(b for b in response.content if b.type == "tool_use")
    classification = EmailClassification(**tool_call.input)

    return ClassificationRun(
        classification=classification,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_ms=latency_ms,
    )


if __name__ == "__main__":
    # manual smoke test
    test_email = "I can't log into my account, it keeps saying wrong password even though I reset it."
    result = classify_email(test_email)
    print(result.model_dump_json(indent=2))