"""Register syllabus files in the manifest.

Usage:
    python src/ingest.py PATH [PATH ...] --course "DSC 10" --term FA22 \
        --instructor "Last, First" --source course_site --url https://...

Copies each file into data/raw/ under a content-hash name (never edits the
original), records metadata in data/manifest.csv, and skips exact duplicates.
"""
import argparse
import csv
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "manifest.csv"

FIELDS = ["doc_id", "course", "term", "instructor", "source", "url",
          "orig_filename", "ext", "sha256", "retrieved_at"]
# source should be one of: course_site, wayback, department, instructor, canvas
VALID_SOURCES = {"course_site", "wayback", "department", "instructor", "canvas"}
SUPPORTED = {".pdf", ".html", ".htm", ".docx", ".txt", ".md"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> list[dict]:
    if not MANIFEST.exists():
        return []
    with open(MANIFEST, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_manifest(rows: list[dict]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def normalize_term(term: str) -> str:
    """'Fall 2022' / 'fa22' / 'FA2022' -> 'FA22'."""
    t = term.strip().upper().replace(" ", "")
    for long, short in [("FALL", "FA"), ("WINTER", "WI"), ("SPRING", "SP"),
                        ("SUMMER1", "S1"), ("SUMMER2", "S2"), ("SUMMER", "SU")]:
        t = t.replace(long, short)
    if len(t) == 6 and t[2:].isdigit():  # FA2022
        t = t[:2] + t[-2:]
    return t


def ingest(path: Path, meta: dict, rows: list[dict]) -> str:
    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        return f"skip (unsupported type {ext}): {path}"
    digest = sha256(path)
    if any(r["sha256"] == digest for r in rows):
        return f"skip (duplicate): {path}"
    doc_id = digest[:12]
    RAW.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, RAW / f"{doc_id}{ext}")
    rows.append({
        "doc_id": doc_id,
        "course": meta["course"].upper().strip(),
        "term": normalize_term(meta["term"]),
        "instructor": meta.get("instructor", ""),
        "source": meta["source"],
        "url": meta.get("url", ""),
        "orig_filename": path.name,
        "ext": ext,
        "sha256": digest,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    return f"added {doc_id}: {path.name}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("--course", required=True)
    p.add_argument("--term", required=True)
    p.add_argument("--instructor", default="")
    p.add_argument("--source", required=True, choices=sorted(VALID_SOURCES))
    p.add_argument("--url", default="")
    a = p.parse_args()
    rows = load_manifest()
    meta = vars(a)
    for path in a.paths:
        print(ingest(path, meta, rows))
    write_manifest(rows)


if __name__ == "__main__":
    main()
