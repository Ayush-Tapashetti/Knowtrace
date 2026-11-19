from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from knowtrace.domain.enums import (
    AtomKind,
    AttemptContext,
    DiagnosisState,
    DiagnosisVerdict,
    ItemKind,
)
from knowtrace.models import (
    Attempt,
    Concept,
    Diagnosis,
    DiagnosisProbe,
    EvalResult,
    EvalRun,
    ForecastRecord,
    Item,
    ItemConcept,
    Lesson,
    LessonAtom,
    LessonStep,
    MasteryState,
    PrerequisiteEdge,
    Student,
)

EXPECTED_TABLES = {
    "concept", "prerequisite_edge", "item", "item_concept", "lesson_atom", "student",
    "attempt", "mastery_state", "diagnosis", "diagnosis_probe", "lesson", "lesson_step",
    "forecast_record", "eval_run", "eval_result",
}  # fmt: skip


def _concept(cid: str, tier: int) -> Concept:
    return Concept(
        id=cid, name=cid, description="d", strand="fractions", tier=tier, p_init=0.3,
        p_learn=0.15, p_slip=0.1, p_guess=0.2, p_forget=0.02, half_life_days=14.0,
    )  # fmt: skip


def populate(s: Session) -> dict[str, str]:
    """Insert one row per entity, flushing parents first (FKs are enforced)."""
    s.add_all([_concept("frac.basic", 1), _concept("frac.add", 2)])
    s.flush()
    s.add(PrerequisiteEdge(concept_id="frac.add", prereq_id="frac.basic"))
    s.add(
        Item(
            id="i.add1", stem="1/2 + 1/4 = ?", kind=ItemKind.MCQ, answer="a", difficulty=0.3,
            choices=[{"id": "a", "text": "3/4"}, {"id": "b", "text": "2/6"}],
        )
    )  # fmt: skip
    s.flush()
    s.add(ItemConcept(item_id="i.add1", concept_id="frac.add", is_primary=True))
    s.add(ItemConcept(item_id="i.add1", concept_id="frac.basic", is_primary=False))
    s.add(LessonAtom(id="a.add.check1", concept_id="frac.add", kind=AtomKind.CHECK,
                     body="Try it", est_seconds=30, order_hint=1, item_id="i.add1"))  # fmt: skip
    student = Student(pseudonym="student-7f3a")
    s.add(student)
    s.flush()
    first = Attempt(student_id=student.id, seq=1, item_id="i.add1", context=AttemptContext.PRACTICE,
                    answer_given="b", is_correct=False)  # fmt: skip
    s.add(first)
    s.add(MasteryState(student_id=student.id, concept_id="frac.add", p_mastery=0.25, n_obs=1))
    s.flush()
    diag = Diagnosis(
        student_id=student.id, trigger_attempt_id=first.id, state=DiagnosisState.PROBING,
        curriculum_hash="abc123", posterior={"frac.add": 0.6, "SLIP": 0.4},
    )  # fmt: skip
    s.add(diag)
    s.flush()
    probe_attempt = Attempt(student_id=student.id, seq=2, item_id="i.add1",
                            context=AttemptContext.PROBE, diagnosis_id=diag.id,
                            answer_given="a", is_correct=True)  # fmt: skip
    s.add(probe_attempt)
    s.flush()
    s.add(DiagnosisProbe(diagnosis_id=diag.id, seq=1, item_id="i.add1",
                         attempt_id=probe_attempt.id, eig_bits=0.7))  # fmt: skip
    lesson = Lesson(diagnosis_id=diag.id, student_id=student.id, root_concept_id="frac.basic",
                    est_seconds=120)  # fmt: skip
    s.add(lesson)
    s.flush()
    s.add(
        LessonStep(
            lesson_id=lesson.id,
            position=1,
            concept_id="frac.add",
            kind=AtomKind.CHECK,
            est_seconds=30,
            atom_id="a.add.check1",
        )
    )
    s.add(
        ForecastRecord(
            student_id=student.id, concept_id="frac.add", made_at_seq=2, p_mastery_pred=0.5,
            p_lo=0.3, p_hi=0.7, p_correct_pred=0.45,
        )
    )  # fmt: skip
    run = EvalRun(seed=1234, n_students=10, curriculum_hash="abc123", config={"k": 1})
    s.add(run)
    s.flush()
    s.add(EvalResult(run_id=run.id, method="graph_bayes", metric="top1", value=0.9, n=10))
    s.commit()
    return {"student": student.id, "diagnosis": diag.id, "attempt": first.id, "lesson": lesson.id}


