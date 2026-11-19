"""Diagnosis episodes and their probes."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Column, Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from knowtrace.domain.enums import DiagnosisState, DiagnosisVerdict
from knowtrace.models._base import UTCDateTime, enum_col, new_id, prob_check, utcnow


class Diagnosis(SQLModel, table=True):
    __tablename__ = "diagnosis"
    __table_args__ = (
        prob_check("diagnosis", "confidence", nullable=True),
        CheckConstraint(
            "verdict IS NULL OR verdict <> 'GAP' OR root_concept_id IS NOT NULL",
            name="ck_diagnosis_gap_has_root",
        ),
        # query served: open_diagnosis(student)
        Index("ix_diagnosis_student_state", "student_id", "state"),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    student_id: str = Field(foreign_key="student.id", ondelete="CASCADE")
    # One diagnosis per failed attempt.
    trigger_attempt_id: str = Field(foreign_key="attempt.id", ondelete="RESTRICT", unique=True)
    parent_diagnosis_id: str | None = Field(default=None, foreign_key="diagnosis.id", ondelete="SET NULL")
    excluded_concepts: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    state: DiagnosisState = Field(default=DiagnosisState.PROBING, sa_column=enum_col(DiagnosisState))
    verdict: DiagnosisVerdict | None = Field(
        default=None, sa_column=enum_col(DiagnosisVerdict, nullable=True)
    )
    root_concept_id: str | None = Field(default=None, foreign_key="concept.id", ondelete="RESTRICT")
    confidence: float | None = None
    posterior: dict[str, float] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    trace: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    config_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    curriculum_hash: str
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)
    updated_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)
    closed_at: datetime | None = Field(default=None, sa_type=UTCDateTime)

    probes: list["DiagnosisProbe"] = Relationship(
        back_populates="diagnosis",
        sa_relationship_kwargs={"passive_deletes": True, "order_by": "DiagnosisProbe.seq"},
    )


class DiagnosisProbe(SQLModel, table=True):
    __tablename__ = "diagnosis_probe"
    __table_args__ = (
        # query served: probes_for_diagnosis in order
        UniqueConstraint("diagnosis_id", "seq", name="uq_probe_diagnosis_seq"),
        CheckConstraint("seq >= 1", name="ck_probe_seq_pos"),
        CheckConstraint("eig_bits >= 0", name="ck_probe_eig_nonneg"),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    diagnosis_id: str = Field(foreign_key="diagnosis.id", ondelete="CASCADE")
    seq: int
    item_id: str = Field(foreign_key="item.id", ondelete="RESTRICT")
    attempt_id: str | None = Field(default=None, foreign_key="attempt.id", ondelete="SET NULL")
    eig_bits: float
    posterior_after: dict[str, float] | None = Field(default=None, sa_column=Column(JSON))

    diagnosis: Diagnosis = Relationship(back_populates="probes")
