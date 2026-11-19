"""Runtime learner data: students, the immutable attempt log, and the derived mastery cache."""

from datetime import datetime

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, String, UniqueConstraint
from sqlmodel import Field, SQLModel

from knowtrace.domain.enums import AttemptContext
from knowtrace.models._base import UTCDateTime, enum_col, new_id, prob_check, utcnow


class Student(SQLModel, table=True):
    """Pseudonymous learner. No names, emails or roll numbers are stored anywhere."""

    __tablename__ = "student"

    id: str = Field(default_factory=new_id, primary_key=True)
    pseudonym: str = Field(unique=True)
    is_synthetic: bool = False
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)


class Attempt(SQLModel, table=True):
    """Immutable event log. `is_correct` is always computed server-side by `grade_answer`."""

    __tablename__ = "attempt"
    __table_args__ = (
        # query served: attempt_history(student) ORDER BY seq (replay)
        UniqueConstraint("student_id", "seq", name="uq_attempt_student_seq"),
        CheckConstraint("seq >= 1", name="ck_attempt_seq_pos"),
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_attempt_latency"),
        # query served: attempts_for_diagnosis
        Index("ix_attempt_diagnosis", "diagnosis_id"),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    student_id: str = Field(foreign_key="student.id", ondelete="CASCADE")
    seq: int
    item_id: str = Field(foreign_key="item.id", ondelete="RESTRICT")
    context: AttemptContext = Field(sa_column=enum_col(AttemptContext))
    # Attempt <-> Diagnosis form an FK cycle (failed attempt first, then the diagnosis that
    # points at it, then probe attempts that point back), hence nullable + use_alter.
    diagnosis_id: str | None = Field(
        default=None,
        sa_column=Column(
            String,
            ForeignKey("diagnosis.id", ondelete="SET NULL", use_alter=True, name="fk_attempt_diagnosis"),
            nullable=True,
        ),
    )
    answer_given: str
    is_correct: bool
    latency_ms: int | None = None
    attempted_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)


class MasteryState(SQLModel, table=True):
    """Derived cache. Invariant: replaying Attempts reproduces this table exactly."""

    __tablename__ = "mastery_state"
    __table_args__ = (
        prob_check("mastery_state", "p_mastery"),
        CheckConstraint("n_obs >= 0", name="ck_mastery_n_obs_nonneg"),
    )

    student_id: str = Field(primary_key=True, foreign_key="student.id", ondelete="CASCADE")
    concept_id: str = Field(primary_key=True, foreign_key="concept.id", ondelete="RESTRICT")
    p_mastery: float
    n_obs: int = 0
    last_observed_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    updated_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)
