# DATAWISE AI -- Interview preparation

Interview handbook for DATAWISE AI, written from the source code, tests, docs and evaluation results
as they were on 2026-11-16.

- [HANDBOOK.md](HANDBOOK.md) -- the rendered handbook: 119 questions in 15 topics, 9 coding exercises,
  5 architecture walkthroughs and 5 mock interview sequences (beginner to senior).
- [questions.json](questions.json) -- the source data. Edit this file, then re-render.

Each question is labeled `[impl]` (describes code in this repo) or `[ext]` (a proposed extension that is
NOT implemented). Every code reference points to a file that exists in `datawise-ai/`.

Re-render and validate (from the workspace root):

```bash
python interview-preparation/render_handbook.py datawise-ai
```

The validator checks unique ids, known topics, difficulty and kind values, minimum answer length,
that every code reference exists, and ASCII-only content.
