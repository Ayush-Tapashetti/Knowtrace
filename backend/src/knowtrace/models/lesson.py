"""Assembled micro-lessons: Lesson and its ordered LessonStep rows."""

from datetime import datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, Relationship, SQLModel

from knowtrace.domain.enums import AtomKind
from knowtrace.models._base import UTCDateTime, enum_col, new_id, utcnow


class Lesson(SQLModel, table=True):
    __tablename__ = "lesson"
    __table_args__ = (CheckConstraint("est_seconds > 0", name="ck_lesson_est_seconds_pos"),)

    id: str = Field(default_factory=new_id, primary_key=True)
    diagnosis_id: str = Field(foreign_key="diagnosis.id", ondelete="CASCADE", unique=True)
    student_id: str = Field(foreign_key="student.id", ondelete="CASCADE")
    root_concept_id: str = Field(foreign_key="concept.id", ondelete="RESTRICT")
    est_seconds: int
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)
    completed_at: datetime | None = Field(default=None, sa_type=UTCDateTime)

    steps: list["LessonStep"] = Relationship(
        back_populates="lesson", sa_relationship_kwargs={"passive_deletes": True}
    )


class LessonStep(SQLModel, table=True):
    """One step of a lesson: an authored atom, or (fallback) a bare item-bank question."""

    __tablename__ = "lesson_step"
    __table_args__ = (
        CheckConstraint("position >= 1", name="ck_lesson_step_position_pos"),
        CheckConstraint("est_seconds > 0", name="ck_lesson_step_est_seconds_pos"),
        CheckConstraint("atom_id IS NOT NULL OR item_id IS NOT NULL", name="ck_lesson_step_has_content"),
    )

    lesson_id: str = Field(primary_key=True, foreign_key="lesson.id", ondelete="CASCADE")
    position: int = Field(primary_key=True)
    concept_id: str = Field(foreign_key="concept.id", ondelete="RESTRICT")
    kind: AtomKind = Field(sa_column=enum_col(AtomKind))
    est_seconds: int
    atom_id: str | None = Field(default=None, foreign_key="lesson_atom.id", ondelete="RESTRICT")
    item_id: str | None = Field(default=None, foreign_key="item.id", ondelete="RESTRICT")
    viewed_at: datetime | None = Field(default=None, sa_type=UTCDateTime)

    lesson: Lesson = Relationship(back_populates="steps")
