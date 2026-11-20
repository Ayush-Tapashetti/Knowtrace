"""Students, the attempt log and the derived mastery cache."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy import func
from sqlmodel import Session, col, select

from knowtrace.models import Attempt, MasteryState, Student


def add_student(s: Session, student: Student) -> Student:
    s.add(student)
    s.flush()
    return student


def get_student(s: Session, student_id: str) -> Student | None:
    return s.get(Student, student_id)


def pseudonym_taken(s: Session, pseudonym: str) -> bool:
    return s.exec(select(Student.id).where(Student.pseudonym == pseudonym)).first() is not None


def next_seq(s: Session, student_id: str) -> int:
    top = s.exec(select(func.max(Attempt.seq)).where(Attempt.student_id == student_id)).one()
    return int(top or 0) + 1


def add_attempt(s: Session, attempt: Attempt) -> Attempt:
    s.add(attempt)
    s.flush()
    return attempt


def attempts_for_student(s: Session, student_id: str, *, before_seq: int | None = None) -> Sequence[Attempt]:
    stmt = select(Attempt).where(Attempt.student_id == student_id)
    if before_seq is not None:
        stmt = stmt.where(Attempt.seq < before_seq)
    return s.exec(stmt.order_by(col(Attempt.seq))).all()


def attempts_for_diagnosis(s: Session, diagnosis_id: str) -> Sequence[Attempt]:
    return s.exec(
        select(Attempt).where(Attempt.diagnosis_id == diagnosis_id).order_by(col(Attempt.seq))
    ).all()


def get_attempt(s: Session, attempt_id: str) -> Attempt | None:
    return s.get(Attempt, attempt_id)


def mastery_rows(s: Session, student_id: str) -> Mapping[str, MasteryState]:
    rows = s.exec(select(MasteryState).where(MasteryState.student_id == student_id)).all()
    return {r.concept_id: r for r in rows}


def upsert_mastery(
    s: Session, student_id: str, values: Mapping[str, float], observed_at: datetime, now: datetime
) -> None:
    existing = mastery_rows(s, student_id)
    for cid, p in values.items():
        row = existing.get(cid)
        if row is None:
            s.add(
                MasteryState(
                    student_id=student_id,
                    concept_id=cid,
                    p_mastery=p,
                    n_obs=1,
                    last_observed_at=observed_at,
                    updated_at=now,
                )
            )
        else:
            row.p_mastery, row.n_obs = p, row.n_obs + 1
            row.last_observed_at, row.updated_at = observed_at, now
            s.add(row)
    s.flush()
