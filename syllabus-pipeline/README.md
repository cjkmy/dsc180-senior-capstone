# Syllabus GenAI-policy pipeline

Turns a pile of syllabi (PDF, HTML, DOCX) into one coded row per course
offering: AI policy, per-assessment scope, citation/detection rules, and the
grade breakdown. Built for a panel design (same courses across terms, before
and after Nov 2022), so syllabi with no AI policy are kept as the comparison group.

Method builds on:
- Ali et al. (SIGCSE 2025): codebook and public-source collection rules (`labels/codebook.md`)
- Woodbridge et al. (2025): LLM classification into a fixed schema
- U. Michigan UROP syllabus project: two-coder consensus labels, then LLM scored with P/R/F1
- Persaud (2024): keyword filter for AI mentions

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # only needed for classify.py
```

Optional: install Tesseract if you have scanned PDFs (`extract.py` flags them as `needs_ocr`).

## Steps (run from `src/`)

| Step | Command | Output |
|---|---|---|
| 1. Register files | `python ingest.py FILES --course "DSC 10" --term FA22 --source course_site --url URL` | `data/raw/`, `data/manifest.csv` |
| 2. Extract text | `python extract.py` | `data/text/*.txt`, `data/extraction_log.csv` |
| 3. Split + flag sections | `python segment.py` | `data/sections.jsonl`, `data/doc_flags.csv` |
| 4. Check inputs (free) | `python classify.py --dry-run` | `data/prompts/*.txt` |
| 5. Classify | `python classify.py --limit 20` | `data/llm_labels.jsonl`, `data/llm_labels.csv` |
| 6. Human agreement | `python validate.py agreement` | kappa per field, `labels/disagreements.csv` |
| 7. LLM vs gold | `python validate.py llm` | P/R/F1, confusion matrix, `labels/llm_errors.csv` |

`--source` must be one of: `course_site`, `wayback`, `department`, `instructor`, `canvas`.
Track it so you can test later whether the source biases results.
Terms are normalized automatically ("Fall 2022", "fa22", "FA2022" → `FA22`).
Exact duplicate files are skipped by content hash.

## Notes

- `ingest.py` copies files; originals are never modified.
- `classify.py` sends only the AI, academic-integrity, and grading sections to
  the model, and every label carries an evidence quote for auditing.
- Re-running steps 2–5 only processes new documents (use `extract.py --force` to redo).
- When you change the prompt or codebook, bump `PROMPT_VERSION` in
  `classify.py` and the version at the top of the codebook.
- `pct_total` in `llm_labels.csv` should be about 100; anything else means the
  grade breakdown was missed or misread.
- `tests/fixtures/` has three sample syllabi (HTML, PDF, DOCX) for trying the pipeline end to end.
- Model defaults to `claude-sonnet-5-5`; override with `CLASSIFY_MODEL`.

## Next to build

- `scrape_wayback.py`: list archived versions of course URLs via the Wayback CDX API.
- Grade-distribution ingest and the course × term panel join.
