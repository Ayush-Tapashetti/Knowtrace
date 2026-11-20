"""Diagnoses, probes, lessons, forecasts and evaluation runs."""

from __future__ import annotations

from collections.abc import Sequence

from sqlmodel import Session, col, select

from knowtrace.domain.enums import DiagnosisState
from knowtrace.models import (
    Diagnosis,
    DiagnosisProbe,
    EvalResult,
    EvalRun,
    ForecastRecord,
    Lesson,
    LessonStep,
)


def add_diagnosis(s: Session, d: Diagnosis) -> Diagnosis:
    s.add(d)
    s.flush()
    return d


def get_diagnosis(s: Session, diagnosis_id: str) -> Diagnosis | None:
    return s.get(Diagnosis, diagnosis_id)


def open_diagnosis(s: Session, student_id: str) -> Diagnosis | None:
    live = (DiagnosisState.PROBING, DiagnosisState.LESSON_ASSIGNED, DiagnosisState.RECHECKING)
    stmt = select(Diagnosis).where(Diagnosis.student_id == student_id, col(Diagnosis.state).in_(live))
    return s.exec(stmt.order_by(col(Diagnosis.created_at).desc())).first()


def page_diagnoses(
    s: Session, student_id: str, *, state: DiagnosisState | None, limit: int, offset: int
) -> Sequence[Diagnosis]:
    stmt = select(Diagnosis).where(Diagnosis.student_id == student_id)
    if state is not None:
        stmt = stmt.where(Diagnosis.state == state)
    return s.exec(stmt.order_by(col(Diagnosis.created_at).desc()).offset(offset).limit(limit)).all()


def add_probe(s: Session, p: DiagnosisProbe) -> DiagnosisProbe:
    s.add(p)
    s.flush()
    return p


def add_lesson(s: Session, lesson: Lesson, steps: Sequence[LessonStep]) -> Lesson:
    s.add(lesson)
    s.flush()
    s.add_all(steps)
    s.flush()
    return lesson


def get_lesson(s: Session, lesson_id: str) -> Lesson | None:
    return s.get(Lesson, lesson_id)


def lesson_for_diagnosis(s: Session, diagnosis_id: str) -> Lesson | None:
    return s.exec(select(Lesson).where(Lesson.diagnosis_id == diagnosis_id)).first()


def steps_for_lesson(s: Session, lesson_id: str) -> Sequence[LessonStep]:
    return s.exec(
        select(LessonStep).where(LessonStep.lesson_id == lesson_id).order_by(col(LessonStep.position))
    ).all()


def add_forecast(s: Session, f: ForecastRecord) -> ForecastRecord:
    s.add(f)
    s.flush()
    return f


def latest_eval(s: Session) -> tuple[EvalRun, Sequence[EvalResult]] | None:
    run = s.exec(select(EvalRun).order_by(col(EvalRun.created_at).desc())).first()
    if run is None:
        return None
    return run, s.exec(select(EvalResult).where(EvalResult.run_id == run.id)).all()


def unresolved_forecasts(s: Session, student_id: str, concept_id: str) -> Sequence[ForecastRecord]:
    stmt = select(ForecastRecord).where(
        ForecastRecord.student_id == student_id,
        ForecastRecord.concept_id == concept_id,
        col(ForecastRecord.observed_correct).is_(None),
    )
    return s.exec(stmt).all()
