"""Extract plain text from every raw syllabus in the manifest.

Usage:
    python src/extract.py            # only docs without text yet
    python src/extract.py --force    # re-extract everything

Writes data/text/<doc_id>.txt and data/extraction_log.csv (chars extracted,
method used, and a flag for likely-scanned PDFs that need OCR).
"""
import argparse
import csv
import re
from pathlib import Path

from ingest import MANIFEST, RAW, ROOT, load_manifest

TEXT = ROOT / "data" / "text"
LOG = ROOT / "data" / "extraction_log.csv"
MIN_CHARS_PER_PAGE = 100  # below this a PDF is probably scanned images


def from_pdf(path: Path) -> tuple[str, str]:
    import pymupdf as fitz
    doc = fitz.open(path)
    pages = [page.get_text("text") for page in doc]
    text = "\n\n".join(pages)
    if len(text.strip()) < MIN_CHARS_PER_PAGE * max(len(pages), 1):
        ocr = try_ocr(doc)
        if ocr:
            return ocr, "pdf_ocr"
        return text, "pdf_needs_ocr"
    return text, "pdf"


def try_ocr(doc) -> str | None:
    """OCR via PyMuPDF + Tesseract, if Tesseract is installed."""
    try:
        parts = []
        for page in doc:
            tp = page.get_textpage_ocr(full=True)
            parts.append(page.get_text("text", textpage=tp))
        return "\n\n".join(parts)
    except Exception:
        return None


def from_html(path: Path) -> tuple[str, str]:
    html = path.read_text(encoding="utf-8", errors="ignore")
    try:
        import trafilatura
        text = trafilatura.extract(html, include_tables=True, include_formatting=True,
                                   favor_recall=True)
        if text and len(text) > 200:
            return text, "html_trafilatura"
    except Exception:
        pass
    # Fallback: keep headings as markdown so segment.py can find sections.
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    for level in range(1, 5):
        for h in soup.find_all(f"h{level}"):
            h.replace_with(f"\n{'#' * level} {h.get_text(strip=True)}\n")
    return soup.get_text("\n"), "html_bs4"


def from_docx(path: Path) -> tuple[str, str]:
    import docx
    d = docx.Document(path)
    lines = []
    for para in d.paragraphs:
        style = (para.style.name or "").lower()
        if style.startswith("heading") and para.text.strip():
            level = "".join(ch for ch in style if ch.isdigit()) or "2"
            lines.append(f"{'#' * int(level)} {para.text.strip()}")
        else:
            lines.append(para.text)
    for table in d.tables:
        for row in table.rows:
            lines.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(lines), "docx"


def clean(text: str) -> str:
    text = text.replace(" ", " ").replace("­", "")
    text = re.sub(r"-\n(?=[a-z])", "", text)        # re-join hyphenated words
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


HANDLERS = {".pdf": from_pdf, ".html": from_html, ".htm": from_html,
            ".docx": from_docx}


def extract_one(row: dict) -> tuple[str, str]:
    path = RAW / f"{row['doc_id']}{row['ext']}"
    handler = HANDLERS.get(row["ext"])
    if handler is None:  # .txt / .md
        return path.read_text(encoding="utf-8", errors="ignore"), "plain"
    return handler(path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true")
    a = p.parse_args()
    if not MANIFEST.exists():
        raise SystemExit("No manifest yet. Run src/ingest.py first.")
    TEXT.mkdir(parents=True, exist_ok=True)
    log = []
    for row in load_manifest():
        out = TEXT / f"{row['doc_id']}.txt"
        if out.exists() and not a.force:
            continue
        try:
            text, method = extract_one(row)
            text = clean(text)
            out.write_text(text, encoding="utf-8")
            status = "needs_ocr" if method == "pdf_needs_ocr" else "ok"
        except Exception as e:  # keep going; the log shows what failed
            text, method, status = "", "error", f"error: {e}"
        log.append({"doc_id": row["doc_id"], "course": row["course"],
                    "term": row["term"], "method": method,
                    "chars": len(text), "status": status})
        print(f"{row['doc_id']} {row['course']} {row['term']}: {status} ({len(text)} chars)")
    if log:
        exists = LOG.exists()
        with open(LOG, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(log[0]))
            if not exists:
                w.writeheader()
            w.writerows(log)


if __name__ == "__main__":
    main()
