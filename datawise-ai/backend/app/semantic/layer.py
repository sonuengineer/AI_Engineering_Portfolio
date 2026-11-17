"""Semantic layer: the single source of truth for business metrics, dimensions, join paths and the
table/column allowlist. The compiler builds SQL only from these definitions; the validator checks
generated SQL against the same allowlist.

Kept as a typed Python registry (not YAML) so it is type-checked and importable without a parser.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Join:
    alias: str
    sql: str
    requires: tuple[str, ...] = ()  # other join aliases that must be present first


@dataclass(frozen=True)
class Fact:
    name: str
    description: str
    from_sql: str
    time_column: str
    base_where: tuple[str, ...] = ()
    joins: dict[str, Join] = field(default_factory=dict)


@dataclass(frozen=True)
class Metric:
    name: str
    label: str
    description: str
    fact: str
    sql: str
    fmt: str  # currency | number | percent | days
    synonyms: tuple[str, ...] = ()
    default_rank_metric: bool = False


@dataclass(frozen=True)
class DimensionBinding:
    sql: str
    joins: tuple[str, ...] = ()


@dataclass(frozen=True)
class Dimension:
    name: str
    label: str
    description: str
    synonyms: tuple[str, ...]
    bindings: dict[str, DimensionBinding]  # fact name -> how to compute this dimension on that fact
    is_time: bool = False
    filterable: bool = True


# ---------------------------------------------------------------- facts (join paths)

FACTS: dict[str, Fact] = {
    "sales": Fact(
        name="sales",
        description="Order lines joined to their orders. Cancelled orders are always excluded.",
        from_sql="orders o JOIN order_items oi ON oi.order_id = o.order_id",
        time_column="o.order_date",
        base_where=("o.status <> 'cancelled'",),
        joins={
            "c": Join("c", "JOIN customers c ON c.customer_id = o.customer_id"),
            "p": Join("p", "JOIN products p ON p.product_id = oi.product_id"),
            "s": Join("s", "JOIN suppliers s ON s.supplier_id = p.supplier_id", requires=("p",)),
        },
    ),
    "web": Fact(
        name="web",
        description="Website sessions with funnel flags (viewed product, added to cart, converted).",
        from_sql="web_sessions ws",
        time_column="ws.session_date",
    ),
    "deliveries": Fact(
        name="deliveries",
        description="Inbound supplier deliveries with promised vs actual dates. Time = delivered_date.",
        from_sql="supplier_deliveries sd",
        time_column="sd.delivered_date",
        joins={
            "s": Join("s", "JOIN suppliers s ON s.supplier_id = sd.supplier_id"),
            "p": Join("p", "JOIN products p ON p.product_id = sd.product_id"),
        },
    ),
}

# ---------------------------------------------------------------- metrics

METRICS: dict[str, Metric] = {
    m.name: m
    for m in [
        Metric("revenue", "Revenue", "Sum of quantity * unit_price over order lines, excluding cancelled orders.",
               "sales", "ROUND(SUM(oi.quantity * oi.unit_price), 2)", "currency",
               ("revenue", "sales", "total sales", "sales amount", "income", "turnover", "gmv", "earnings",
                "spend", "spent", "money"), default_rank_metric=True),
        Metric("order_count", "Orders", "Number of distinct non-cancelled orders.",
               "sales", "COUNT(DISTINCT o.order_id)", "number",
               ("order count", "number of orders", "count of orders", "orders", "order volume",
                "how many orders", "purchases")),
        Metric("avg_order_value", "Average order value", "Revenue divided by number of orders.",
               "sales", "ROUND(SUM(oi.quantity * oi.unit_price) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2)",
               "currency", ("average order value", "avg order value", "aov", "average basket",
                            "average basket size", "average order size", "average order")),
        Metric("units_sold", "Units sold", "Sum of order line quantities, excluding cancelled orders.",
               "sales", "SUM(oi.quantity)", "number",
               ("units sold", "units", "items sold", "quantity sold", "quantity", "volume sold")),
        Metric("active_customers", "Active customers", "Number of distinct customers with a non-cancelled order.",
               "sales", "COUNT(DISTINCT o.customer_id)", "number",
               ("active customers", "number of customers", "how many customers", "customer count",
                "unique customers", "count of customers", "distinct customers")),
        Metric("conversion_rate", "Conversion rate", "Share of web sessions that converted (0..1).",
               "web", "ROUND(AVG(CAST(ws.converted AS INTEGER)), 4)", "percent",
               ("conversion rate", "conversion", "conversions rate", "convert", "converting")),
        Metric("sessions", "Sessions", "Number of web sessions.",
               "web", "COUNT(ws.session_id)", "number",
               ("sessions", "web sessions", "visits", "site visits", "traffic")),
        Metric("on_time_delivery_rate", "On-time delivery rate",
               "Share of supplier deliveries delivered on or before the promised date (0..1).",
               "deliveries", "ROUND(AVG(CAST(sd.on_time AS INTEGER)), 4)", "percent",
               ("on-time delivery rate", "on time delivery rate", "on-time delivery", "on time delivery",
                "on-time rate", "on time rate", "delivery reliability", "on-time", "on time", "late deliveries")),
        Metric("avg_lead_time_days", "Average lead time (days)",
               "Average days between purchase order and delivery.",
               "deliveries", "ROUND(AVG(sd.lead_time_days), 2)", "days",
               ("average lead time", "avg lead time", "lead time", "lead times", "delivery time",
                "delivery times", "days to deliver")),
    ]
}

# ---------------------------------------------------------------- dimensions


def _time_bindings(grain: str) -> dict[str, DimensionBinding]:
    return {
        name: DimensionBinding(f"CAST(DATE_TRUNC('{grain}', {fact.time_column}) AS DATE)")
        for name, fact in FACTS.items()
    }


DIMENSIONS: dict[str, Dimension] = {
    d.name: d
    for d in [
        Dimension("month", "Month", "Calendar month of the event date.",
                  ("by month", "per month", "each month", "monthly", "month by month", "month over month",
                   "over time", "trend", "trends", "by months", "every month"),
                  _time_bindings("month"), is_time=True, filterable=False),
        Dimension("quarter", "Quarter", "Calendar quarter of the event date.",
                  ("by quarter", "per quarter", "each quarter", "quarterly", "quarter over quarter",
                   "by quarters"),
                  _time_bindings("quarter"), is_time=True, filterable=False),
        Dimension("year", "Year", "Calendar year of the event date.",
                  ("by year", "per year", "each year", "yearly", "annual", "annually", "year over year",
                   "yoy", "by years"),
                  _time_bindings("year"), is_time=True, filterable=False),
        Dimension("product", "Product", "Product name.",
                  ("products", "product", "items", "skus", "sku"),
                  {"sales": DimensionBinding("p.name", ("p",)), "deliveries": DimensionBinding("p.name", ("p",))}),
        Dimension("category", "Category", "Product category.",
                  ("product categories", "product category", "categories", "category"),
                  {"sales": DimensionBinding("p.category", ("p",)),
                   "deliveries": DimensionBinding("p.category", ("p",))}),
        Dimension("customer", "Customer", "Customer name.",
                  ("customers", "customer", "clients", "client", "accounts", "buyers"),
                  {"sales": DimensionBinding("c.name", ("c",))}),
        Dimension("customer_segment", "Customer segment", "Consumer, Small Business or Enterprise.",
                  ("customer segments", "customer segment", "segments", "segment"),
                  {"sales": DimensionBinding("c.segment", ("c",))}),
        Dimension("region", "Region", "Sales region (customer region for sales, session region for web).",
                  ("regions", "region", "areas", "geography", "geographies"),
                  {"sales": DimensionBinding("c.region", ("c",)), "web": DimensionBinding("ws.region")}),
        Dimension("supplier", "Supplier", "Supplier name.",
                  ("suppliers", "supplier", "vendors", "vendor"),
                  {"sales": DimensionBinding("s.name", ("s",)), "deliveries": DimensionBinding("s.name", ("s",))}),
        Dimension("channel", "Sales channel", "Order channel: web, mobile or store.",
                  ("sales channels", "sales channel", "channels", "channel"),
                  {"sales": DimensionBinding("o.channel")}),
        Dimension("traffic_source", "Traffic source", "Web session acquisition source.",
                  ("traffic sources", "traffic source", "marketing channels", "sources", "source"),
                  {"web": DimensionBinding("ws.traffic_source")}),
        Dimension("device", "Device", "Web session device type.",
                  ("devices", "device", "device type", "device types", "platforms"),
                  {"web": DimensionBinding("ws.device")}),
    ]
}

# Low-cardinality dimension values loaded at runtime from the analytics DB for filter matching.
VALUE_QUERIES: dict[str, str] = {
    "category": "SELECT DISTINCT category FROM products",
    "region": "SELECT DISTINCT region FROM customers",
    "customer_segment": "SELECT DISTINCT segment FROM customers",
    "channel": "SELECT DISTINCT channel FROM orders",
    "traffic_source": "SELECT DISTINCT traffic_source FROM web_sessions",
    "device": "SELECT DISTINCT device FROM web_sessions",
    "supplier": "SELECT name FROM suppliers",
    "product": "SELECT name FROM products",
    "customer": "SELECT name FROM customers",
}

# ---------------------------------------------------------------- allowlist (validator + catalog)

ALLOWED_TABLES: dict[str, tuple[str, ...]] = {
    "suppliers": ("supplier_id", "name", "country"),
    "products": ("product_id", "name", "category", "supplier_id", "unit_cost", "list_price"),
    "customers": ("customer_id", "name", "segment", "region", "city", "signup_date"),
    "orders": ("order_id", "customer_id", "order_date", "status", "channel"),
    "order_items": ("order_item_id", "order_id", "product_id", "quantity", "unit_price"),
    "web_sessions": ("session_id", "session_date", "region", "traffic_source", "device", "viewed_product",
                     "added_to_cart", "converted"),
    "supplier_deliveries": ("delivery_id", "supplier_id", "product_id", "ordered_date", "promised_date",
                            "delivered_date", "quantity", "lead_time_days", "on_time"),
}

TABLE_DESCRIPTIONS: dict[str, str] = {
    "suppliers": "Companies that supply products.",
    "products": "Product catalog (120 products in 8 categories).",
    "customers": "Customers with segment and region.",
    "orders": "Customer orders. status: completed | shipped | cancelled | returned.",
    "order_items": "Order lines: product, quantity and the unit price actually charged.",
    "web_sessions": "Website sessions with funnel flags for conversion analysis.",
    "supplier_deliveries": "Inbound deliveries: promised vs delivered dates, lead time and on-time flag.",
}

ALLOWED_COLUMNS: frozenset[str] = frozenset(c for cols in ALLOWED_TABLES.values() for c in cols)

DATA_START = "2024-11-01"
DATA_END = "2026-10-31"


def metrics_for_fact(fact: str) -> list[str]:
    return [m.name for m in METRICS.values() if m.fact == fact]


def dimensions_for_fact(fact: str) -> list[str]:
    return [d.name for d in DIMENSIONS.values() if fact in d.bindings]


def describe_for_prompt() -> str:
    """Compact text description of the semantic layer for LLM planner prompts."""
    lines = ["METRICS (name: description [fact]):"]
    for m in METRICS.values():
        lines.append(f"- {m.name}: {m.description} [{m.fact}] synonyms={', '.join(m.synonyms[:5])}")
    lines.append("DIMENSIONS (name: description; facts):")
    for d in DIMENSIONS.values():
        lines.append(f"- {d.name}: {d.description}; facts={','.join(d.bindings)}")
    lines.append(f"DATA RANGE: {DATA_START} to {DATA_END}.")
    lines.append("Metrics from different facts cannot be combined in one plan.")
    return "\n".join(lines)
