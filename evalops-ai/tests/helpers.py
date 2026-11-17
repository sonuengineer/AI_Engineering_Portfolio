"""Builders for DB-backed tests (use the real services, not raw SQL)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.core.db import session_scope
from app.models import Dataset, EvaluatorConfig, ModelConfig, Project, PromptTemplate, PromptVersion, Target
from app.services.datasets import create_version, parse_jsonl

KB = "Payment is due within 30 days of the invoice date. Annual plans receive a 15 percent discount."

CASES = [
    {"id": "c1", "input": "When is payment due?", "expected_output": "Payment is due within 30 days of the invoice date.",
     "reference_contexts": [KB], "expected_citations": ["kb-1"],
     "metadata": {"expected_keywords": ["30 days"],
                  "scripted_outputs": {"good": {"answer": "Payment is due within 30 days of the invoice date.",
                                                "citations": ["kb-1"]},
                                       "bad": {"answer": "Payment is due within 90 days.", "citations": []}}}},
    {"id": "c2", "input": "What discount do annual plans get?", "expected_output": "Annual plans receive a 15 percent discount.",
     "reference_contexts": [KB], "expected_citations": ["kb-1"],
     "metadata": {"expected_keywords": ["15 percent"],
                  "scripted_outputs": {"good": {"answer": "Annual plans receive a 15 percent discount.",
                                                "citations": ["kb-1"]},
                                       "bad": {"answer": "Annual plans receive a 15 percent discount.",
                                               "citations": ["kb-1"]}}}},
    {"id": "c3", "input": "Contact me at someone@example.com about payment due dates",
     "expected_output": "Payment is due within 30 days of the invoice date.", "reference_contexts": [KB],
     "expected_citations": ["kb-1"],
     "metadata": {"expected_keywords": ["30 days"],
                  "scripted_outputs": {"good": {"answer": "Payment is due within 30 days of the invoice date.",
                                                "citations": ["kb-1"]},
                                       "bad": {"answer": "I do not know.", "citations": []}}}},
]


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return ("\n".join(json.dumps(r) for r in rows) + "\n").encode()


def build_project(org_id: uuid.UUID, slug: str = "proj") -> dict[str, Any]:
    with session_scope() as s:
        p = Project(org_id=org_id, name=slug, slug=slug)
        s.add(p)
        s.flush()
        ds = Dataset(org_id=org_id, project_id=p.id, name="qa")
        s.add(ds)
        s.flush()
        dv = create_version(s, ds, parse_jsonl(jsonl(CASES), max_cases=100))
        t = PromptTemplate(org_id=org_id, project_id=p.id, name="t")
        s.add(t)
        s.flush()
        pv = PromptVersion(org_id=org_id, template_id=t.id, version=1, system_prompt="sys",
                           user_template="Context: {{contexts}}\nQ: {{input}}", content_hash="h")
        s.add(pv)
        s.flush()
        targets = {}
        for name, provider, params in [("local", "local", {}), ("good", "mock_scripted", {"script": "good"}),
                                       ("bad", "mock_scripted", {"script": "bad"})]:
            mc = ModelConfig(org_id=org_id, project_id=p.id, name=name, provider=provider,
                             model="local-extractive-v1" if provider == "local" else "scripted", params=params,
                             price_in_per_1k=0.001, price_out_per_1k=0.002)
            s.add(mc)
            s.flush()
            tg = Target(org_id=org_id, project_id=p.id, name=name, kind="llm", model_config_id=mc.id,
                        prompt_version_id=pv.id)
            s.add(tg)
            s.flush()
            targets[name] = tg.id
        evs = []
        for name, type_, kind, params, thr in [
            ("answer", "normalized_match", "deterministic", {"allow_containment": True}, None),
            ("keywords", "contains", "deterministic", {}, None),
            ("citations", "citation_correctness", "deterministic", {}, 1.0),
            ("judge", "llm_judge", "judge", {}, 4.0),
        ]:
            e = EvaluatorConfig(org_id=org_id, project_id=p.id, name=name, type=type_, kind=kind, params=params,
                                threshold=thr, gating=kind == "deterministic")
            s.add(e)
            s.flush()
            evs.append(e.id)
        return {"project_id": p.id, "dataset_id": ds.id, "dv_id": dv.id, "targets": targets, "evaluators": evs}
