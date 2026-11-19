"""Canonical content hash, so every diagnosis can be tied to the exact curriculum that produced it."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from knowtrace.domain.types import AtomSpec, Graph, ItemSpec, QRow


def curriculum_hash(
    graph: Graph,
    items: Mapping[str, ItemSpec],
    qmatrix: Mapping[str, QRow],
    atoms: Sequence[AtomSpec],
) -> str:
    """SHA-256 over a canonical (sorted, normalised) form. Independent of input ordering."""
    canon = {
        "concepts": [
            [c.id, c.tier, c.p_init, c.p_learn, c.p_slip, c.p_guess, c.p_forget, c.half_life_days, c.name]
            for c in (graph.concepts[k] for k in sorted(graph.concepts))
        ],
        "edges": sorted([dep, pre] for dep, pres in graph.parents.items() for pre in pres),
        "items": [
            [
                i.id,
                i.kind.value,
                i.answer,
                sorted(i.choices),
                i.tolerance_abs,
                i.tolerance_rel,
                i.difficulty,
                i.p_slip,
                i.p_guess,
            ]
            for i in (items[k] for k in sorted(items))
        ],
        "qmatrix": [[k, sorted(qmatrix[k].concepts), qmatrix[k].primary] for k in sorted(qmatrix)],
        "atoms": [
            [a.id, a.concept_id, a.kind.value, a.est_seconds, a.order_hint, a.item_id, a.body]
            for a in sorted(atoms, key=lambda a: a.id)
        ],
    }
    blob = json.dumps(canon, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("ascii")).hexdigest()
