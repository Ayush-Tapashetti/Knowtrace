"""Import every table so `SQLModel.metadata` is complete."""

from knowtrace.models.curriculum import Concept, Item, ItemConcept, LessonAtom, PrerequisiteEdge
from knowtrace.models.diagnosis import Diagnosis, DiagnosisProbe
from knowtrace.models.evaluation import EvalResult, EvalRun
from knowtrace.models.forecast import ForecastRecord
from knowtrace.models.learner import Attempt, MasteryState, Student
from knowtrace.models.lesson import Lesson, LessonStep

__all__ = [
    "Attempt",
    "Concept",
    "Diagnosis",
    "DiagnosisProbe",
    "EvalResult",
    "EvalRun",
    "ForecastRecord",
    "Item",
    "ItemConcept",
    "Lesson",
    "LessonAtom",
    "LessonStep",
    "MasteryState",
    "PrerequisiteEdge",
    "Student",
]
