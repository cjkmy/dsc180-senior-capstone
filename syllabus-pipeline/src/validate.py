"""Check label quality: human vs human, then LLM vs human gold labels.

Usage:
    python src/validate.py agreement   # two human coders -> Cohen's kappa
    python src/validate.py llm         # LLM vs reconciled gold -> P/R/F1

Inputs:
    labels/human_labels.csv  one row per (doc_id, coder); see labels/README
    labels/gold.csv          reconciled labels after coders discuss disagreements
    data/llm_labels.csv      output of classify.py

Writes labels/disagreements.csv (to discuss) and labels/llm_errors.csv
(to read when deciding how to revise the prompt or codebook).
"""
import sys

import pandas as pd
from sklearn.metrics import (classification_report, cohen_kappa_score,
                             confusion_matrix)

from ingest import ROOT

LABELS = ROOT / "labels"
FIELDS = ["ai_policy", "citation_required", "detection_mentioned", "stance",
          "ai_is_course_content"]


def norm(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().replace({"1": "true", "0": "false",
                                                          "yes": "true", "no": "false"})


def agreement():
    df = pd.read_csv(LABELS / "human_labels.csv")
    coders = sorted(df["coder"].unique())
    if len(coders) != 2:
        raise SystemExit(f"expected exactly 2 coders, found {coders}")
    a = df[df.coder == coders[0]].set_index("doc_id")
    b = df[df.coder == coders[1]].set_index("doc_id")
    both = a.index.intersection(b.index)
    print(f"{len(both)} docs coded by both {coders[0]} and {coders[1]}\n")
    rows = []
    for f in FIELDS:
        x, y = norm(a.loc[both, f]), norm(b.loc[both, f])
        if len(set(x) | set(y)) < 2:
            ktxt = "kappa=n/a (only one label used)"
        else:
            ktxt = f"kappa={cohen_kappa_score(x, y):.2f}"
        print(f"{f:24s} {ktxt}  raw agreement={(x == y).mean():.0%}")
        for d in both[(x != y).values]:
            rows.append({"doc_id": d, "field": f, coders[0]: x[d], coders[1]: y[d]})
    pd.DataFrame(rows).to_csv(LABELS / "disagreements.csv", index=False)
    print(f"\n{len(rows)} disagreements -> labels/disagreements.csv")
    print("Rule of thumb: kappa >= 0.80 strong, 0.60-0.80 acceptable; "
          "below that, tighten the codebook before scaling.")


def llm():
    gold = pd.read_csv(LABELS / "gold.csv").set_index("doc_id")
    pred = pd.read_csv(ROOT / "data" / "llm_labels.csv").set_index("doc_id")
    ids = gold.index.intersection(pred.index)
    print(f"{len(ids)} docs have both gold and LLM labels\n")
    errors = []
    for f in FIELDS:
        y, yhat = norm(gold.loc[ids, f]), norm(pred.loc[ids, f])
        print(f"=== {f} ===")
        print(classification_report(y, yhat, zero_division=0))
        if f == "ai_policy":
            labs = sorted(set(y) | set(yhat))
            cm = pd.DataFrame(confusion_matrix(y, yhat, labels=labs),
                              index=[f"gold:{l}" for l in labs],
                              columns=[f"llm:{l}" for l in labs])
            print(cm, "\n")
        for d in ids[(y != yhat).values]:
            errors.append({"doc_id": d, "field": f, "gold": y[d], "llm": yhat[d],
                           "llm_confidence": pred.loc[d, "confidence"],
                           "evidence_quote": pred.loc[d, "evidence_quote"]})
    pd.DataFrame(errors).to_csv(LABELS / "llm_errors.csv", index=False)
    print(f"{len(errors)} LLM errors -> labels/llm_errors.csv")


if __name__ == "__main__":
    {"agreement": agreement, "llm": llm}.get(
        sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
