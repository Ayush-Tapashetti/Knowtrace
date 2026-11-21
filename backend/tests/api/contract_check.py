"""API contract verification: drive every endpoint of the real app and check each response against
`docs/openapi.json` (status code, body shape, error envelope), then check the exported file is current.

Run on its own:  PYTHONPATH=src python -m tests.api.contract_check [--frontend]
It also runs inside pytest (test_contract.py). Offline: in-memory database, no model, no network.
`--frontend` additionally regenerates the TypeScript types and fails if the committed ones differ.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from knowtrace.cli.export_openapi import DEFAULT_OUT, render
from tests.api.support import API, make_client

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "backend" / "content" / "seed"
JsonT = dict[str, Any]


class Validator:
    """The small slice of JSON Schema that FastAPI/Pydantic emits (enough for an honest shape check)."""

    def __init__(self, spec: JsonT) -> None:
        self.spec = spec

    def ref(self, node: JsonT) -> JsonT:
        while "$ref" in node:
            node = self.spec["components"]["schemas"][node["$ref"].rsplit("/", 1)[1]]
        return node

    def check(self, value: Any, schema: JsonT, where: str = "$") -> list[str]:
        s = self.ref(schema)
        if "anyOf" in s or "oneOf" in s:
            options = s.get("anyOf") or s["oneOf"]
            attempts = [self.check(value, o, where) for o in options]
            return (
                [] if any(not a for a in attempts) else [f"{where}: matches none of {len(options)} options"]
            )
        if "enum" in s and value not in s["enum"]:
            return [f"{where}: {value!r} not in enum"]
        if "const" in s and value != s["const"]:
            return [f"{where}: {value!r} != const"]
        t = s.get("type")
        if t == "null":
            return [] if value is None else [f"{where}: expected null"]
        if t == "object" or "properties" in s:
            if not isinstance(value, dict):
                return [f"{where}: expected object, got {type(value).__name__}"]
            errs = [f"{where}.{k}: missing required field" for k in s.get("required", []) if k not in value]
            props = s.get("properties", {})
            extra = s.get("additionalProperties")
            for k, v in value.items():
                if k in props:
                    errs += self.check(v, props[k], f"{where}.{k}")
                elif isinstance(extra, dict):
                    errs += self.check(v, extra, f"{where}.{k}")
                elif extra is True or (not props and extra is None):
                    continue  # free-form object
                else:
                    errs.append(f"{where}.{k}: undocumented field")
            return errs
        if t == "array":
            if not isinstance(value, list):
                return [f"{where}: expected array"]
            item = s.get("items", {})
            return [e for i, v in enumerate(value) for e in self.check(v, item, f"{where}[{i}]")]
        ok = {
            "string": isinstance(value, str),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, int | float) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
        }.get(t or "", True)
        return [] if ok else [f"{where}: expected {t}, got {type(value).__name__}"]


class Driver:
    def __init__(self, client: TestClient, spec: JsonT) -> None:
        self.c, self.spec, self.v = client, spec, Validator(spec)
        self.seen: set[tuple[str, str]] = set()
        self.statuses: dict[tuple[str, str], set[int]] = {}
        self.problems: list[str] = []
        self.calls = 0

    def req(self, method: str, template: str, expect: int, *, path: dict[str, str] | None = None,
            body: JsonT | None = None, query: JsonT | None = None) -> Any:  # fmt: skip
        url = API + template.format(**(path or {}))
        # (`template` is re-prefixed below to match the contract keys)
        r = self.c.request(method, url, json=body, params=query)
        self.calls += 1
        template = API + template  # the contract lists full paths
        key = (method.lower(), template)
        self.seen.add(key)
        self.statuses.setdefault(key, set()).add(r.status_code)
        ops = self.spec["paths"].get(template, {})
        op = ops.get(method.lower())
        if op is None:
            self.problems.append(f"{method} {template}: not in the contract")
            return None
        if r.status_code != expect:
            self.problems.append(
                f"{method} {template}: expected {expect}, got {r.status_code}: {r.text[:120]}"
            )
        resp = op["responses"].get(str(r.status_code))
        if resp is None:
            self.problems.append(f"{method} {template}: status {r.status_code} is not documented")
            return None
        schema = resp.get("content", {}).get("application/json", {}).get("schema")
        data = r.json() if r.content else None
        if schema is not None:
            self.problems += [
                f"{method} {template} [{r.status_code}] {e}" for e in self.v.check(data, schema)
            ]
        if r.status_code >= 400:
            err = (data or {}).get("error", {})
            if not {"code", "message"} <= set(err):
                self.problems.append(f"{method} {template}: error body is not the envelope")
        return data


def _truth() -> tuple[set[str], dict[str, str], dict[str, set[str]]]:
    edges = json.loads((SEED / "edges.json").read_text())
    desc: dict[str, set[str]] = {}
    for e in edges:
        desc.setdefault(e["prereq_id"], set()).add(e["concept_id"])
    broken, stack = {"equiv_frac"}, ["equiv_frac"]
    while stack:
        for ch in desc.get(stack.pop(), ()):
            if ch not in broken:
                broken.add(ch)
                stack.append(ch)
    items = json.loads((SEED / "items.json").read_text())
    return broken, {i["id"]: i["answer"] for i in items}, {}


def _scenario(d: Driver) -> None:
    broken, keys, _ = _truth()
    links = json.loads((SEED / "item_concepts.json").read_text())
    concepts_of: dict[str, set[str]] = {}
    for link in links:
        concepts_of.setdefault(link["item_id"], set()).add(link["concept_id"])

    def answer(item: JsonT, knows: bool = True) -> str:
        right = keys[item["id"]]
        if knows and not (concepts_of[item["id"]] & broken):
            return right
        return next(c["id"] for c in item["choices"] if c["id"] != right)

    # system, before any evaluation exists
    d.req("get", "/health", 200)
    d.req("get", "/status", 200)
    d.req("get", "/eval/latest", 404)
    from knowtrace.services import eval_runner as ev  # a small real run, saved through the service

    # curriculum
    page = d.req("get", "/concepts", 200, query={"limit": 100})
    cid = page["items"][0]["id"]
    d.req("get", "/concepts/{concept_id}", 200, path={"concept_id": "equiv_frac"})
    d.req("get", "/concepts/{concept_id}", 404, path={"concept_id": "no_such_concept"})
    d.req("get", "/graph", 200)
    items = d.req("get", "/items", 200, query={"concept_id": cid, "limit": 5})
    d.req("get", "/items/{item_id}", 200, path={"item_id": items["items"][0]["id"]})
    d.req("get", "/items/{item_id}", 404, path={"item_id": "no_such_item"})

    # learner
    d.req("post", "/students", 422, body={"pseudonym": "!!"})
    sid = d.req("post", "/students", 201, body={})["id"]
    d.req("get", "/students/{student_id}", 200, path={"student_id": sid})
    d.req("get", "/students/{student_id}", 404, path={"student_id": "missing"})
    all_items = d.req("get", "/items", 200, query={"limit": 100})
    total = all_items["total"]
    pool = [
        i
        for off in range(0, total, 100)
        for i in d.req("get", "/items", 200, query={"limit": 100, "offset": off})["items"]
    ]
    for item in pool:
        if item["id"].rsplit(".", 1)[1] in {"1", "2", "3"} and not (concepts_of[item["id"]] & broken):
            d.req(
                "post",
                "/students/{student_id}/attempts",
                201,
                path={"student_id": sid},
                body={"item_id": item["id"], "answer": answer(item)},
            )
    d.req(
        "post",
        "/students/{student_id}/attempts",
        422,
        path={"student_id": sid},
        body={"item_id": pool[0]["id"], "answer": "zzz"},
    )
    d.req(
        "post",
        "/students/{student_id}/attempts",
        404,
        path={"student_id": sid},
        body={"item_id": "no_such_item", "answer": "a"},
    )
    d.req("get", "/students/{student_id}/mastery", 200, path={"student_id": sid})
    d.req(
        "get",
        "/students/{student_id}/forecast",
        200,
        path={"student_id": sid},
        query={"concept_id": "equiv_frac", "horizon": 10},
    )

    # diagnosis -> lesson -> recheck
    start = next(i for i in pool if i["id"] == "i.add_unlike_frac.2")
    res = d.req(
        "post",
        "/students/{student_id}/attempts",
        201,
        path={"student_id": sid},
        body={"item_id": start["id"], "answer": answer(start)},
    )
    dx = res["diagnosis"]
    d.req(
        "post",
        "/students/{student_id}/attempts",
        409,
        path={"student_id": sid},
        body={"item_id": start["id"], "answer": answer(start)},
    )
    d.req("get", "/diagnoses/{diagnosis_id}", 404, path={"diagnosis_id": "missing"})
    d.req("get", "/students/{student_id}/diagnoses", 200, path={"student_id": sid})
    d.req(
        "post",
        "/diagnoses/{diagnosis_id}/recheck",
        409,
        path={"diagnosis_id": dx["id"]},
        body={"answer": "a"},
    )
    for _ in range(12):
        dx = d.req("get", "/diagnoses/{diagnosis_id}", 200, path={"diagnosis_id": dx["id"]})
        if dx["state"] == "PROBING":
            dx = d.req(
                "post",
                "/diagnoses/{diagnosis_id}/answer",
                200,
                path={"diagnosis_id": dx["id"]},
                body={"answer": answer(dx["pending_item"])},
            )["diagnosis"]
        elif dx["state"] == "LESSON_ASSIGNED":
            lesson = d.req("get", "/lessons/{lesson_id}", 200, path={"lesson_id": dx["lesson_id"]})
            d.req("get", "/lessons/{lesson_id}", 404, path={"lesson_id": "missing"})
            d.req("post", "/lessons/{lesson_id}/complete", 409, path={"lesson_id": lesson["id"]})
            for step in lesson["steps"]:
                body = {"answer": keys[step["item"]["id"]]} if step["item"] else {}
                d.req(
                    "post",
                    "/lessons/{lesson_id}/steps/{position}/view",
                    200,
                    path={"lesson_id": lesson["id"], "position": str(step["position"])},
                    body=body,
                )
            dx = d.req("post", "/lessons/{lesson_id}/complete", 200, path={"lesson_id": lesson["id"]})
        elif dx["state"] == "RECHECKING":
            dx = d.req(
                "post",
                "/diagnoses/{diagnosis_id}/recheck",
                200,
                path={"diagnosis_id": dx["id"]},
                body={"answer": keys[dx["pending_item"]["id"]]},
            )["diagnosis"]
        else:
            break
    # a second diagnosis to abandon
    fail = next(i for i in pool if i["id"] == "i.add_unlike_frac.3")
    res = d.req(
        "post",
        "/students/{student_id}/attempts",
        201,
        path={"student_id": sid},
        body={"item_id": fail["id"], "answer": answer(fail)},
    )
    if res["diagnosis"]:
        d.req("post", "/diagnoses/{diagnosis_id}/abandon", 200, path={"diagnosis_id": res["diagnosis"]["id"]})
        d.req("post", "/diagnoses/{diagnosis_id}/abandon", 409, path={"diagnosis_id": res["diagnosis"]["id"]})

    # evaluation, now that a run exists
    from sqlmodel import Session

    with Session(d.c.app.state.engine) as s:  # type: ignore[attr-defined]
        ev.persist(s, ev.run_experiment(d.c.app.state.bundle, ev.EvalParams(students=30)))  # type: ignore[attr-defined]
    d.req("get", "/eval/latest", 200)


def run() -> tuple[Driver, list[str]]:
    spec = json.loads(DEFAULT_OUT.read_text(encoding="utf-8"))
    problems: list[str] = []
    if DEFAULT_OUT.read_text(encoding="utf-8") != render():
        problems.append("docs/openapi.json is stale: run python -m knowtrace.cli.export_openapi")
    with make_client(SEED) as client:
        d = Driver(client, spec)
        _scenario(d)
    declared = {(m, p) for p, ops in spec["paths"].items() for m in ops if m != "parameters"}
    problems += [f"{m.upper()} {p}: never exercised" for m, p in sorted(declared - d.seen)]
    problems += d.problems
    return d, problems


def frontend_types_fresh() -> list[str]:
    npm = shutil.which("npm")
    if npm is None:
        return ["npm not found: frontend type freshness not verified"]
    out = subprocess.run(
        [npm, "run", "check:types-fresh"], cwd=ROOT / "frontend", capture_output=True, text=True, check=False
    )
    return (
        [] if out.returncode == 0 else ["frontend types are stale vs docs/openapi.json: " + out.stdout[-300:]]
    )


def main() -> int:
    d, problems = run()
    if "--frontend" in sys.argv:
        problems += frontend_types_fresh()
    print(
        f"{d.calls} calls across {len(d.seen)} operations; statuses seen: "
        + ", ".join(sorted({str(s) for v in d.statuses.values() for s in v}))
    )
    for p in problems:
        print("PROBLEM", p)
    print("CONTRACT:", "FAIL" if problems else "OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
