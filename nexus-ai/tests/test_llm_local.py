from app.agents.investigation import ground_sources
from app.llm.base import LLMRequest, estimate_cost
from app.llm.embeddings import HashingEmbedder
from app.llm.local import LocalProvider
from app.schemas.llm_outputs import (
    CustomerFinding,
    Evidence,
    EvidenceAnalysis,
    GroundedAnswer,
    Hypothesis,
    WorkflowPlan,
)
from app.services.chat import validate_citations

P = LocalProvider()


def _answer(question, contexts):
    req = LLMRequest(task="answer_question", system="", user="", payload={"question": question, "contexts": contexts})
    return P.generate(req, GroundedAnswer)


def test_local_answer_cites_supporting_context_and_reports_local_provider():
    ctx = [
        {"id": 1, "text": "Standard payment terms are net 45 days from invoice date.", "title": "H", "page": 1},
        {"id": 2, "text": "Safety helmets are stocked in three sizes for all sites.", "title": "C", "page": None},
    ]
    ans, usage = _answer("What are the standard payment terms?", ctx)
    assert ans.cited_context_ids == [1] and "net 45" in ans.answer and not ans.insufficient_evidence
    assert usage.provider == "local" and usage.tokens_are_estimates and usage.estimated_cost_usd == 0


def test_local_answer_abstains_when_coverage_low():
    ctx = [
        {"id": 1, "text": "The capital expenditure budget freeze affects spare parts orders.", "title": "x", "page": 1}
    ]
    ans, _ = _answer("What is the capital of France?", ctx)
    assert ans.insufficient_evidence and ans.cited_context_ids == []


def test_planner_extracts_parameters_and_rejects_unsupported():
    plan, _ = P.generate(
        LLMRequest(
            "plan_workflow", "", "", {"goal": "Why are purchases declining for our top 5 customers over 3 months?"}
        ),
        WorkflowPlan,
    )
    assert plan.intent == "customer_decline_investigation" and plan.top_n == 5 and plan.lookback_months == 3
    plan2, _ = P.generate(LLMRequest("plan_workflow", "", "", {"goal": "Write me a poem about the sea"}), WorkflowPlan)
    assert plan2.intent == "unsupported" and plan2.steps == []


def test_citation_validation_strips_hallucinated_ids():
    raw = GroundedAnswer(answer="Fact A [1]. Fact B [7].", cited_context_ids=[1, 9])
    v = validate_citations(raw, n_contexts=3)
    assert v.cited_context_ids == [1] and "[7]" not in v.answer and "[1]" in v.answer


def test_answer_without_valid_citations_is_marked_insufficient():
    v = validate_citations(GroundedAnswer(answer="Unsupported claim [5].", cited_context_ids=[5]), 2)
    assert v.insufficient_evidence


def test_ground_sources_drops_ungathered_sources_and_unknown_customers():
    analysis = EvidenceAnalysis(
        summary="s",
        findings=[
            CustomerFinding(
                customer_id="c1",
                customer_name="A",
                recommended_action="x",
                evidence=[
                    Evidence(statement="ok", source="erp_orders"),
                    Evidence(statement="made up", source="email:fake"),
                ],
                hypotheses=[
                    Hypothesis(statement="h", confidence="low", supporting_sources=["email:e1", "document:zzz#p1"])
                ],
            ),
            CustomerFinding(
                customer_id="ghost", customer_name="Ghost", recommended_action="x", evidence=[], hypotheses=[]
            ),
        ],
    )
    customers = [{"customer_id": "c1", "pending_quotes": [], "emails": [{"id": "e1"}], "documents": []}]
    g = ground_sources(analysis, customers)
    assert [f.customer_id for f in g.findings] == ["c1"]
    assert [e.source for e in g.findings[0].evidence] == ["erp_orders"]
    assert g.findings[0].hypotheses[0].supporting_sources == ["email:e1"]


def test_hashing_embedder_is_deterministic_normalized_and_lexical():
    e = HashingEmbedder()
    a, b, c = e.embed(["late hydraulic deliveries", "late hydraulic deliveries", "marine coating quality"])
    assert a == b and abs(sum(x * x for x in a) - 1.0) < 1e-9
    near = e.embed(["hydraulic deliveries were late"])[0]
    cos = lambda u, v: sum(x * y for x, y in zip(u, v, strict=True))  # noqa: E731
    assert cos(a, near) > cos(a, c)


def test_cost_estimate_uses_price_table():
    assert estimate_cost("gpt-4o-mini", 1_000_000, 0) == 0.15
    assert estimate_cost("unknown-model", 1000, 1000) == 0.0


def test_customer_excerpt_keeps_only_that_customers_rows():
    from app.agents.investigation import customer_excerpt

    chunk = (
        "[Sheet Q3 2026] Customer: Bluepeak Energy; Average delay (days): 6.4; Comment: Repeated late deliveries\n"
        "Customer: Northwind Fabrication; Average delay (days): 0.4; Comment: On target\n"
        "Customer: Harbor Marine Systems; Comment: Replacement shipment delayed 11 days"
    )
    ex = customer_excerpt(chunk, "Northwind Fabrication")
    assert "On target" in ex and "late" not in ex and "Bluepeak" not in ex
    assert customer_excerpt(chunk, "Unknown Co") == ""
