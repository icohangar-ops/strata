# Instructor Integration: Rubric Enforcement via Structured Output

## Overview

This document describes how [jxnl/instructor](https://github.com/jxnl/instructor) enforces a 5-dimension evaluation rubric on LLM grading outputs, replacing manual review in the deliverable factory.

## Why Instructor?

Instructor patches OpenAI/Anthropic/other LLM clients to return validated Pydantic models instead of raw text. This means:

- **Guaranteed schema**: Every LLM response matches the expected rubric structure.
- **Automatic retries**: If the LLM produces invalid output, instructor retries with corrected schema guidance.
- **Type safety**: Downstream code consumes validated data, not unparsed strings.

## The 5-Dimension Evaluation Rubric

| Dimension              | Weight | Description                                              |
|------------------------|--------|----------------------------------------------------------|
| Financial Accuracy     | 30%    | Correctness of financial calculations, formulas, data    |
| Actionability          | 25%    | Whether recommendations are concrete and implementable   |
| Risk Awareness         | 20%    | Identification and mitigation of financial risks         |
| Stakeholder Clarity    | 15%    | Communicability to non-financial stakeholders            |
| Data Faithfulness      | 10%    | Alignment with source data, no fabricated figures        |

## Pydantic Schema

```python
from pydantic import BaseModel, Field
from enum import Enum

class DimensionScore(BaseModel):
    """Score for a single rubric dimension."""
    score: float = Field(..., ge=0, le=10, description="Score from 0-10")
    weight: float = Field(..., description="Weight of this dimension")
    rationale: str = Field(..., description="Explanation of the score")

class EvaluationRubric(BaseModel):
    """Complete 5-dimension evaluation rubric for deliverable grading."""
    financial_accuracy: DimensionScore = Field(
        default_factory=lambda: DimensionScore(score=0, weight=0.30, rationale=""),
        description="Financial Accuracy (30% weight)"
    )
    actionability: DimensionScore = Field(
        default_factory=lambda: DimensionScore(score=0, weight=0.25, rationale=""),
        description="Actionability (25% weight)"
    )
    risk_awareness: DimensionScore = Field(
        default_factory=lambda: DimensionScore(score=0, weight=0.20, rationale=""),
        description="Risk Awareness (20% weight)"
    )
    stakeholder_clarity: DimensionScore = Field(
        default_factory=lambda: DimensionScore(score=0, weight=0.15, rationale=""),
        description="Stakeholder Clarity (15% weight)"
    )
    data_faithfulness: DimensionScore = Field(
        default_factory=lambda: DimensionScore(score=0, weight=0.10, rationale=""),
        description="Data Faithfulness (10% weight)"
    )

    def weighted_total(self) -> float:
        """Calculate weighted total score."""
        dimensions = [
            self.financial_accuracy,
            self.actionability,
            self.risk_awareness,
            self.stakeholder_clarity,
            self.data_faithfulness,
        ]
        return sum(d.score * d.weight for d in dimensions)
```

## Instructor Integration

```python
import instructor
from openai import OpenAI

client = instructor.from_openai(OpenAI())

def grade_deliverable(deliverable_text: str) -> EvaluationRubric:
    """Grade a deliverable using the 5-dimension rubric."""
    return client.chat.completions.create(
        model="gpt-4",
        response_model=EvaluationRubric,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior financial analyst grading deliverables. "
                    "Evaluate the following deliverable on 5 dimensions. "
                    "Provide a score (0-10) and rationale for each. "
                    "Be strict: only reward genuine financial rigor."
                ),
            },
            {
                "role": "user",
                "content": f"Grade this deliverable:\n\n{deliverable_text}",
            },
        ],
        max_retries=3,
    )
```

## Replacing Manual Grading in the Deliverable Factory

### Before (Manual)

```python
# Old approach: LLM returns free text, human parses it
response = llm.complete("Grade this deliverable on 5 dimensions...")
# Human reads response, extracts scores, validates structure
# Error-prone, inconsistent, slow
```

### After (Instructor-Enforced)

```python
# New approach: instructor guarantees structured output
rubric = grade_deliverable(deliverable_text)
assert isinstance(rubric, EvaluationRubric)
total = rubric.weighted_total()  # e.g., 7.85

if total < 6.0:
    deliverable.status = "REVISION_REQUIRED"
    deliverable.feedback = rubric
elif total < 8.0:
    deliverable.status = "APPROVED_WITH_NOTES"
    deliverable.feedback = rubric
else:
    deliverable.status = "APPROVED"
    deliverable.feedback = rubric
```

### Benefits

- **Consistency**: Every deliverable graded against identical schema.
- **Auditability**: Rationales stored per-dimension for compliance review.
- **Automation**: Factory pipeline can auto-route based on weighted total.
- **Speed**: No human parsing of free-text grading responses.

## Retry Behavior

Instructor automatically retries when the LLM output fails Pydantic validation. Common retry scenarios:

- Missing required fields (e.g., empty `rationale`)
- Score out of range (e.g., `score: 12`)
- Malformed JSON

Each retry includes the validation error in the prompt, guiding the LLM to self-correct.

## Future Extensions

- Add `confidence: float` to `DimensionScore` for uncertainty quantification
- Support multi-grader consensus via `instructor.patch` on multiple clients
- Persist rubric results to S3/DynamoDB for longitudinal tracking
