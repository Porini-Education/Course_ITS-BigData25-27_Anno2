"""Business rules that decide whether a receipt can be accepted automatically.

Each rule returns zero or more Issue objects. Any issue with severity
"review" routes the document to a person. "info" issues are recorded only.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime

TOLERANCE = 0.02  # currency units


@dataclass
class Issue:
    rule: str
    severity: str  # "review" or "info"
    message: str


def _num(x):
    return None if x is None else float(x)


def check_required(rec: dict) -> list[Issue]:
    issues = []
    for name in ("total", "merchant"):
        if rec.get(name) is None:
            issues.append(Issue(f"missing_{name}", "review", f"{name} is missing"))
    return issues


def check_confidence(rec: dict, threshold: float) -> list[Issue]:
    issues = []
    for name, conf in (rec.get("confidence") or {}).items():
        if conf is not None and conf < threshold:
            issues.append(Issue("low_confidence", "review",
                                f"{name} confidence {conf:.2f} is below {threshold:.2f}"))
    return issues


def check_arithmetic(rec: dict) -> list[Issue]:
    """subtotal + tax + tip should equal total (within a tolerance)."""
    subtotal, tax, tip, total = (_num(rec.get(k)) for k in ("subtotal", "tax", "tip", "total"))
    if total is None or subtotal is None:
        return [Issue("arithmetic_not_checked", "info",
                      "subtotal or total missing, totals not reconciled")]
    expected = subtotal + (tax or 0) + (tip or 0)
    diff = round(total - expected, 2)
    if abs(diff) <= TOLERANCE:
        return []
    return [Issue("totals_do_not_reconcile", "review",
                  f"subtotal {subtotal:.2f} + tax {tax or 0:.2f} + tip {tip or 0:.2f} "
                  f"= {expected:.2f}, but total is {total:.2f} (difference {diff:+.2f}: "
                  f"fees, discount or a misread value?)")]


def check_date(rec: dict, today: date | None = None) -> list[Issue]:
    today = today or date.today()
    value = rec.get("transaction_date")
    text = (rec.get("raw_text") or {}).get("transaction_date")
    if value is None and text:
        return [Issue("date_not_interpreted", "review",
                      f"date text '{text}' was found but not converted to a date")]
    if value is None:
        return [Issue("missing_date", "review", "transaction date is missing")]
    try:
        d = value if isinstance(value, date) else datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return [Issue("date_unparseable", "review", f"cannot parse date {value!r}")]
    if d > today:
        return [Issue("date_in_future", "review", f"date {d} is in the future")]
    return []


def check_currency(rec: dict) -> list[Issue]:
    if rec.get("total") is not None and not rec.get("currency"):
        return [Issue("missing_currency", "info", "no currency code returned")]
    return []


def validate(rec: dict, threshold: float = 0.80, today: date | None = None) -> list[Issue]:
    return (check_required(rec) + check_confidence(rec, threshold)
            + check_arithmetic(rec) + check_date(rec, today) + check_currency(rec))


def find_duplicates(records: list[dict]) -> dict[str, list[Issue]]:
    """Same merchant + date + total appearing more than once in a batch."""
    seen: dict[tuple, str] = {}
    issues: dict[str, list[Issue]] = {}
    for rec in records:
        if rec.get("total") is None:
            continue
        key = ((rec.get("merchant") or "").strip().lower(),
               str(rec.get("transaction_date")), round(float(rec["total"]), 2))
        if key in seen:
            issues.setdefault(rec["source_file"], []).append(
                Issue("possible_duplicate", "review",
                      f"same merchant, date and total as {seen[key]}"))
        else:
            seen[key] = rec["source_file"]
    return issues


def review_batch(records: list[dict], threshold: float = 0.80,
                 today: date | None = None) -> list[dict]:
    """Validate every record; add needs_review and the reasons."""
    dupes = find_duplicates(records)
    out = []
    for rec in records:
        issues = validate(rec, threshold, today) + dupes.get(rec["source_file"], [])
        reasons = [i.message for i in issues if i.severity == "review"]
        out.append({**rec,
                    "issues": [asdict(i) for i in issues],
                    "needs_review": bool(reasons),
                    "review_reasons": "; ".join(reasons)})
    return out
