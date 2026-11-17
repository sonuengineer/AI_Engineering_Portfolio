import asyncio

from conftest import get_user

from app.mcp_server import build_server
from app.services.retrieval import hybrid_search


def test_hybrid_search_uses_both_signals_and_ranks_relevant_first(db):
    user = get_user(db, "analyst@acme.example")
    hits = hybrid_search(db, user.org_id, "Harbor Marine rejected batch adhesion failure", k=5)
    assert hits[0].document_title.startswith("Harbor Marine")
    assert any(h.vector_rank is not None for h in hits) and any(h.keyword_rank is not None for h in hits)
    assert hits == sorted(hits, key=lambda h: h.rerank_score, reverse=True)


def test_retrieval_is_tenant_scoped(db):
    globex = get_user(db, "admin@globex.example")
    titles = {h.document_title for h in hybrid_search(db, globex.org_id, "payment terms discount policy", k=10)}
    assert titles == {"Globex Confidential Pricing"}


def test_mcp_exposes_read_tools_but_never_send_email():
    server = build_server()

    async def go():
        names = {t.name for t in await server.list_tools()}
        res = await server.call_tool("get_pending_quotations", {})
        return names, res

    names, res = asyncio.run(go())
    assert "search_documents" in names and "send_email" not in names
    assert "Q-2026-0412" in str(res)
