"""Compare extracted values with the hand-checked ground truth.

This links back to classical ML evaluation: the service is a model, the
ground truth is a labelled test set, and confidence should be checked against
how often the values are actually right.
"""
from __future__ import annotations

import pandas as pd

FIELDS = ["merchant", "transaction_date", "subtotal", "tax", "tip", "total"]


def _same(field, extracted, truth) -> bool | None:
    if pd.isna(truth) or truth == "":
        return None  # no reference value for this field
    if extracted is None or (isinstance(extracted, float) and pd.isna(extracted)):
        return False
    if field in ("subtotal", "tax", "tip", "total"):
        return abs(float(extracted) - float(truth)) <= 0.01
    if field == "transaction_date":
        return str(extracted)[:10] == str(truth)[:10]
    a, b = str(extracted).lower(), str(truth).lower()
    return a in b or b in a


def compare(records: list[dict], truth_csv: str) -> pd.DataFrame:
    truth = pd.read_csv(truth_csv).set_index("file")
    rows = []
    for rec in records:
        f = rec["source_file"]
        if f not in truth.index:
            continue
        for field in FIELDS:
            ok = _same(field, rec.get(field), truth.loc[f, field])
            if ok is None:
                continue
            rows.append({"file": f, "field": field, "extracted": rec.get(field),
                         "expected": truth.loc[f, field],
                         "confidence": (rec.get("confidence") or {}).get(field),
                         "correct": ok})
    return pd.DataFrame(rows)


def confidence_table(results: pd.DataFrame, bins=(0, 0.5, 0.8, 0.9, 0.95, 1.0001)) -> pd.DataFrame:
    """Accuracy per confidence band: is a 0.9 really right about 90% of the time?"""
    df = results.dropna(subset=["confidence"]).copy()
    df["band"] = pd.cut(df["confidence"], bins=list(bins), right=False)
    return (df.groupby("band", observed=True)["correct"]
              .agg(values="count", accuracy="mean").reset_index())