def test_all_fifteen_tables_exist(engine: Engine) -> None:
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
    assert set(SQLModel.metadata.tables) == EXPECTED_TABLES


def test_one_row_per_entity_roundtrips(session: Session) -> None:
    ids = populate(session)
    for model in (Concept, PrerequisiteEdge, Item, ItemConcept, LessonAtom, Student, Attempt,
                  MasteryState, Diagnosis, DiagnosisProbe, Lesson, LessonStep, ForecastRecord,
                  EvalRun, EvalResult):  # fmt: skip
        assert session.exec(select(model)).first() is not None, model.__name__

    diag = session.get(Diagnosis, ids["diagnosis"])
    assert diag is not None
    assert diag.state is DiagnosisState.PROBING and diag.verdict is None
    assert diag.posterior == {"frac.add": 0.6, "SLIP": 0.4}
    assert diag.created_at.tzinfo is UTC
    assert [p.seq for p in diag.probes] == [1]

    item = session.get(Item, "i.add1")
    assert item is not None
    assert item.kind is ItemKind.MCQ and item.choices is not None and len(item.choices) == 2
    assert len(item.concept_links) == 2


def test_foreign_key_violation_rejected(session: Session) -> None:
    session.add(Attempt(student_id="no-such-student", seq=1, item_id="x",
                        context=AttemptContext.PRACTICE, answer_given="a", is_correct=True))  # fmt: skip
    with pytest.raises(IntegrityError):
        session.commit()


def test_probability_check_enforced(session: Session) -> None:
    populate(session)
    sid = session.exec(select(Student)).one().id
    session.add(MasteryState(student_id=sid, concept_id="frac.basic", p_mastery=1.0))
    with pytest.raises(IntegrityError):
        session.commit()


def test_self_loop_edge_rejected(session: Session) -> None:
    session.add(_concept("c1", 1))
    session.flush()
    session.add(PrerequisiteEdge(concept_id="c1", prereq_id="c1"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_exactly_one_primary_concept_per_item(session: Session) -> None:
    populate(session)
    session.add(_concept("frac.extra", 3))
    session.flush()
    session.add(ItemConcept(item_id="i.add1", concept_id="frac.extra", is_primary=True))
    with pytest.raises(IntegrityError):
        session.commit()


def test_attempt_seq_unique_per_student(session: Session) -> None:
    ids = populate(session)
    session.add(Attempt(student_id=ids["student"], seq=1, item_id="i.add1",
                        context=AttemptContext.PRACTICE, answer_given="a", is_correct=True))  # fmt: skip
    with pytest.raises(IntegrityError):
        session.commit()


def test_practice_atom_requires_item(session: Session) -> None:
    session.add(_concept("c1", 1))
    session.flush()
    session.add(LessonAtom(id="a1", concept_id="c1", kind=AtomKind.PRACTICE, body="x",
                           est_seconds=10, order_hint=1))  # fmt: skip
    with pytest.raises(IntegrityError):
        session.commit()


def test_gap_verdict_requires_root_concept(session: Session) -> None:
    ids = populate(session)
    diag = session.get(Diagnosis, ids["diagnosis"])
    assert diag is not None
    diag.verdict = DiagnosisVerdict.GAP
    session.add(diag)
    with pytest.raises(IntegrityError):
        session.commit()


def test_enum_value_enforced_at_database_level(session: Session) -> None:
    ids = populate(session)
    with pytest.raises(IntegrityError):
        session.execute(text("UPDATE diagnosis SET state = 'BOGUS' WHERE id = :i"), {"i": ids["diagnosis"]})


def test_deleting_student_cascades_but_concept_in_use_is_restricted(session: Session) -> None:
    ids = populate(session)
    with pytest.raises(IntegrityError):
        session.execute(text("DELETE FROM concept WHERE id = 'frac.add'"))
    session.rollback()

    session.execute(text("DELETE FROM student WHERE id = :s"), {"s": ids["student"]})
    session.commit()
    for table in ("attempt", "mastery_state", "diagnosis", "lesson", "lesson_step",
                  "forecast_record", "diagnosis_probe"):  # fmt: skip
        count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        assert count == 0, table


def test_naive_datetime_rejected(session: Session) -> None:
    session.add(Student(pseudonym="student-naive", created_at=datetime(2026, 1, 1)))
    with pytest.raises(Exception, match="naive datetime"):
        session.commit()
