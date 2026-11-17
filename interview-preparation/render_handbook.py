"""Validate an interview handbook JSON and render it to Markdown.

Usage:
  python interview-preparation/render_handbook.py nexus-ai        # validates + writes nexus-ai/interview-preparation/HANDBOOK.md
  python interview-preparation/render_handbook.py cross-project   # interview-preparation/cross-project.json -> CROSS_PROJECT.md

Validation (any failure exits 1):
  - required fields, unique ids, known topic ids, difficulty in {beginner,intermediate,advanced,senior}
  - kind in {implemented, proposed_extension}
  - every code_ref "path[:symbol]" points to an EXISTING file/dir (relative to the project dir,
    or to the workspace root for cross-project) -- invented references fail the build
  - mock interview question ids exist
  - ASCII only
  - minimum question count (100 per project, 30 for cross-project)
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIFFS = ("beginner", "intermediate", "advanced", "senior")
KINDS = ("implemented", "proposed_extension")


def fail(errors: list[str]) -> None:
    for e in errors[:50]:
        print(f"ERROR: {e}")
    print(f"{len(errors)} error(s)")
    sys.exit(1)


def validate(hb: dict, base: Path, minimum: int) -> list[str]:
    errs: list[str] = []
    for key in ("project", "title", "generated_from", "topics", "questions", "exercises", "walkthroughs", "mock_interviews"):
        if key not in hb:
            errs.append(f"missing top-level key {key}")
    if errs:
        return errs
    topic_ids = {t["id"] for t in hb["topics"]}
    ids = Counter(q.get("id") for q in hb["questions"])
    errs += [f"duplicate question id {i}" for i, n in ids.items() if n > 1]
    for q in hb["questions"]:
        qid = q.get("id", "?")
        for f in ("id", "topic", "difficulty", "question", "answer", "code_refs", "follow_ups", "kind"):
            if f not in q:
                errs.append(f"{qid}: missing {f}")
        if q.get("topic") not in topic_ids:
            errs.append(f"{qid}: unknown topic {q.get('topic')}")
        if q.get("difficulty") not in DIFFS:
            errs.append(f"{qid}: bad difficulty {q.get('difficulty')}")
        if q.get("kind") not in KINDS:
            errs.append(f"{qid}: bad kind {q.get('kind')}")
        if len(q.get("answer", "")) < 80:
            errs.append(f"{qid}: answer too short")
        for ref in q.get("code_refs", []):
            path = ref.split(":", 1)[0].strip()
            if not (base / path).exists():
                errs.append(f"{qid}: code_ref does not exist: {ref}")
    if len(hb["questions"]) < minimum:
        errs.append(f"only {len(hb['questions'])} questions (< {minimum})")
    for m in hb["mock_interviews"]:
        for qid in m.get("question_ids", []):
            if qid not in ids:
                errs.append(f"mock '{m.get('title')}' references unknown question {qid}")
    for ex in hb["exercises"]:
        for f in ("id", "title", "difficulty", "prompt", "solution_outline", "evaluation_criteria"):
            if f not in ex:
                errs.append(f"exercise {ex.get('id')}: missing {f}")
    raw = json.dumps(hb, ensure_ascii=False)
    bad = sorted({c for c in raw if ord(c) > 127})
    if bad:
        errs.append(f"non-ASCII characters present: {bad[:10]}")
    return errs


def render(hb: dict) -> str:
    out = [f"# {hb['title']}", "", f"_Source: {hb['generated_from']}_", ""]
    counts = Counter(q["topic"] for q in hb["questions"])
    dcounts = Counter(q["difficulty"] for q in hb["questions"])
    out += ["## Contents", "", "| Topic | Questions |", "|---|---|"]
    out += [f"| [{t['title']}](#{t['id']}) | {counts.get(t['id'], 0)} |" for t in hb["topics"]]
    out += ["", "Difficulty mix: " + ", ".join(f"{d} {dcounts.get(d, 0)}" for d in DIFFS), "",
            "Labels: `[impl]` = implemented in this repo, `[ext]` = proposed extension (not implemented).", ""]
    for t in hb["topics"]:
        out += [f'<a id="{t["id"]}"></a>', f"## {t['title']}", ""]
        for q in [q for q in hb["questions"] if q["topic"] == t["id"]]:
            tag = "impl" if q["kind"] == "implemented" else "ext"
            out += [f"### {q['id']}. {q['question']}", "", f"`{q['difficulty']}` `[{tag}]`", "", "**Answer.** " + q["answer"], ""]
            if q.get("reasoning"):
                out += ["**Why it matters.** " + q["reasoning"], ""]
            if q["code_refs"]:
                out += ["**Code:** " + ", ".join(f"`{r}`" for r in q["code_refs"]), ""]
            if q["follow_ups"]:
                out += ["**Follow-ups:**"] + [f"- {f}" for f in q["follow_ups"]] + [""]
    out += ["## Coding exercises", ""]
    for ex in hb["exercises"]:
        out += [f"### {ex['title']} (`{ex['difficulty']}`)", "", ex["prompt"], "", "**Solution outline.** " + ex["solution_outline"], "",
                "**Evaluation criteria:**"] + [f"- {c}" for c in ex["evaluation_criteria"]] + [""]
    out += ["## Architecture walkthroughs", ""]
    for w in hb["walkthroughs"]:
        out += [f"### {w['title']}", ""] + [f"{i}. {s}" for i, s in enumerate(w["steps"], 1)] + [""]
    byid = {q["id"]: q for q in hb["questions"]}
    out += ["## Mock interview sequences", ""]
    for m in hb["mock_interviews"]:
        out += [f"### {m['title']} (`{m['level']}`)", ""] + [f"{i}. {byid[q]['question']} ({q})" for i, q in enumerate(m["question_ids"], 1)] + [""]
    return "\n".join(out)


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    if target == "cross-project":
        src, base, dest, minimum = ROOT / "interview-preparation" / "cross-project.json", ROOT, ROOT / "interview-preparation" / "CROSS_PROJECT.md", 30
    elif target in ("nexus-ai", "datawise-ai", "evalops-ai"):
        base = ROOT / target
        src, dest, minimum = base / "interview-preparation" / "questions.json", base / "interview-preparation" / "HANDBOOK.md", 100
    else:
        sys.exit("usage: render_handbook.py <nexus-ai|datawise-ai|evalops-ai|cross-project>")
    hb = json.loads(src.read_text(encoding="utf-8"))
    errs = validate(hb, base, minimum)
    if errs:
        fail(errs)
    dest.write_text(render(hb), encoding="utf-8")
    print(f"OK: {len(hb['questions'])} questions, {len(hb['exercises'])} exercises -> {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
