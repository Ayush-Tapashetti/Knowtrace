"""Trajectory forecasts recorded for calibration (differentiator D2)."""

from sqlalchemy import CheckConstraint, Index
from sqlmodel import Field, SQLModel

from knowtrace.models._base import new_id, prob_check


class ForecastRecord(SQLModel, table=True):
    __tablename__ = "forecast_record"
    __table_args__ = (
        prob_check("forecast_record", "p_mastery_pred"),
        prob_check("forecast_record", "p_lo"),
        prob_check("forecast_record", "p_hi"),
        prob_check("forecast_record", "p_correct_pred"),
        CheckConstraint("p_lo <= p_mastery_pred AND p_mastery_pred <= p_hi", name="ck_forecast_interval"),
        CheckConstraint("made_at_seq >= 0", name="ck_forecast_made_at_seq"),
        # query served: unresolved_forecasts(student, concept) and calibration queries
        Index("ix_forecast_student_concept_seq", "student_id", "concept_id", "made_at_seq"),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    student_id: str = Field(foreign_key="student.id", ondelete="CASCADE")
    concept_id: str = Field(foreign_key="concept.id", ondelete="RESTRICT")
    made_at_seq: int
    p_mastery_pred: float
    p_lo: float
    p_hi: float
    p_correct_pred: float
    observed_correct: bool | None = None
    resolved_attempt_id: str | None = Field(default=None, foreign_key="attempt.id", ondelete="SET NULL")
