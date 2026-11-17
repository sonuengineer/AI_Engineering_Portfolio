# ruff: noqa: E501  (data tables)
"""Build the demo datasets used by the seed script (deterministic; no randomness).

- demo_support_qa_v1.jsonl: RAG-style QA over a small synthetic help-center KB ("Acme Cloud").
  Each case carries reference contexts, expected answer, expected doc citations, keywords and two
  scripted outputs: "v1" (a good baseline script) and "v2" (a deliberately regressed script used to
  demonstrate regression detection). Scripted outputs are hand-written fixtures, NOT model output.
- demo_extraction_v1.jsonl: structured-extraction cases for json_schema_valid / numeric_tolerance.

Run: uv run --directory backend python ../benchmarks/tools/build_demo_datasets.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]

KB = {
    "kb-billing-01": "Acme Cloud invoices are issued on the first day of each month. Payment is due within 30 days "
                     "of the invoice date. Annual plans are billed upfront and receive a 15 percent discount.",
    "kb-billing-02": "Refunds are available within 14 days of purchase for monthly plans. Annual plans can be "
                     "refunded pro rata within 60 days. Refunds are returned to the original payment method.",
    "kb-sec-01": "Acme Cloud encrypts data at rest with AES-256 and in transit with TLS 1.3. Encryption keys are "
                 "rotated every 90 days. Customer-managed keys are available on the Enterprise plan.",
    "kb-sec-02": "Single sign-on supports SAML 2.0 and OpenID Connect. SSO is included in the Business and "
                 "Enterprise plans. SCIM user provisioning is available on the Enterprise plan only.",
    "kb-limits-01": "The Starter plan allows 5 projects and 10 GB of storage. The Business plan allows 50 projects "
                    "and 500 GB of storage. The Enterprise plan has unlimited projects and 5 TB of storage.",
    "kb-limits-02": "The public API is rate limited to 600 requests per minute per workspace. Bursts above the limit "
                    "receive HTTP 429 responses with a Retry-After header.",
    "kb-support-01": "Standard support responds within 24 hours on business days. Premium support responds within "
                     "1 hour for severity 1 incidents, 24 hours a day. Premium support is included in Enterprise.",
    "kb-data-01": "Deleted projects are kept in a recycle bin for 30 days and can be restored by an admin. After 30 "
                  "days they are permanently erased. Backups are taken every 6 hours and retained for 35 days.",
    "kb-data-02": "Data residency is available in the EU (Frankfurt) and US (Virginia) regions. The region is chosen "
                  "when the workspace is created and cannot be changed later.",
    "kb-uptime-01": "Acme Cloud offers a 99.9 percent monthly uptime SLA on Business and 99.95 percent on Enterprise. "
                    "Service credits of 10 percent are issued for each 0.1 percent below the SLA, up to 50 percent.",
}

# (id, question, expected_answer, citations, keywords, tags, v2_mode)
# v2_mode: None = same as v1; "wrong" = incorrect answer; "nocite" = drops citations;
#          "halluc" = adds an unsupported sentence; "refuse" = says it does not know
CASES = [
    ("qa-001", "When is payment due for an Acme Cloud invoice?", "Payment is due within 30 days of the invoice date.",
     ["kb-billing-01"], ["30 days"], ["billing"], None),
    ("qa-002", "What discount do annual plans receive?", "Annual plans receive a 15 percent discount.",
     ["kb-billing-01"], ["15 percent"], ["billing"], "wrong"),
    ("qa-003", "How long do I have to request a refund on a monthly plan?",
     "Refunds are available within 14 days of purchase for monthly plans.", ["kb-billing-02"], ["14 days"],
     ["billing"], None),
    ("qa-004", "Can annual plans be refunded?", "Annual plans can be refunded pro rata within 60 days.",
     ["kb-billing-02"], ["pro rata", "60 days"], ["billing"], "nocite"),
    ("qa-005", "What encryption is used for data at rest?", "Data at rest is encrypted with AES-256.",
     ["kb-sec-01"], ["AES-256"], ["security"], None),
    ("qa-006", "How often are encryption keys rotated?", "Encryption keys are rotated every 90 days.",
     ["kb-sec-01"], ["90 days"], ["security"], "halluc"),
    ("qa-007", "Which SSO protocols are supported?", "Single sign-on supports SAML 2.0 and OpenID Connect.",
     ["kb-sec-02"], ["SAML", "OpenID Connect"], ["security"], None),
    ("qa-008", "Which plan includes SCIM provisioning?", "SCIM user provisioning is available on the Enterprise plan only.",
     ["kb-sec-02"], ["Enterprise"], ["security"], "wrong"),
    ("qa-009", "How many projects does the Starter plan allow?", "The Starter plan allows 5 projects.",
     ["kb-limits-01"], ["5 projects"], ["limits"], None),
    ("qa-010", "How much storage does the Business plan include?", "The Business plan includes 500 GB of storage.",
     ["kb-limits-01"], ["500 GB"], ["limits"], None),
    ("qa-011", "What is the API rate limit?", "The public API is rate limited to 600 requests per minute per workspace.",
     ["kb-limits-02"], ["600 requests per minute"], ["limits", "api"], "refuse"),
    ("qa-012", "What happens when I exceed the API rate limit?",
     "Requests above the limit receive HTTP 429 responses with a Retry-After header.", ["kb-limits-02"],
     ["429", "Retry-After"], ["limits", "api"], None),
    ("qa-013", "How fast does standard support respond?", "Standard support responds within 24 hours on business days.",
     ["kb-support-01"], ["24 hours"], ["support"], None),
    ("qa-014", "What is the premium support response time for severity 1 incidents?",
     "Premium support responds within 1 hour for severity 1 incidents.", ["kb-support-01"], ["1 hour"],
     ["support"], "halluc"),
    ("qa-015", "How long are deleted projects kept before permanent erasure?",
     "Deleted projects are kept in a recycle bin for 30 days.", ["kb-data-01"], ["30 days"], ["data"], None),
    ("qa-016", "How often are backups taken?", "Backups are taken every 6 hours and retained for 35 days.",
     ["kb-data-01"], ["6 hours", "35 days"], ["data"], None),
    ("qa-017", "Which data residency regions are available?",
     "Data residency is available in the EU (Frankfurt) and US (Virginia) regions.", ["kb-data-02"],
     ["Frankfurt", "Virginia"], ["data"], "nocite"),
    ("qa-018", "Can I change the data region of an existing workspace?",
     "No. The region is chosen when the workspace is created and cannot be changed later.", ["kb-data-02"],
     ["cannot be changed"], ["data"], None),
    ("qa-019", "What uptime SLA does the Enterprise plan have?", "The Enterprise plan has a 99.95 percent monthly uptime SLA.",
     ["kb-uptime-01"], ["99.95"], ["sla"], None),
    ("qa-020", "What is the maximum service credit for SLA breaches?",
     "Service credits are capped at 50 percent.", ["kb-uptime-01"], ["50 percent"], ["sla"], "wrong"),
    ("qa-021", "Are customer-managed encryption keys available on the Business plan?",
     "No. Customer-managed keys are available on the Enterprise plan.", ["kb-sec-01"], ["Enterprise"],
     ["security"], None),
    ("qa-022", "Is SSO included in the Business plan and does it support SAML?",
     "Yes. SSO is included in the Business plan and supports SAML 2.0.", ["kb-sec-02"], ["Business", "SAML"],
     ["security"], None),
]

WRONG = {
    "qa-002": "Annual plans receive a 25 percent discount.",
    "qa-008": "SCIM user provisioning is available on all plans.",
    "qa-020": "Service credits are capped at 100 percent.",
}
HALLUC = " The maximum is also configurable per customer by contacting the CEO directly."


def build_support() -> list[dict[str, object]]:
    rows = []
    for cid, q, ans, cites, kws, tags, v2_mode in CASES:
        contexts = [KB[c] for c in cites]
        v1 = {"answer": ans, "citations": cites, "contexts": contexts}
        if v2_mode is None:
            v2 = v1
        elif v2_mode == "wrong":
            v2 = {"answer": WRONG[cid], "citations": cites, "contexts": contexts}
        elif v2_mode == "nocite":
            v2 = {"answer": ans, "citations": [], "contexts": contexts}
        elif v2_mode == "halluc":
            v2 = {"answer": ans + HALLUC, "citations": cites, "contexts": contexts}
        else:
            v2 = {"answer": "I do not know.", "citations": [], "contexts": []}
        rows.append({
            "id": cid, "input": q, "expected_output": ans, "reference_contexts": contexts,
            "expected_citations": cites, "tags": tags,
            "metadata": {"expected_keywords": kws, "scripted_outputs": {"v1": v1, "v2": v2},
                         "v2_fault": v2_mode},
        })
    return rows


INVOICE_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor": {"type": "string"},
        "invoice_number": {"type": "string", "pattern": "^INV-[0-9]{4,}$"},
        "total": {"type": "number"},
        "currency": {"type": "string", "enum": ["USD", "EUR", "GBP"]},
    },
    "required": ["vendor", "invoice_number", "total", "currency"],
    "additionalProperties": False,
}

EXTRACTION = [
    ("ex-001", "Invoice INV-1042 from Northwind Supply, total 1,250.00 USD.", "Northwind Supply", "INV-1042", 1250.0, "USD", None),
    ("ex-002", "Bluepeak Energy billed us 980.50 EUR on invoice INV-2201.", "Bluepeak Energy", "INV-2201", 980.5, "EUR", None),
    ("ex-003", "Invoice number INV-3310, vendor Harbor Marine, amount GBP 4,400.", "Harbor Marine", "INV-3310", 4400.0, "GBP", "bad_total"),
    ("ex-004", "Summit Foods sent INV-0457 for 312.99 USD.", "Summit Foods", "INV-0457", 312.99, "USD", None),
    ("ex-005", "Cedar Valley Utilities, INV-7781, total due 15,020.10 USD.", "Cedar Valley Utilities", "INV-7781", 15020.1, "USD", "bad_json"),
    ("ex-006", "Ironclad Construction invoice INV-5523 totals 2,000 EUR.", "Ironclad Construction", "INV-5523", 2000.0, "EUR", None),
    ("ex-007", "Payment request INV-6610 from Atlas Trading: 75.25 USD.", "Atlas Trading", "INV-6610", 75.25, "USD", "bad_schema"),
    ("ex-008", "Falcon Logistics INV-9002, 18,400.00 GBP.", "Falcon Logistics", "INV-9002", 18400.0, "GBP", None),
    ("ex-009", "Invoice INV-1203 from Oakridge Wholesale for 640.00 USD.", "Oakridge Wholesale", "INV-1203", 640.0, "USD", None),
    ("ex-010", "Riverbend Imports, invoice INV-3344, 99.99 EUR.", "Riverbend Imports", "INV-3344", 99.99, "EUR", None),
]


def build_extraction() -> list[dict[str, object]]:
    rows = []
    for cid, text, vendor, inv, total, cur, v2_fault in EXTRACTION:
        good = {"vendor": vendor, "invoice_number": inv, "total": total, "currency": cur}
        if v2_fault == "bad_total":
            v2: object = json.dumps({**good, "total": total * 10})
        elif v2_fault == "bad_json":
            v2 = "vendor: " + vendor + ", total: " + str(total)
        elif v2_fault == "bad_schema":
            v2 = json.dumps({**good, "invoice_number": inv.replace("INV-", "#"), "notes": "extra"})
        else:
            v2 = json.dumps(good)
        rows.append({
            "id": cid,
            "input": text,
            "expected_output": json.dumps(good),
            "tags": ["extraction", "invoice"],
            "metadata": {"json_schema": INVOICE_SCHEMA, "expected_number": total,
                         "scripted_outputs": {"v1": json.dumps(good), "v2": v2}, "v2_fault": v2_fault},
        })
    return rows


def write(name: str, rows: list[dict[str, object]]) -> None:
    path = OUT / name
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=True) + "\n")
    print(f"wrote {path} ({len(rows)} cases)")


if __name__ == "__main__":
    write("demo_support_qa_v1.jsonl", build_support())
    write("demo_extraction_v1.jsonl", build_extraction())
