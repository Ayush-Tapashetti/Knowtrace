"""One success, one validation failure and one domain/state error per P0 endpoint, plus the envelope."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.api.support import API, attempt, new_student


def err(r) -> dict:  # type: ignore[no-untyped-def]
    body = r.json()
    assert set(body) == {"error"} and {"code", "message"} <= set(body["error"]), body
    return dict(body["error"])


# --- system -----------------------------------------------------------------------------------
def test_health_both_paths(client: TestClient) -> None:
    for path in ("/health", f"{API}/health"):
        assert client.get(path).json() == {"status": "ok"}


def test_status_reports_deterministic_mode_and_counts(client: TestClient) -> None:
    s = client.get(f"{API}/status").json()
    assert (s["status"], s["database_ok"], s["curriculum_loaded"]) == ("ok", True, True)
    assert (s["llm_mode"], s["fallback_active"], s["llm_model"]) == ("deterministic", True, None)
    assert s["counts"]["concepts"] == 6 and s["counts"]["edges"] == 6 and len(s["curriculum_hash"]) >= 16


def test_status_is_degraded_and_graph_endpoints_say_not_ready_without_a_curriculum(
    empty_client: TestClient,
) -> None:
    assert empty_client.get(f"{API}/status").json()["status"] == "degraded"
    r = empty_client.get(f"{API}/concepts")
    assert r.status_code == 503 and err(r)["code"] == "not_ready"


def test_eval_latest_404_then_200(client: TestClient) -> None:
    from sqlmodel import Session

    from knowtrace.models import EvalResult, EvalRun

    r = client.get(f"{API}/eval/latest")
    assert r.status_code == 404 and err(r)["code"] == "not_found"
    with Session(client.app.state.engine) as s:  # type: ignore[attr-defined]
        run = EvalRun(seed=1, n_students=3, curriculum_hash="h")
        s.add(run)
        s.flush()
        s.add(EvalResult(run_id=run.id, method="graph_bayes", metric="top1", value=0.9, n=3))
        s.commit()
    ok = client.get(f"{API}/eval/latest").json()
    assert ok["metrics"] == [
        {"method": "graph_bayes", "metric": "top1", "value": 0.9, "n": 3, "detail": None}
    ]


# --- curriculum (P0-1) -------------------------------------------------------------------------
def test_concepts_list_filter_and_pagination(client: TestClient) -> None:
    page = client.get(f"{API}/concepts", params={"limit": 4}).json()
    assert (page["total"], page["limit"], page["offset"], len(page["items"])) == (6, 4, 0, 4)
    rest = client.get(f"{API}/concepts", params={"limit": 4, "offset": 4}).json()
    assert len(rest["items"]) == 2
    assert [c["id"] for c in client.get(f"{API}/concepts", params={"q": "ratio"}).json()["items"]] == ["D"]
    assert client.get(f"{API}/concepts", params={"strand": "nope"}).json()["total"] == 0


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "x"}])
def test_pagination_bounds_are_validated(client: TestClient, params: dict) -> None:
    r = client.get(f"{API}/concepts", params=params)
    assert r.status_code == 422 and err(r)["code"] == "validation_error"
    assert err(r)["details"][0]["loc"][0] == "query"


def test_concept_detail_and_unknown_concept(client: TestClient) -> None:
    c = client.get(f"{API}/concepts/F").json()
    assert (
        c["prerequisites"] == ["C", "E"]
        and c["ancestors"] == {"C": 1, "E": 1, "B": 2, "A": 3}
        and c["item_count"] >= 4
    )
    r = client.get(f"{API}/concepts/ZZ")
    assert r.status_code == 404 and err(r)["code"] == "unknown_concept"


def test_graph_is_topologically_ordered_with_edges(client: TestClient) -> None:
    g = client.get(f"{API}/graph").json()
    order = [n["id"] for n in g["nodes"]]
    assert order.index("A") < order.index("B") < order.index("C") < order.index("F")
    assert {"prerequisite": "B", "dependent": "C"} in g["edges"] and len(g["edges"]) == 6


def test_items_never_expose_the_answer_key(client: TestClient) -> None:
    page = client.get(f"{API}/items", params={"concept_id": "C"}).json()
    assert page["total"] >= 3
    for it in page["items"] + [client.get(f"{API}/items/i.C.1").json()]:
        assert "answer" not in it and set(it) == {
            "id",
            "stem",
            "kind",
            "choices",
            "concept_ids",
            "primary_concept_id",
            "difficulty",
        }
    r = client.get(f"{API}/items/nope")
    assert r.status_code == 404 and err(r)["code"] == "not_found"
    assert client.get(f"{API}/items", params={"concept_id": "ZZ"}).status_code == 404


# --- students & attempts (P0-2, P0-5) ------------------------------------------------------------
def test_create_student(client: TestClient) -> None:
    a = client.post(f"{API}/students", json={})
    assert a.status_code == 201 and a.json()["pseudonym"].startswith("student-")
    b = client.post(f"{API}/students", json={"pseudonym": "ada.l-01"})
    assert (
        b.status_code == 201
        and client.get(f"{API}/students/{b.json()['id']}").json()["pseudonym"] == "ada.l-01"
    )


@pytest.mark.parametrize(
    "body",
    [
        {"pseudonym": "x"},
        {"pseudonym": "has space"},
        {"pseudonym": "a@b.com"},
        {"name": "Real Name"},
        {"pseudonym": 5},
    ],
)
def test_create_student_validation(client: TestClient, body: dict) -> None:
    r = client.post(f"{API}/students", json=body)
    assert r.status_code == 422 and err(r)["code"] == "validation_error"


def test_duplicate_pseudonym_and_unknown_student(client: TestClient) -> None:
    client.post(f"{API}/students", json={"pseudonym": "dup-one"})
    r = client.post(f"{API}/students", json={"pseudonym": "dup-one"})
    assert r.status_code == 409 and err(r)["code"] == "conflict"
    for url in ("", "/mastery", "/diagnoses", "/forecast?concept_id=A"):
        assert client.get(f"{API}/students/nope{url}").status_code == 404, url
    assert (
        client.post(f"{API}/students/nope/attempts", json={"item_id": "i.A.1", "answer": "a"}).status_code
        == 404
    )


def test_attempt_validation_and_domain_errors(client: TestClient) -> None:
    sid = new_student(client)
    url = f"{API}/students/{sid}/attempts"
    for body in (
        {},
        {"item_id": "i.A.1"},
        {"item_id": "i.A.1", "answer": ""},
        {"item_id": "i.A.1", "answer": "a", "is_correct": True},  # clients cannot claim correctness
        {"item_id": "i.A.1", "answer": "a", "latency_ms": -5},
    ):
        r = client.post(url, json=body)
        assert r.status_code == 422 and err(r)["code"] == "validation_error", body
    assert client.post(url, json={"item_id": "nope", "answer": "a"}).status_code == 404
    bad = client.post(url, json={"item_id": "i.A.1", "answer": "zzz"})  # not one of the choices
    assert bad.status_code == 422 and err(bad)["code"] == "invalid_answer"
    # nothing was recorded by the failed requests
    assert all(m["n_obs"] == 0 for m in client.get(f"{API}/students/{sid}/mastery").json()["concepts"])


def test_attempts_are_graded_server_side_and_update_mastery(client: TestClient) -> None:
    sid = new_student(client)
    right = attempt(client, sid, "i.A.1", "a")["attempt"]
    assert right["seq"] == 1 and right["is_correct"] and right["mastery"]["A"] > 0.3
    m = {x["concept_id"]: x for x in client.get(f"{API}/students/{sid}/mastery").json()["concepts"]}
    assert m["A"]["n_obs"] == 1 and m["A"]["p_mastery"] == right["mastery"]["A"] and m["B"]["n_obs"] == 0


def test_multi_concept_item_updates_each_concept(client: TestClient) -> None:
    sid = new_student(client)
    r = attempt(client, sid, "i.F.multi", "a")["attempt"]
    assert set(r["mastery"]) == {"F", "C"} and all(v > 0.3 for v in r["mastery"].values())


# --- forecast (D2) --------------------------------------------------------------------------------
def test_forecast_curve(client: TestClient) -> None:
    sid = new_student(client)
    attempt(client, sid, "i.A.1", "a")
    f = client.get(f"{API}/students/{sid}/forecast", params={"concept_id": "A", "horizon": 10}).json()
    pts = f["points"]
    assert len(pts) == 11 and pts[0]["step"] == 0 and pts[0]["p_mastery"] == f["current_mastery"]
    assert all(p["p_lo"] <= p["p_mastery"] <= p["p_hi"] for p in pts)
    assert pts[-1]["p_mastery"] > pts[0]["p_mastery"] and 0 < f["p_next_correct"] < 1
    assert f["steps_to_mastery"] is None or f["steps_to_mastery"] > 0


def test_forecast_validation_and_unknown_concept(client: TestClient) -> None:
    sid = new_student(client)
    base = f"{API}/students/{sid}/forecast"
    assert client.get(base).status_code == 422  # concept_id required
    assert client.get(base, params={"concept_id": "A", "horizon": 0}).status_code == 422
    assert client.get(base, params={"concept_id": "A", "horizon": 61}).status_code == 422
    r = client.get(base, params={"concept_id": "ZZ"})
    assert r.status_code == 404 and err(r)["code"] == "unknown_concept"


# --- diagnoses & lessons: lookups ---------------------------------------------------------------
def test_unknown_diagnosis_and_lesson(client: TestClient) -> None:
    assert client.get(f"{API}/diagnoses/nope").status_code == 404
    assert client.post(f"{API}/diagnoses/nope/answer", json={"answer": "a"}).status_code == 404
    assert client.post(f"{API}/diagnoses/nope/recheck", json={"answer": "a"}).status_code == 404
    assert client.post(f"{API}/diagnoses/nope/abandon").status_code == 404
    assert client.get(f"{API}/lessons/nope").status_code == 404
    assert client.post(f"{API}/lessons/nope/complete").status_code == 404
    assert client.post(f"{API}/lessons/nope/steps/1/view", json={}).status_code == 404


def test_probe_answer_validation(client: TestClient) -> None:
    sid = new_student(client)
    d = attempt(client, sid, "i.D.1", "b")["diagnosis"]
    url = f"{API}/diagnoses/{d['id']}/answer"
    for body in ({}, {"answer": ""}, {"answer": "a", "item_id": "i.A.1"}):
        assert client.post(url, json=body).status_code == 422, body
    bad = client.post(url, json={"answer": "zzz"})
    assert bad.status_code == 422 and err(bad)["code"] == "invalid_answer"
    assert (
        client.get(f"{API}/diagnoses/{d['id']}").json()["probes_used"] == 0
    )  # failed request recorded nothing
