"""Deterministic, rule-based stand-in for an LLM.

It implements each task with transparent heuristics over the structured payload. It is used for
keyless demos and tests and is always reported as provider "local".
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from app.llm.base import LLMRequest, StructuredOutputError, T, Usage, estimate_tokens
from app.llm.embeddings import tokenize
from app.schemas.llm_outputs import (
    CustomerFinding,
    EmailDraft,
    Evidence,
    EvidenceAnalysis,
    GroundedAnswer,
    Hypothesis,
    WorkflowPlan,
)

Handler = Callable[[dict[str, Any]], BaseModel]
_HANDLERS: dict[str, Handler] = {}


def handles(task: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _HANDLERS[task] = fn
        return fn

    return deco


_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT_RE.split(text.replace("\n", " ")) if p.strip()]
    return [p for p in parts if len(p) > 20]


@handles("answer_question")
def _answer(payload: dict[str, Any]) -> GroundedAnswer:
    q_terms = set(tokenize(payload["question"]))
    scored: list[tuple[float, float, int, str]] = []  # (score, coverage, ctx id, sentence)
    for ctx in payload["contexts"]:
        for pos, sent in enumerate(split_sentences(ctx["text"])):
            s_terms = set(tokenize(sent))
            if not s_terms or not q_terms:
                continue
            overlap = len(q_terms & s_terms)
            if overlap == 0:
                continue
            coverage = overlap / len(q_terms)
            score = coverage + 0.15 * overlap / len(s_terms) ** 0.5 - pos * 0.005
            scored.append((score, coverage, ctx["id"], sent))
    scored.sort(key=lambda x: x[0], reverse=True)
    # Abstain unless the best sentence covers most of the question's content terms.
    if not scored or scored[0][1] < 0.6:
        return GroundedAnswer(
            answer="I could not find enough evidence in the indexed documents to answer this.",
            insufficient_evidence=True,
        )
    best = scored[0][0]
    picked: list[tuple[int, str]] = []
    seen: set[str] = set()
    for score, _cov, cid, sent in scored:
        if score < 0.75 * best:  # keep only sentences close to the best match
            break
        key = sent.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        picked.append((cid, sent))
        if len(picked) == 3:
            break
    body = " ".join(f"{s.rstrip('.')} [{cid}]." for cid, s in picked)
    return GroundedAnswer(
        answer=f"Based on the indexed documents: {body}",
        cited_context_ids=sorted({cid for cid, _ in picked}),
    )


_NUM_WORDS = {"five": 5, "ten": 10, "twenty": 20, "three": 3, "fifteen": 15}


@handles("plan_workflow")
def _plan(payload: dict[str, Any]) -> WorkflowPlan:
    goal = payload["goal"].lower()
    top_n = 10
    m = re.search(r"top\s+(\d{1,2}|" + "|".join(_NUM_WORDS) + r")\b", goal)
    if m:
        top_n = int(m.group(1)) if m.group(1).isdigit() else _NUM_WORDS[m.group(1)]
    months = 6
    mm = re.search(r"(\d{1,2})\s+months?", goal)
    if mm:
        months = max(1, min(24, int(mm.group(1))))
    decline = any(w in goal for w in ("declin", "drop", "decreas", "fall", "churn", "lower"))
    customers = any(w in goal for w in ("customer", "account", "client", "purchas", "order"))
    if decline and customers:
        return WorkflowPlan(
            intent="customer_decline_investigation",
            steps=["data_agent", "research_agent", "analysis_agent", "report_agent", "action_agent"],
            top_n=top_n,
            lookback_months=months,
            rationale="Goal mentions declining customer purchases: quantify decline from ERP, "
            "gather documents/emails, separate evidence from hypotheses, report, draft follow-ups.",
        )
    return WorkflowPlan(
        intent="unsupported",
        steps=[],
        rationale="The local rule-based planner only supports customer purchase-decline "
        "investigations. Use chat for document questions.",
    )


# Specific phrases, not bare words: "delay" alone matches column headers like "Average delay (days)"
# and "quality" matches praise ("quality remains good"). Known limitation: no negation handling --
# a real LLM provider is expected to do better (see docs/roadmap-and-limitations.md).
_SIGNALS: list[tuple[tuple[str, ...], str]] = [
    (
        ("competitor", "cheaper", "price match", "pricing remains", "pricing pressure", "below our current"),
        "Competitive pricing pressure may be pulling volume away",
    ),
    (
        ("arrived late", "late deliver", "late hydraulic", "delivery delay", "shipment delayed", "missed delivery"),
        "Delivery reliability problems may be reducing order volume",
    ),
    (
        ("defect", "quality complaint", "rejected batch", "rejecting the batch", "non-conform", "failed adhesion"),
        "Product quality issues may have reduced trust",
    ),
    (
        ("budget freeze", "cost cutting", "spending freeze", "downturn"),
        "Customer-side budget constraints may be reducing demand",
    ),
    (
        ("contract expired", "contract renewal", "renewal negotiations", "agreement expired"),
        "Contract renewal timing may be affecting purchases",
    ),
]


@handles("analyze_evidence")
def _analyze(payload: dict[str, Any]) -> EvidenceAnalysis:
    findings: list[CustomerFinding] = []
    for c in payload["customers"]:
        ev: list[Evidence] = [
            Evidence(
                statement=(
                    f"Revenue fell from {c['prior_revenue']:,.2f} to {c['recent_revenue']:,.2f} "
                    f"({c['change_pct']:+.1f}%) comparing the prior vs most recent "
                    f"{c['window_months']} months."
                ),
                source="erp_orders",
            )
        ]
        if c.get("avg_delay_recent", 0) > 2:
            ev.append(
                Evidence(
                    statement=f"Average delivery delay in the recent window was "
                    f"{c['avg_delay_recent']:.1f} days (prior window {c['avg_delay_prior']:.1f}).",
                    source="erp_orders",
                )
            )
        for q in c.get("pending_quotes", []):
            ev.append(
                Evidence(
                    statement=f"Quotation {q['quote_number']} ({q['amount']:,.2f}, {q['product_line']}) "
                    f"has been pending since {q['issued_on']}.",
                    source=f"erp_quotations:{q['quote_number']}",
                )
            )
        texts: list[tuple[str, str]] = [
            (f"email:{e['id']}", f"{e['subject']} {e['body']}") for e in c.get("emails", [])
        ] + [(f"document:{d['document_id']}#p{d.get('page') or 1}", d["text"]) for d in c.get("documents", [])]
        for src, text in texts:
            snippet = text.strip().replace("\n", " ")
            ev.append(Evidence(statement=f'Record states: "{snippet[:220]}"', source=src))
        hyps: list[Hypothesis] = []
        for keywords, statement in _SIGNALS:
            support = [src for src, text in texts if any(k in text.lower() for k in keywords)]
            if statement.startswith("Delivery") and c.get("avg_delay_recent", 0) > 2:
                support.append("erp_orders")
            if support:
                conf = "high" if len(support) >= 3 else "medium" if len(support) == 2 else "low"
                hyps.append(Hypothesis(statement=statement, confidence=conf, supporting_sources=support))
        if c.get("pending_quotes"):
            hyps.append(
                Hypothesis(
                    statement="Open quotations suggest the customer is still evaluating purchases; "
                    "a stalled quote may indicate price or terms objections",
                    confidence="low",
                    supporting_sources=[f"erp_quotations:{q['quote_number']}" for q in c["pending_quotes"]],
                )
            )
        if not hyps:
            hyps.append(
                Hypothesis(
                    statement="No explanatory signal found in available records; needs account-manager input",
                    confidence="low",
                    supporting_sources=[],
                )
            )
        top = hyps[0].statement.lower()
        action = "Schedule an account review call to confirm the drivers and address " + (
            "pricing"
            if "pricing" in top
            else "delivery performance"
            if "delivery" in top
            else "quality concerns"
            if "quality" in top
            else "open questions"
        )
        findings.append(
            CustomerFinding(
                customer_id=c["customer_id"],
                customer_name=c["name"],
                evidence=ev,
                hypotheses=hyps,
                recommended_action=action,
            )
        )
    declining = len(findings)
    summary = (
        f"{declining} of the top {payload['top_n']} customers show declining purchases over the last "
        f"{payload['window_months']} months. Evidence below is taken directly from ERP, CRM, email "
        "and document records; hypotheses are rule-based inferences and must be validated."
    )
    return EvidenceAnalysis(summary=summary, findings=findings)


@handles("draft_email")
def _draft(payload: dict[str, Any]) -> EmailDraft:
    first = payload["contact_name"].split()[0]
    topic = payload.get("topic") or "your recent orders"
    body = (
        f"Hi {first},\n\n"
        f"I hope you are well. I am reaching out because we value our partnership with "
        f"{payload['customer_name']} and noticed a change in your recent ordering. "
        f"We would like to understand whether {topic} is affecting your plans and how we can help.\n\n"
        "Would you be open to a 30-minute review call next week? We can also revisit any open "
        "quotations.\n\n"
        f"Best regards,\n{payload['sender_name']}"
    )
    return EmailDraft(subject=f"{payload['customer_name']}: account review", body=body)


class LocalProvider:
    name = "local"

    def generate(self, request: LLMRequest, schema: type[T]) -> tuple[T, Usage]:
        handler = _HANDLERS.get(request.task)
        if handler is None:
            raise StructuredOutputError(f"local adapter has no handler for task {request.task!r}")
        t0 = time.perf_counter()
        result = handler(request.payload)
        if not isinstance(result, schema):
            result = schema.model_validate(result.model_dump())
        latency = int((time.perf_counter() - t0) * 1000)
        usage = Usage(
            provider="local",
            model="rule-based-v1",
            input_tokens=estimate_tokens(request.system + request.user),
            output_tokens=estimate_tokens(result.model_dump_json()),
            estimated_cost_usd=0.0,
            latency_ms=latency,
            tokens_are_estimates=True,
        )
        return result, usage
