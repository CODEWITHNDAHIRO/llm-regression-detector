"""
Phase 3, LLM-as-judge scoring for summary quality.

Category correctness is a simple equality check (see eval_runner.py). Summary
quality isn't -- two different wordings can both be correct. This module uses
a separate LLM call, with an explicit rubric, to score how well the actual
summary matches the intent of the golden reference summary.
"""
from pydantic import BaseModel
from classifier import client  # reuse the same sync client; judging is a
                                 # secondary pass, doesn't need to be async


class JudgeScore(BaseModel):
    score: int  # 1-5
    reasoning: str


JUDGE_TOOL = {
    "name": "submit_judgment",
    "description": "Submit the quality judgment for the candidate summary.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {
                "type": "integer",
                "description": "1-5 rating per the rubric",
                "enum": [1, 2, 3, 4, 5],
            },
            "reasoning": {
                "type": "string",
                "description": "One sentence explaining the score",
            },
        },
        "required": ["score", "reasoning"],
    },
}

JUDGE_SYSTEM_PROMPT = """You are grading whether a candidate summary correctly
captures the same essential information as a reference summary, for a
customer support email triage system.

Score on this rubric:
5 - Captures the same core request/issue as the reference, no missing or
    incorrect information.
4 - Captures the core request, but omits a minor secondary detail present
    in the reference.
3 - Captures the general topic but misses or misstates part of the core
    request.
2 - Only loosely related to the reference; misses the main point.
1 - Unrelated to the reference, or factually contradicts it.

You are grading MEANING equivalence, not wording. Different phrasing of the
same information should score 5. Only penalize actual content differences."""


def judge_summary(email: str, expected_summary: str, actual_summary: str) -> JudgeScore:
    """Scores actual_summary against expected_summary for the given email."""
    user_message = f"""Original email:
{email}

Reference summary (ground truth):
{expected_summary}

Candidate summary (to be graded):
{actual_summary}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=JUDGE_SYSTEM_PROMPT,
        tools=[JUDGE_TOOL],
        tool_choice={"type": "tool", "name": "submit_judgment"},
        messages=[{"role": "user", "content": user_message}],
    )

    tool_call = next(b for b in response.content if b.type == "tool_use")
    return JudgeScore(**tool_call.input)


if __name__ == "__main__":
    # Smoke test: a clearly good summary and a clearly bad one
    email = "I was charged twice for my subscription this month, please help."
    expected = "Customer reports a duplicate subscription charge and requests a refund."

    good = judge_summary(email, expected, "Customer was double-billed for their subscription this month.")
    print("Good candidate:", good.model_dump_json(indent=2))

    bad = judge_summary(email, expected, "Customer wants to change their password.")
    print("Bad candidate:", bad.model_dump_json(indent=2))