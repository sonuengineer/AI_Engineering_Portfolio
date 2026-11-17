"""Deterministic, rule-based planner (LLM_PROVIDER=local).

This is NOT an LLM and never pretends to be one: responses carry provider="local". It maps a
question onto the semantic layer with phrase matching:

1. time phrases -> TimeRange (app.services.timeparse), blanked out of the text
2. longest-match phrase scan over metric synonyms, dimension synonyms and known dimension values
3. a dimension noun becomes a GROUP BY only when a grouping cue surrounds it
   ("by region", "top 5 products", "which category", "customers who spent the most")
4. ranking words -> ORDER BY metric + LIMIT; comparisons ("over 10k") -> HAVING
5. anything ambiguous -> needs_clarification with ready-to-send option questions
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.llm.base import PlannerProvider, Usage
from app.schemas.plan import Clarification, Filter, OrderBy, PlannerOutcome, QueryPlan
from app.semantic.layer import DATA_END, DATA_START, DIMENSIONS, METRICS
from app.services.compiler import check_plan
from app.services.timeparse import NUMBER_WORDS, parse_time
from app.services.values import ValueIndex

LOWER_IS_BETTER = {"avg_lead_time_days"}
GENERIC_TIME_PHRASES = {"trend", "trends", "over time"}
BEST_SELLING = ("best selling", "best-selling", "bestselling", "top selling", "top-selling", "most popular")

DESC_WORDS = {"top", "best", "highest", "most", "largest", "biggest", "leading", "greatest", "maximum", "max"}
ASC_WORDS = {"bottom", "worst", "lowest", "least", "fewest", "smallest", "minimum", "min"}
CUE_WORDS = DESC_WORDS | ASC_WORDS | {"by", "per", "each", "every", "across", "among", "which", "what", "compare",
                                      "comparing", "rank", "ranking", "vs", "versus", "breakdown", "split"}
SKIP_WORDS = {"the", "our", "my", "all", "of", "selling", "performing", "valuable", "profitable", "active",
              "loyal", "popular", "five", "ten", "three", "two", "four", "six", "seven", "eight", "nine",
              "twenty", "fifteen", "twelve", "__value__", "different", "individual", "most", "least"}
FOLLOW_CUE = re.compile(r"^\s+(with|that|who|which|ranked|sorted|ordered|had|have|has|generating|generated|"
                        r"bought|spent|sold|drove|driving|bring|brought)\b")
STOPWORDS = {
    "what", "was", "were", "is", "are", "the", "a", "an", "of", "for", "in", "on", "by", "show", "me", "give",
    "list", "how", "much", "many", "did", "do", "does", "our", "we", "my", "i", "total", "and", "to", "from",
    "with", "per", "each", "which", "top", "best", "worst", "highest", "lowest", "most", "least", "please",
    "can", "you", "tell", "about", "us", "at", "it", "its", "this", "that", "be", "been", "get", "find", "all",
    "overall", "number", "breakdown", "compare", "between", "vs", "versus", "who", "had", "have", "has",
    "there", "their", "they", "biggest", "largest", "smallest", "rate", "value", "average", "avg", "sum",
    "count", "amount", "metric", "data", "report", "chart", "see", "want", "know", "like", "would", "could",
    "should", "make", "made", "generate", "generated", "across", "among", "every", "so", "far", "up", "than",
    "more", "less", "over", "under", "above", "below", "time", "period", "any", "some", "where", "when", "why",
    "as", "or", "if", "into", "out", "ranked", "sorted", "order", "group", "grouped", "split", "s",
}


@dataclass
class _Match:
    start: int
    end: int
    kind: str  # metric | dim_noun | dim_time | value | best_selling
    payload: object
    phrase: str


def _normalize(q: str) -> str:
    t = q.lower().replace(chr(0x2019), "'").replace(chr(0x2018), "'")
    t = re.sub(r"'s\b", "", t)
    t = re.sub(r"[?!,;:\"()\[\]{}]", " ", t)
    t = t.replace("'", " ")
    return re.sub(r"\s+", " ", t).strip()


def _blank(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for s, e in spans:
        for i in range(s, e):
            chars[i] = " "
    return "".join(chars)


_DIM_SINGULAR = {
    "product": "product", "category": "category", "customer": "customer", "customer_segment": "customer segment",
    "region": "region", "supplier": "supplier", "channel": "sales channel", "traffic_source": "traffic source",
    "device": "device", "month": "month", "quarter": "quarter", "year": "year",
}
_RANK_CANDIDATES = ["revenue", "order_count", "units_sold", "on_time_delivery_rate", "avg_lead_time_days",
                    "conversion_rate", "sessions"]


class LocalPlanner(PlannerProvider):
    name = "local"
    model = "rules-v1"

    def __init__(self, values: ValueIndex, as_of: date, max_rows: int) -> None:
        self.as_of = as_of
        self.max_rows = max_rows
        self._phrases: list[tuple[str, str, object]] = []
        for m in METRICS.values():
            for syn in m.synonyms:
                self._phrases.append((syn, "metric", m.name))
        for d in DIMENSIONS.values():
            for syn in d.synonyms:
                self._phrases.append((syn, "dim_time" if d.is_time else "dim_noun", d.name))
        for phrase, pairs in values.aliases().items():
            self._phrases.append((phrase, "value", pairs))
        for p in BEST_SELLING:
            self._phrases.append((p, "best_selling", "units_sold"))
        self._compiled = [
            (re.compile(r"(?<![\w-])" + re.escape(p.lower()) + r"(?![\w-])"), p.lower(), k, pl)
            for p, k, pl in self._phrases
        ]

    # ------------------------------------------------------------------ public

    def plan(self, question: str) -> tuple[PlannerOutcome, Usage]:
        return self._plan(question), Usage()

    # ------------------------------------------------------------------ helpers

    def _scan(self, text: str) -> list[_Match]:
        found: list[_Match] = []
        for rx, phrase, kind, payload in self._compiled:
            for m in rx.finditer(text):
                found.append(_Match(m.start(), m.end(), kind, payload, phrase))
        # greedy longest-first, non-overlapping
        found.sort(key=lambda x: (-(x.end - x.start), x.start))
        taken: list[_Match] = []
        for f in found:
            if all(f.end <= t.start or f.start >= t.end for t in taken):
                taken.append(f)
        return sorted(taken, key=lambda x: x.start)

    @staticmethod
    def _has_cue_before(prefix: str) -> bool:
        words = prefix.split()
        for i in range(len(words) - 1, -1, -1):
            w = words[i]
            if w in CUE_WORDS:
                return True
            if w in SKIP_WORDS or w.isdigit() or w in NUMBER_WORDS:
                continue
            return False
        return False

    def _canonical(self, metric: str, dims: list[str], time_phrase: str, filters: list[Filter],
                   top: int | None = None) -> str:
        mphrase = METRICS[metric].synonyms[0]
        if top is not None and dims:
            q = f"top {top} {DIMENSIONS[dims[0]].synonyms[0]} by {mphrase}"
        else:
            q = mphrase + "".join(f" by {_DIM_SINGULAR[d]}" for d in dims)
        for f in filters:
            if f.kind == "dimension" and isinstance(f.value, str):
                q += f" for {f.value}"
        if time_phrase:
            q += f" {time_phrase}"
        return q[0].upper() + q[1:]

    # ------------------------------------------------------------------ main

    def _plan(self, question: str) -> PlannerOutcome:  # noqa: C901 -- linear rule pipeline
        text = _normalize(question)
        tp = parse_time(text, self.as_of)
        time_phrase = " ".join(text[s:e].strip() for s, e in tp.spans).strip()
        work = _blank(text, tp.spans)
        matches = self._scan(work)
        assumptions: list[str] = []

        # value positions, replaced by a marker so cue detection can skip over them
        value_spans = [(m.start, m.end) for m in matches if m.kind == "value"]
        cue_text = work
        for s, e in sorted(value_spans, reverse=True):
            cue_text = cue_text[:s] + "__value__".ljust(e - s) + cue_text[e:]

        metrics: list[str] = []
        dims_time: list[tuple[str, str]] = []
        dims_cat: list[str] = []
        mentioned_dims: list[str] = []
        value_matches: list[_Match] = []
        for i, m in enumerate(matches):
            if m.kind in ("metric", "best_selling"):
                if m.payload not in metrics:
                    metrics.append(str(m.payload))
                if m.kind == "best_selling":
                    assumptions.append(f"'{m.phrase}' interpreted as units sold.")
            elif m.kind == "dim_time":
                dims_time.append((str(m.payload), m.phrase))
            elif m.kind == "value":
                value_matches.append(m)
            elif m.kind == "dim_noun":
                dim = str(m.payload)
                mentioned_dims.append(dim)
                prev = matches[i - 1] if i > 0 else None
                after_own_value = (
                    prev is not None and prev.kind == "value" and cue_text[prev.end:m.start].strip() == ""
                    and not self._has_cue_before(cue_text[: prev.start])
                )
                grouped = False
                continues_group = (
                    prev is not None and prev.kind in ("dim_noun", "dim_time")
                    and (prev.kind == "dim_time" or str(prev.payload) in dims_cat)
                    and re.fullmatch(r"\s+(and|&)\s+", cue_text[prev.end:m.start]) is not None
                )
                if continues_group:
                    grouped = True
                elif not after_own_value:
                    if self._has_cue_before(cue_text[: m.start]) or FOLLOW_CUE.match(cue_text[m.end:]):
                        grouped = True
                    else:
                        nxt = matches[i + 1] if i + 1 < len(matches) else None
                        between = cue_text[m.end: nxt.start] if nxt else ""
                        if nxt is not None and nxt.kind == "metric" and re.fullmatch(r"\s+by\s+", between):
                            grouped = True
                if grouped and dim not in dims_cat:
                    dims_cat.append(dim)

        # time grain: explicit grains win over generic "trend"
        explicit = [d for d, p in dims_time if p not in GENERIC_TIME_PHRASES]
        time_dims = list(dict.fromkeys(explicit or [d for d, _ in dims_time]))[:1]
        if not time_dims and len(tp.years_mentioned) > 1:
            time_dims = ["year"]
            assumptions.append("Several years mentioned: comparing them year by year.")

        # ranking
        rank = re.search(r"\b(top|bottom|best|worst|highest|lowest|most|least|fewest|largest|biggest|smallest|"
                         r"leading|greatest|maximum|minimum)\b(?:\s+(\d+|" + "|".join(
                             k for k in NUMBER_WORDS if k != "a") + r")\b)?", work)
        explicit_n: int | None = None
        direction = "desc"
        if rank:
            direction = "asc" if rank.group(1) in ASC_WORDS else "desc"
            if rank.group(2):
                g = rank.group(2)
                explicit_n = int(g) if g.isdigit() else NUMBER_WORDS[g]
        is_which = re.search(r"\b(which|what)\b", work) is not None

        # ---------------- clarification: no metric
        if not metrics:
            if (rank or is_which) and (dims_cat or mentioned_dims):
                dim = (dims_cat or mentioned_dims)[0]
                options = self._rank_options(dim, time_phrase, explicit_n or 10)
                return PlannerOutcome(kind="clarify", clarification=Clarification(
                    question=f"How should {DIMENSIONS[dim].synonyms[0]} be ranked? Choose a measure.",
                    options=options))
            leftovers = self._leftovers(work, matches)
            hint = f" I could not map {', '.join(repr(w) for w in leftovers[:3])} to a known metric." if leftovers \
                else ""
            return PlannerOutcome(kind="clarify", clarification=Clarification(
                question="Which measure do you mean?" + hint + " Available metrics: "
                + ", ".join(m.label.lower() for m in METRICS.values()) + ".",
                options=[f"Revenue by month {time_phrase or 'in 2025'}".strip(),
                         f"Top 10 products by revenue {time_phrase}".strip(),
                         f"Conversion rate by traffic source {time_phrase or 'in 2025'}".strip(),
                         f"On-time delivery rate by supplier {time_phrase or 'in 2025'}".strip()]))

        # ---------------- clarification: metrics from several facts
        facts = list(dict.fromkeys(METRICS[m].fact for m in metrics))
        if len(facts) > 1:
            groups = [[m for m in metrics if METRICS[m].fact == f] for f in facts]
            return PlannerOutcome(kind="clarify", clarification=Clarification(
                question="These measures come from different datasets and cannot be combined in one query. "
                         "Which one first?",
                options=[self._canonical(g[0], [d for d in time_dims + dims_cat
                                                if METRICS[g[0]].fact in DIMENSIONS[d].bindings],
                                         time_phrase, []) for g in groups]))
        fact = facts[0]

        # ---------------- filters from values (resolved against the fact)
        filters_by_dim: dict[str, list[str]] = {}
        negated: set[str] = set()
        for vm in value_matches:
            pairs = [p for p in vm.payload if isinstance(p, tuple)]  # type: ignore[attr-defined]
            compatible = [(d, v) for d, v in pairs if fact in DIMENSIONS[d].bindings]
            if not compatible:
                generic = all(d in ("channel", "traffic_source", "device") for d, _ in pairs)
                if generic:
                    assumptions.append(f"Ignored '{vm.phrase}' (not applicable to {metrics[0]}).")
                    continue
                d0 = pairs[0][0]
                ok_dims = [d for d in DIMENSIONS if fact in DIMENSIONS[d].bindings and DIMENSIONS[d].filterable]
                return PlannerOutcome(kind="clarify", clarification=Clarification(
                    question=f"'{vm.phrase}' is a {_DIM_SINGULAR[d0]}, but {METRICS[metrics[0]].label} cannot be "
                             f"filtered by {_DIM_SINGULAR[d0]}. It can be broken down by: "
                             + ", ".join(_DIM_SINGULAR[d] for d in ok_dims) + ".",
                    options=[self._canonical(metrics[0], [d], time_phrase, []) for d in ok_dims[:4]]))
            d, v = compatible[0]
            filters_by_dim.setdefault(d, [])
            if v not in filters_by_dim[d]:
                filters_by_dim[d].append(v)
            if re.search(r"\b(excluding|except|not|other than|without|besides)\s+(the\s+)?$", work[: vm.start]):
                negated.add(d)
        filters: list[Filter] = []
        for d, vals in filters_by_dim.items():
            if len(vals) == 1:
                filters.append(Filter(field=d, kind="dimension", op="neq" if d in negated else "eq", value=vals[0]))
            elif d in negated:
                for v in vals:
                    filters.append(Filter(field=d, kind="dimension", op="neq", value=v))
            else:
                filters.append(Filter(field=d, kind="dimension", op="in", value=vals))

        # a grouping dimension that is also filtered to a single value adds nothing
        dims_cat = [d for d in dims_cat if not any(f.field == d and f.op == "eq" for f in filters)]

        # ---------------- clarification: incompatible grouping dimension
        bad = [d for d in time_dims + dims_cat if fact not in DIMENSIONS[d].bindings]
        if bad:
            ok_dims = [d for d in DIMENSIONS if fact in DIMENSIONS[d].bindings and not DIMENSIONS[d].is_time]
            return PlannerOutcome(kind="clarify", clarification=Clarification(
                question=f"{METRICS[metrics[0]].label} cannot be broken down by {_DIM_SINGULAR[bad[0]]}. "
                         "Available breakdowns: month, quarter, year, "
                         + ", ".join(_DIM_SINGULAR[d] for d in ok_dims) + ".",
                options=[self._canonical(metrics[0], [d], time_phrase, filters) for d in ok_dims[:4]]))

        dims = time_dims + dims_cat
        if len(dims) > 2:
            assumptions.append(f"Only two breakdowns are supported; ignored {', '.join(dims[2:])}.")
            dims = dims[:2]

        # A bare total without a period ("What were sales?") defaults to ALL available data; the
        # assumption is stated in the answer (see "assumptions" below) instead of asking the user.

        # ---------------- threshold filters (HAVING)
        thr = re.search(r"\b(over|above|more than|greater than|exceeding|at least|under|below|less than|"
                        r"fewer than|at most)\s+\$?(\d[\d,]*(?:\.\d+)?)\s*(k|m|%|percent)?(?![\w])", work)
        if thr:
            op = {"over": "gt", "above": "gt", "more than": "gt", "greater than": "gt", "exceeding": "gt",
                  "at least": "gte", "under": "lt", "below": "lt", "less than": "lt", "fewer than": "lt",
                  "at most": "lte"}[thr.group(1)]
            val = float(thr.group(2).replace(",", ""))
            suffix = thr.group(3)
            if suffix == "k":
                val *= 1000
            elif suffix == "m":
                val *= 1_000_000
            target = metrics[0]
            if METRICS[target].fmt == "percent" and (suffix in ("%", "percent") or val > 1):
                val /= 100
            filters.append(Filter(field=target, kind="metric", op=op, value=val))

        # ---------------- ordering + limit
        order_by: list[OrderBy] = []
        limit = self.max_rows
        primary = metrics[0]
        if rank and (dims_cat or not time_dims):
            d = direction
            if primary in LOWER_IS_BETTER:
                if re.search(r"\b(best|fastest|shortest)\b", work):
                    d = "asc"
                elif re.search(r"\b(worst|slowest|longest)\b", work):
                    d = "desc"
            order_by = [OrderBy(field=primary, direction=d)]
            if explicit_n:
                limit = explicit_n
            elif not is_which and dims_cat:
                noun_plural = any(m.kind == "dim_noun" and m.payload == dims_cat[0] and m.phrase.endswith("s")
                                  for m in matches)
                limit = 10 if noun_plural else 1
                assumptions.append(f"Showing the top {limit}.")
        elif time_dims:
            order_by = [OrderBy(field=time_dims[0], direction="asc")]
        elif dims:
            order_by = [OrderBy(field=primary, direction="desc")]
        if not dims:
            limit = 1

        # ---------------- assumptions
        if fact == "sales":
            assumptions.append("Cancelled orders are excluded from sales metrics.")
        if tp.time_range is None:
            assumptions.append(f"No period given: using all available data ({DATA_START} to {DATA_END}).")
        elif not re.search(r"20\d\d", time_phrase):
            assumptions.append(f"Relative dates are anchored to {self.as_of.isoformat()} (end of data).")

        plan = QueryPlan(metrics=metrics, dimensions=dims, filters=filters, time_range=tp.time_range,
                         order_by=order_by, limit=min(limit, self.max_rows), assumptions=assumptions)
        issues = check_plan(plan)
        if issues:
            return PlannerOutcome(kind="clarify", clarification=Clarification(
                question="I could not build a valid query: " + "; ".join(issues),
                options=[self._canonical(primary, [], time_phrase or "in 2025", [])]))
        return PlannerOutcome(kind="plan", plan=plan)

    def _rank_options(self, dim: str, time_phrase: str, n: int) -> list[str]:
        d = DIMENSIONS[dim]
        chosen: list[str] = []
        facts_seen: set[str] = set()
        for m in _RANK_CANDIDATES:  # first one metric per fact, then fill
            f = METRICS[m].fact
            if f in d.bindings and f not in facts_seen:
                chosen.append(m)
                facts_seen.add(f)
        for m in _RANK_CANDIDATES:
            if METRICS[m].fact in d.bindings and m not in chosen:
                chosen.append(m)
        out = []
        for m in chosen[:3]:
            q = f"Top {n} {d.synonyms[0]} by {METRICS[m].synonyms[0]}"
            if time_phrase:
                q += f" {time_phrase}"
            out.append(q)
        return out

    @staticmethod
    def _leftovers(work: str, matches: list[_Match]) -> list[str]:
        blanked = _blank(work, [(m.start, m.end) for m in matches])
        words = re.findall(r"[a-z][a-z\-]+", blanked)
        return [w for w in words if w not in STOPWORDS and len(w) > 2]
