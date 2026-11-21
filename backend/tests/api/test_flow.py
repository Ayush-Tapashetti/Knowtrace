"""End-to-end P0-5 flow over HTTP: fail -> diagnose (with path) -> lesson -> recheck -> mastery up."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.support import API, DESC, attempt, knows_unless_missing, new_student, probe_until_done, teach


def _open_diagnosis(c: TestClient, sid: str, item: str = "i.D.1") -> dict:
    res = attempt(c, sid, item, "b")  # wrong
    assert res["attempt"]["is_correct"] is False
    assert res["diagnosis"]["state"] == "PROBING"
    return res["diagnosis"]


def test_full_flow_resolves_the_root_gap_and_raises_its_mastery(client: TestClient) -> None:
    sid = new_student(client)
    teach(client, sid, "A", rounds=2)  # A is solid; B (and everything above) unknown
    d = _open_diagnosis(client, sid)
    assert d["pending_item"] is not None and "answer" not in d["pending_item"]
    assert d["max_probes"] == 4

    d = probe_until_done(client, d, knows_unless_missing({"B"}, DESC))
    assert d["verdict"] == "GAP" and d["root_concept_id"] == "B"
    assert d["state"] == "LESSON_ASSIGNED" and d["probes_used"] <= 4
    assert d["confidence"] >= 0.8
    path = [n["concept_id"] for n in d["trace"]]
    assert path[0] == "B" and path[-1] == "D" and "C" in path  # root -> ... -> failed concept
    assert "Fractions" in d["explanation"]

    lesson = client.get(f"{API}/lessons/{d['lesson_id']}").json()
    assert lesson["root_concept_id"] == "B" and lesson["est_seconds"] <= 300 and not lesson["completed"]
    assert all(s["source"] == "authored" for s in lesson["steps"])
    assert sum(1 for s in lesson["steps"] if s["kind"] == "CHECK" and s["concept_id"] == "B") >= 2

    # completing early is refused until every step was viewed
    early = client.post(f"{API}/lessons/{lesson['id']}/complete")
    assert early.status_code == 409 and early.json()["error"]["code"] == "illegal_transition"

    for step in lesson["steps"]:
        body = {"answer": "a"} if step["item"] else {}
        r = client.post(f"{API}/lessons/{lesson['id']}/steps/{step['position']}/view", json=body)
        assert r.status_code == 200, r.text
        assert (r.json()["attempt"] is not None) == bool(step["item"])
    assert r.json()["all_viewed"] is True

    done = client.post(f"{API}/lessons/{lesson['id']}/complete")
    assert done.status_code == 200 and done.json()["state"] == "RECHECKING"
    d = done.json()

    result = None
    for _ in range(d["max_rechecks"]):
        assert d["pending_kind"] == "RECHECK" and d["pending_item"]["primary_concept_id"] == "B"
        r = client.post(f"{API}/diagnoses/{d['id']}/recheck", json={"answer": "a"})
        assert r.status_code == 200, r.text
        result = r.json()
        d = result["diagnosis"]
        if d["state"] != "RECHECKING":
            break
    assert result is not None and d["state"] == "RESOLVED" and result["passed"] is True
    assert result["root_mastery_after"] > result["root_mastery_before"]
    assert result["root_mastery_after"] >= 0.85

    mastery = {m["concept_id"]: m for m in client.get(f"{API}/students/{sid}/mastery").json()["concepts"]}
    assert mastery["B"]["mastered"] is True

    # the student is free to practise again
    assert (
        client.post(f"{API}/students/{sid}/attempts", json={"item_id": "i.A.1", "answer": "a"}).status_code
        == 201
    )


def test_a_correct_practice_answer_opens_no_diagnosis(client: TestClient) -> None:
    res = attempt(client, new_student(client), "i.C.1", "a")
    assert res["attempt"]["is_correct"] is True and res["diagnosis"] is None
    assert res["attempt"]["mastery"]["C"] > 0.3


def test_a_strong_learner_who_misses_one_item_is_told_it_was_a_slip(client: TestClient) -> None:
    sid = new_student(client)
    teach(client, sid)
    d = _open_diagnosis(client, sid, "i.D.1")
    d = probe_until_done(client, d, lambda concepts: True)  # everything else answered correctly
    assert d["verdict"] == "SLIP" and d["state"] == "SLIP_DISMISSED" and d["lesson_id"] is None
    assert d["closed_at"] is not None and "slip" in d["explanation"].lower()


def test_second_failure_while_diagnosis_is_open_is_a_conflict_until_abandoned(client: TestClient) -> None:
    sid = new_student(client)
    d = _open_diagnosis(client, sid)
    r = client.post(f"{API}/students/{sid}/attempts", json={"item_id": "i.A.1", "answer": "a"})
    assert r.status_code == 409 and r.json()["error"]["details"]["diagnosis_id"] == d["id"]

    gone = client.post(f"{API}/diagnoses/{d['id']}/abandon")
    assert gone.status_code == 200 and gone.json()["state"] == "ABANDONED"
    assert client.post(f"{API}/diagnoses/{d['id']}/abandon").status_code == 409  # terminal
    assert (
        client.post(f"{API}/students/{sid}/attempts", json={"item_id": "i.A.1", "answer": "a"}).status_code
        == 201
    )


def test_diagnosis_endpoints_enforce_the_state_machine(client: TestClient) -> None:
    sid = new_student(client)
    teach(client, sid, "A", rounds=2)
    d = probe_until_done(client, _open_diagnosis(client, sid), knows_unless_missing({"B"}, DESC))
    assert d["state"] == "LESSON_ASSIGNED"
    for path in ("answer", "recheck"):
        r = client.post(f"{API}/diagnoses/{d['id']}/{path}", json={"answer": "a"})
        assert r.status_code == 409 and r.json()["error"]["code"] == "illegal_transition", path
    listed = client.get(f"{API}/students/{sid}/diagnoses", params={"state": "LESSON_ASSIGNED"}).json()
    assert [x["id"] for x in listed] == [d["id"]]


def test_lesson_step_rules(client: TestClient) -> None:
    sid = new_student(client)
    teach(client, sid, "A", rounds=2)
    d = probe_until_done(client, _open_diagnosis(client, sid), knows_unless_missing({"B"}, DESC))
    lesson = client.get(f"{API}/lessons/{d['lesson_id']}").json()
    text_step = next(s for s in lesson["steps"] if s["item"] is None)
    r = client.post(f"{API}/lessons/{lesson['id']}/steps/{text_step['position']}/view", json={"answer": "a"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_request"
    assert client.post(f"{API}/lessons/{lesson['id']}/steps/40/view", json={}).status_code == 404
    assert client.post(f"{API}/lessons/{lesson['id']}/steps/99/view", json={}).status_code == 422
    again = [
        client.post(f"{API}/lessons/{lesson['id']}/steps/{text_step['position']}/view", json={})
        for _ in range(2)
    ]
    assert all(x.status_code == 200 for x in again)  # idempotent


def test_mastery_decays_on_read_but_is_never_stored_decayed(client: TestClient, clock) -> None:  # type: ignore[no-untyped-def]
    sid = new_student(client)
    teach(client, sid, "A")
    fresh = {
        m["concept_id"]: m["p_mastery"]
        for m in client.get(f"{API}/students/{sid}/mastery").json()["concepts"]
    }
    clock.advance(days=60)
    later = {
        m["concept_id"]: m["p_mastery"]
        for m in client.get(f"{API}/students/{sid}/mastery").json()["concepts"]
    }
    assert later["A"] < fresh["A"] and later["A"] >= 0.3  # decays toward the prior, not below it
    assert later["F"] == fresh["F"] == 0.3  # untouched concept stays at its prior
    clock.advance(days=-60)
    again = {
        m["concept_id"]: m["p_mastery"]
        for m in client.get(f"{API}/students/{sid}/mastery").json()["concepts"]
    }
    assert again["A"] == fresh["A"]


def test_forecast_records_are_rolled_per_attempt(client: TestClient) -> None:
    from sqlmodel import Session, select

    from knowtrace.models import ForecastRecord

    sid = new_student(client)
    attempt(client, sid, "i.A.1", "a")
    attempt(client, sid, "i.A.2", "b")  # wrong: opens a diagnosis, resolves the previous forecast
    with Session(client.app.state.engine) as s:  # type: ignore[attr-defined]
        rows = s.exec(
            select(ForecastRecord)
            .where(ForecastRecord.concept_id == "A")
            .order_by(ForecastRecord.made_at_seq)
        ).all()
    assert [r.observed_correct for r in rows] == [
        False,
        None,
    ]  # forecast made after attempt 1 is scored by attempt 2
    assert all(r.p_lo <= r.p_mastery_pred <= r.p_hi for r in rows)
