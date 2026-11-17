# NEXUS AI -- Interview preparation

Interview handbook generated from the NEXUS AI source code (inspected 2026-11-16). Every question
points to real files and symbols in this repository; the renderer fails the build if a reference
does not exist.

- [HANDBOOK.md](HANDBOOK.md) -- rendered handbook: 121 questions across 15 topics, coding
  exercises, architecture walkthroughs and mock interview sequences.
- [questions.json](questions.json) -- source data (edit this, not the Markdown).

Labels: `[impl]` = describes implemented code; `[ext]` = proposed extension that is NOT
implemented (S3 storage, OTel export, Redis rate limiting, cross-encoder reranker, RLS, etc.).

Regenerate and validate:

```
cd h:/ai-engineer-portfolio
python interview-preparation/render_handbook.py nexus-ai
```
