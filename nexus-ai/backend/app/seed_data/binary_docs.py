"""Definitions for seed documents generated as real PDF / DOCX / XLSX files at seed time."""

NCR_PDF_TITLE = "Harbor Marine Systems -- Non-Conformance Report NCR-2026-117"
NCR_PDF_PAGES = [
    "Non-Conformance Report NCR-2026-117\n"
    "Customer: Harbor Marine Systems\n"
    "Product line: Marine Coatings\n"
    "Date opened: 14 May 2026\n\n"
    "Summary: Harbor Marine Systems rejected batch MC-5521 of anti-corrosion coating after field "
    "tests showed adhesion failure on two vessels. The customer filed a formal quality complaint.",
    "Root cause analysis (page 2)\n\n"
    "The adhesion failure was traced to a curing-agent supplier change in April 2026. "
    "The replacement shipment was delayed by 11 days. Harbor Marine Systems stated that it will "
    "dual-source marine coatings until two consecutive batches pass inspection.",
    "Corrective actions (page 3)\n\n"
    "Acme reverted to the original curing-agent supplier and added batch-level adhesion testing. "
    "A credit for batch MC-5521 was issued. Harbor Marine Systems requested a quality review meeting.",
]

HANDBOOK_DOCX_TITLE = "Customer Service Handbook"
HANDBOOK_DOCX = [
    (
        "Payment terms",
        [
            "Standard payment terms are net 45 days from invoice date.",
            "Customers in the Platinum tier may request net 60 days with finance approval.",
        ],
    ),
    (
        "Order escalation",
        [
            "Orders delayed by more than 7 days must be escalated to the logistics manager.",
            "Customers must be notified proactively of any delay longer than 3 days.",
        ],
    ),
    (
        "Account reviews",
        [
            "Platinum and Gold accounts receive a quarterly business review.",
            "Account reviews must cover order trends, open quotations and service issues.",
        ],
    ),
]

DELIVERY_XLSX_TITLE = "Delivery Performance Q3 2026"
DELIVERY_XLSX_ROWS = [
    ("Customer", "Orders shipped", "On-time %", "Average delay (days)", "Comment"),
    ("Bluepeak Energy", 38, 61, 6.4, "Repeated late hydraulic deliveries after warehouse relocation"),
    ("Northwind Fabrication", 52, 96, 0.4, "On target"),
    ("Harbor Marine Systems", 21, 88, 1.9, "Replacement shipment for MC-5521 delayed 11 days"),
    ("Summit Foods Processing", 17, 94, 0.7, "On target"),
    ("Ironclad Construction", 25, 92, 0.9, "On target"),
    ("Cedar Valley Utilities", 30, 95, 0.5, "On target"),
]
