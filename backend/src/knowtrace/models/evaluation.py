"""Evaluation harness results (differentiators D1 and D2)."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Column, Index, text
from sqlmodel import Field, Relationship, SQLModel

from knowtrace.models._base import UTCDateTime, new_id, utcnow


class EvalRun(SQLModel, table=True):
    __tablename__ = "eval_run"
    __table_args__ = (
        CheckConstraint("n_students >= 1", name="ck_eval_run_n_students"),
        # query served: latest_eval_run
        Index("ix_eval_run_created_at", text("created_at DESC")),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)
    seed: int
    n_students: int
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    curriculum_hash: str
    code_version: str | None = None

    results: list["EvalResult"] = Relationship(
        back_populates="run", sa_relationship_kwargs={"passive_deletes": True}
    )


class EvalResult(SQLModel, table=True):
    __tablename__ = "eval_result"
    __table_args__ = (CheckConstraint("n >= 0", name="ck_eval_result_n_nonneg"),)

    run_id: str = Field(primary_key=True, foreign_key="eval_run.id", ondelete="CASCADE")
    method: str = Field(primary_key=True)  # graph_bayes | baseline_parent | baseline_flat_bkt
    metric: str = Field(primary_key=True)  # top1 | top3 | probes_mean | auc | brier | reliability
    value: float
    n: int
    detail: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))

    run: EvalRun = Relationship(back_populates="results")
