"""Classify each syllabus into the fixed coding schema with an LLM.

Usage:
    export ANTHROPIC_API_KEY=...
    python src/classify.py                 # all docs not yet classified
    python src/classify.py --limit 20      # try a few first
    python src/classify.py --dry-run       # write prompts only, no API calls

Writes data/llm_labels.jsonl (one JSON object per doc, plus model + prompt
version so results stay reproducible) and data/llm_labels.csv (flat view).

The model only sees the sections segment.py flagged (AI mentions, academic
integrity, grading), not the whole syllabus. That keeps cost down and makes
errors easy to audit: every label comes with an evidence quote.
"""
import argparse
import csv
import json
import os
import time
from collections import defaultdict

from ingest import ROOT, load_manifest
from segment import SECTIONS

OUT_JSONL = ROOT / "data" / "llm_labels.jsonl"
OUT_CSV = ROOT / "data" / "llm_labels.csv"
DRY_DIR = ROOT / "data" / "prompts"
PROMPT_VERSION = "v1"
MODEL = os.environ.get("CLASSIFY_MODEL", "claude-sonnet-5-5")
MAX_INPUT_CHARS = 24_000

SCOPE_VALUES = ["allowed", "prohibited", "conditional", "not_specified"]
SCHEMA = {
    "type": "object",
    "properties": {
        "ai_policy": {
            "type": "string",
            "enum": ["none", "prohibited", "permission_required", "partial", "permitted"],
            "description": (
                "Overall GenAI-use policy. none = syllabus says nothing about students "
                "using AI tools. prohibited = no use for graded work. permission_required "
                "= only with explicit instructor permission. partial = allowed for some "
                "activities, banned for others. permitted = allowed for most/all work "
                "(possibly with citation)."),
        },
        "scope": {
            "type": "object",
            "description": "Policy for each kind of assessment the syllabus addresses.",
            "properties": {k: {"type": "string", "enum": SCOPE_VALUES} for k in
                           ["homework", "projects", "take_home_exams",
                            "proctored_exams", "writing", "studying_learning"]},
            "required": ["homework", "projects", "take_home_exams",
                         "proctored_exams", "writing", "studying_learning"],
            "additionalProperties": False,
        },
        "citation_required": {"type": "boolean",
                              "description": "Students must cite or disclose AI use."},
        "detection_mentioned": {"type": "boolean",
                                "description": "Mentions AI-detection tools or checking."},
        "stance": {"type": "string", "enum": ["encourages", "discourages", "neutral"],
                   "description": "Explicit encouragement/discouragement beyond the rule itself."},
        "implications": {
            "type": "array",
            "items": {"type": "string", "enum": ["veracity", "privacy",
                                                 "hindering_learning", "skill_development"]},
            "description": "Reasons the syllabus gives about AI's effects."},
        "tools_named": {"type": "array", "items": {"type": "string"},
                        "description": "AI tools named, e.g. ChatGPT, Copilot."},
        "ai_is_course_content": {"type": "boolean",
                                 "description": "AI is a subject taught in the course (not just a policy)."},
        "assessment_weights": {
            "type": "array",
            "description": "Grade breakdown as stated. Leave empty if not given.",
            "items": {"type": "object", "properties": {
                "component": {"type": "string"},
                "category": {"type": "string", "enum": [
                    "homework", "project", "lab", "quiz", "proctored_exam",
                    "take_home_exam", "participation", "other"]},
                "percent": {"type": "number"}},
                "required": ["component", "category", "percent"],
                "additionalProperties": False},
        },
        "evidence_quote": {"type": "string",
                           "description": "Shortest verbatim excerpt (<= 60 words) supporting ai_policy; empty if none."},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["ai_policy", "scope", "citation_required", "detection_mentioned",
                 "stance", "implications", "tools_named", "ai_is_course_content",
                 "assessment_weights", "evidence_quote", "confidence"],
    "additionalProperties": False,
}

SYSTEM = """You code university course syllabi for a research study on generative-AI \
policies. Follow the codebook exactly and record only what the text states; never \
infer a policy the syllabus does not state. If AI is mentioned only as course \
content (e.g. a machine learning class) and there is no rule about students using \
AI tools, ai_policy is "none". A general rule like "all submitted work must be your \
own" does NOT count as an AI policy unless AI tools are named or clearly meant. \
For assessment_weights, classify an exam as take_home_exam only if the syllabus \
says it is taken outside class; otherwise proctored_exam. Use "conditional" scope \
when a use is allowed only under conditions (e.g. with citation, for debugging only)."""


def load_sections() -> dict[str, list[dict]]:
    by_doc = defaultdict(list)
    with open(SECTIONS, encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            by_doc[s["doc_id"]].append(s)
    return by_doc


def build_input(secs: list[dict]) -> str:
    keep = [s for s in secs if s["ai_hits"] or s["integrity_hit"] or s["grading_hit"]]
    # AI sections first so they survive truncation.
    keep.sort(key=lambda s: (not s["ai_hits"], s["section_idx"]))
    parts, total = [], 0
    for s in keep:
        chunk = f"## {s['heading']}\n{s['text']}\n"
        if total + len(chunk) > MAX_INPUT_CHARS:
            chunk = chunk[: MAX_INPUT_CHARS - total]
        parts.append((s["section_idx"], chunk))
        total += len(chunk)
        if total >= MAX_INPUT_CHARS:
            break
    if not parts:
        return "(No sections about AI, academic integrity, or grading were found.)"
    # Put the kept sections back in document order so the model reads them naturally.
    return "\n".join(chunk for _, chunk in sorted(parts))


def classify(client, row: dict, text: str) -> dict:
    import anthropic
    user = (f"Course: {row['course']}  Term: {row['term']}\n\n"
            f"Relevant syllabus sections:\n<syllabus>\n{text}\n</syllabus>\n\n"
            "Return the coding as JSON.")
    for attempt in range(4):
        try:
            resp = client.messages.create(
                model=MODEL, max_tokens=4000, system=SYSTEM,
                output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
                messages=[{"role": "user", "content": user}],
            )
            if resp.stop_reason == "max_tokens":
                raise RuntimeError("output cut off at max_tokens; raise max_tokens")
            text = next(b.text for b in resp.content if b.type == "text")
            return normalize(json.loads(text))
        except (anthropic.RateLimitError, anthropic.APIConnectionError,
                anthropic.InternalServerError) as e:  # only retry transient errors
            if attempt == 3:
                raise
            wait = 2 ** attempt * 5
            print(f"  retry in {wait}s ({e})")
            time.sleep(wait)


def normalize(lab: dict) -> dict:
    for k in ["ai_policy", "stance", "confidence"]:
        lab[k] = str(lab[k]).strip().lower()
    lab["scope"] = {k: str(v).strip().lower() for k, v in lab["scope"].items()}
    lab["implications"] = [str(v).strip().lower() for v in lab["implications"]]
    for w in lab["assessment_weights"]:
        w["category"] = str(w["category"]).strip().lower()
    return lab


def flatten(rec: dict) -> dict:
    lab = rec["labels"]
    flat = {"doc_id": rec["doc_id"], "course": rec["course"], "term": rec["term"],
            "model": rec["model"], "prompt_version": rec["prompt_version"]}
    for k in ["ai_policy", "citation_required", "detection_mentioned", "stance",
              "ai_is_course_content", "confidence", "evidence_quote"]:
        flat[k] = lab.get(k)
    for k, v in lab.get("scope", {}).items():
        flat[f"scope_{k}"] = v
    flat["implications"] = ";".join(lab.get("implications", []))
    flat["tools_named"] = ";".join(lab.get("tools_named", []))
    weights = defaultdict(float)
    for w in lab.get("assessment_weights", []):
        weights[w["category"]] += float(w["percent"])
    for cat in ["homework", "project", "lab", "quiz", "proctored_exam",
                "take_home_exam", "participation", "other"]:
        flat[f"pct_{cat}"] = weights.get(cat, 0.0)
    flat["pct_total"] = sum(weights.values())  # should be ~100; flag if not
    return flat


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    done = set()
    if OUT_JSONL.exists():
        done = {json.loads(l)["doc_id"] for l in open(OUT_JSONL, encoding="utf-8")}
    sections = load_sections()
    todo = [r for r in load_manifest() if r["doc_id"] in sections and r["doc_id"] not in done]
    if a.limit:
        todo = todo[: a.limit]

    if a.dry_run:
        DRY_DIR.mkdir(parents=True, exist_ok=True)
        for r in todo:
            (DRY_DIR / f"{r['doc_id']}.txt").write_text(build_input(sections[r["doc_id"]]),
                                                       encoding="utf-8")
        print(f"wrote {len(todo)} prompt inputs to {DRY_DIR}")
        return

    import anthropic
    client = anthropic.Anthropic()
    with open(OUT_JSONL, "a", encoding="utf-8") as out:
        for r in todo:
            labels = classify(client, r, build_input(sections[r["doc_id"]]))
            rec = {"doc_id": r["doc_id"], "course": r["course"], "term": r["term"],
                   "model": MODEL, "prompt_version": PROMPT_VERSION, "labels": labels}
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(f"{r['doc_id']} {r['course']} {r['term']}: {labels['ai_policy']}")

    recs = [json.loads(l) for l in open(OUT_JSONL, encoding="utf-8")]
    if recs:
        flat = [flatten(r) for r in recs]
        with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(flat[0]))
            w.writeheader()
            w.writerows(flat)


if __name__ == "__main__":
    main()
