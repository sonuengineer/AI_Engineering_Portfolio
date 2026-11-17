# EvalOps AI -- interview preparation

Interview handbook generated from the actual EvalOps AI source code, docs and live benchmark
results (inspected on 2026-11-16).

- [HANDBOOK.md](HANDBOOK.md) -- the rendered handbook: 125 questions across 15 topics, coding
  exercises, architecture walkthroughs and mock interview sequences (beginner -> senior).
- [questions.json](questions.json) -- the source of truth. Edit this file, then re-render.

Every question is labeled `[impl]` (describes code in this repo) or `[ext]` (proposed extension,
not implemented). Every code reference points to a file that exists; the renderer fails the build
otherwise.

Re-render and validate (from the workspace root):

```bash
python interview-preparation/render_handbook.py evalops-ai
```
