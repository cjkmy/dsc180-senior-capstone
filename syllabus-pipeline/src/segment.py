"""Split extracted text into sections and flag the ones relevant to coding.

Usage:
    python src/segment.py

Writes data/sections.jsonl, one line per section:
    {doc_id, section_idx, heading, text, ai_hits, grading_hit, integrity_hit}

Every document gets a row in data/doc_flags.csv, including documents with
NO AI mention. Those are not missing data: before late 2022 "no policy" is
the normal state and serves as the comparison group.
"""
import csv
import json
import re

from extract import TEXT
from ingest import ROOT, load_manifest

SECTIONS = ROOT / "data" / "sections.jsonl"
FLAGS = ROOT / "data" / "doc_flags.csv"

# Keyword list adapted from Persaud (2024) and the tools Ali et al. (2025)
# found in syllabi; extended with later tools. Word boundaries avoid
# matching "ai" inside "maintain", "gpt" inside URLs, etc.
AI_TERMS = [
    r"\bA\.?I\.?\b", r"artificial intelligence", r"generative", r"\bgen ?ai\b",
    r"chat ?gpt", r"\bGPT-?\d?\b", r"\bLLMs?\b", r"large language model",
    r"language model", r"co-?pilot", r"\bclaude\b", r"\bgemini\b", r"\bbard\b",
    r"bing (ai|chat)", r"\bcursor\b", r"grammarly", r"perplexity",
    r"chatbots?", r"\bAI[- ]generated\b", r"\bAI tools?\b", r"midjourney",
]
AI_RE = re.compile("|".join(AI_TERMS), re.IGNORECASE)
# Courses ABOUT AI mention it constantly; we still flag them so a human can
# separate "policy on AI use" from "AI as course content".
GRADING_RE = re.compile(r"\b(grading|grade breakdown|assessment|evaluation|weights?)\b|\d{1,3}\s?%",
                        re.IGNORECASE)
INTEGRITY_RE = re.compile(r"academic (integrity|honesty|misconduct)|collaboration policy|"
                          r"cheating|plagiari", re.IGNORECASE)

# A line is treated as a heading if it is markdown-style, or short,
# not ending in sentence punctuation, and mostly Title/UPPER case.
MD_HEAD = re.compile(r"^#{1,6}\s+(.+)$")
NUMBERED_HEAD = re.compile(r"^(\d+(\.\d+)*|[IVX]+)[.)]?\s+[A-Z][^.!?]{2,60}$")


def is_heading(line: str) -> str | None:
    s = line.strip()
    if not s or len(s) > 80:
        return None
    m = MD_HEAD.match(s)
    if m:
        return m.group(1).strip()
    # Bullets, percentages, and "Label: value" lines are list items, not headings.
    if s[0] in "-*•–·" or "%" in s or ":" in s[:-1]:
        return None
    if NUMBERED_HEAD.match(s):
        return s
    if s[-1] in ".,;!?" or len(s.split()) > 8:
        return None
    words = [w for w in re.findall(r"[A-Za-z]+", s) if len(w) > 3]
    if words and (s.isupper() or sum(w[0].isupper() for w in words) / len(words) >= 0.8):
        return s.rstrip(":")
    return None


def split_sections(text: str) -> list[dict]:
    sections, heading, buf = [], "(preamble)", []
    for line in text.splitlines():
        h = is_heading(line)
        if h:
            if "".join(buf).strip():
                sections.append({"heading": heading, "text": "\n".join(buf).strip()})
            heading, buf = h, []
        else:
            buf.append(line)
    if "".join(buf).strip():
        sections.append({"heading": heading, "text": "\n".join(buf).strip()})
    return sections


def main():
    rows = load_manifest()
    flags = []
    with open(SECTIONS, "w", encoding="utf-8") as out:
        for row in rows:
            path = TEXT / f"{row['doc_id']}.txt"
            if not path.exists():
                continue
            secs = split_sections(path.read_text(encoding="utf-8"))
            n_ai = 0
            for i, s in enumerate(secs):
                blob = s["heading"] + "\n" + s["text"]
                hits = sorted({m.group(0).lower() for m in AI_RE.finditer(blob)})
                n_ai += bool(hits)
                out.write(json.dumps({
                    "doc_id": row["doc_id"], "section_idx": i,
                    "heading": s["heading"], "text": s["text"],
                    "ai_hits": hits,
                    "grading_hit": bool(GRADING_RE.search(blob)),
                    "integrity_hit": bool(INTEGRITY_RE.search(blob)),
                }) + "\n")
            flags.append({"doc_id": row["doc_id"], "course": row["course"],
                          "term": row["term"], "n_sections": len(secs),
                          "n_ai_sections": n_ai, "mentions_ai": n_ai > 0})
            print(f"{row['doc_id']} {row['course']} {row['term']}: "
                  f"{len(secs)} sections, {n_ai} mention AI")
    with open(FLAGS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["doc_id", "course", "term", "n_sections",
                                          "n_ai_sections", "mentions_ai"])
        w.writeheader()
        w.writerows(flags)


if __name__ == "__main__":
    main()
