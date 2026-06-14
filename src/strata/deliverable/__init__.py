"""Deliverable factory for LLM-based grading."""

from strata.deliverable.base import Deliverable, Rubric, Grade
from strata.deliverable.grader import Grader

__all__ = ["Deliverable", "Rubric", "Grade", "Grader", "InstructorGrader"]


def __getattr__(name: str):
    if name == "InstructorGrader":
        from strata.deliverable.instructor_grader import InstructorGrader

        return InstructorGrader
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
