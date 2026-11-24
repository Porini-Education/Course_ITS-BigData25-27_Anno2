"""Receipt extraction with Azure AI Document Intelligence.

The one function most code should call is `extract_receipt(path)`:

    input   : path to a PDF or image
    output  : a plain, normalized Python dictionary
    errors  : MissingFileError, UnsupportedDocumentError, ServiceError
    warnings: listed in result["warnings"] (missing fields, low confidence, ...)

Service results are cached as JSON under data/results/ so each document is
sent to Azure once. Re-running a notebook then costs nothing and works offline.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

MODEL_ID = "prebuilt-receipt"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "results"

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".heif"}


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------
class ExtractionError(Exception):
    """Base class for everything that stops a document being processed."""


class MissingFileError(ExtractionError):
    pass


class UnsupportedDocumentError(ExtractionError):
    pass


class ServiceError(ExtractionError):
    pass


# --------------------------------------------------------------------------
# Talking to the service
# --------------------------------------------------------------------------
def get_client():
    """Create a client from environment variables (never hard-code keys)."""
    try:
        from dotenv import load_dotenv  # optional convenience
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    except ImportError:
        pass
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential

    endpoint = os.environ.get("DOCUMENTINTELLIGENCE_ENDPOINT")
    key = os.environ.get("DOCUMENTINTELLIGENCE_API_KEY")
    if not endpoint or not key:
        raise ServiceError(
            "Set DOCUMENTINTELLIGENCE_ENDPOINT and DOCUMENTINTELLIGENCE_API_KEY "
            "(copy .env.example to .env and fill it in)."
        )
    return DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))


def cache_path(path: Path, model_id: str = MODEL_ID) -> Path:
    return CACHE_DIR / f"{path.name}.{model_id}.json"


def analyze(path: str | Path, model_id: str = MODEL_ID, client=None,
            use_cache: bool = True, **kwargs) -> dict:
    """Send one document to the service and return the raw result as a dict.

    The dict has the same camelCase keys as the REST JSON
    (pages, tables, documents[0].fields, ...).
    """
    path = Path(path)
    if not path.exists():
        raise MissingFileError(f"File not found: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise UnsupportedDocumentError(f"Unsupported file type: {path.suffix}")

    cached = cache_path(path, model_id)
    if use_cache and cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))

    from azure.core.exceptions import HttpResponseError, ServiceRequestError

    client = client or get_client()
    try:
        with open(path, "rb") as f:
            poller = client.begin_analyze_document(model_id, body=f, **kwargs)
        result = poller.result()  # waits for the long-running operation
    except HttpResponseError as e:  # 400 bad document, 401 bad key, 429 throttled...
        raise ServiceError(f"{path.name}: service returned {e.status_code}: {e.message}") from e
    except ServiceRequestError as e:  # DNS / network / wrong endpoint
        raise ServiceError(f"{path.name}: could not reach the service: {e}") from e

    raw = result.as_dict()
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(raw, indent=2, default=str), encoding="utf-8")
    return raw


# --------------------------------------------------------------------------
# Turning the response into ordinary Python
# --------------------------------------------------------------------------

DEFAULT_THRESHOLD = 0.80  # classroom value, NOT a production standard
# Fields we care about: service field name -> our normalized name
FIELD_MAP = {
    "MerchantName": "merchant",
    "TransactionDate": "transaction_date",
    "Subtotal": "subtotal",
    "TotalTax": "tax",
    "Tip": "tip",
    "Total": "total",
}
REQUIRED_FIELDS = ("merchant", "transaction_date", "total")

def field_value(field: dict | None) -> Any:
    """Return the typed value of one field, whatever its type."""
    if not field:
        return None
    ftype = field.get("type")
    if ftype == "currency":
        return (field.get("valueCurrency") or {}).get("amount")
    if ftype == "number":
        return field.get("valueNumber")
    if ftype == "date":
        return field.get("valueDate")
    if ftype == "time":
        return field.get("valueTime")
    if ftype == "string":
        return field.get("valueString")
    return field.get("content")


def field_currency(field: dict | None) -> str | None:
    if field and field.get("type") == "currency":
        return (field.get("valueCurrency") or {}).get("currencyCode")
    return None


def normalize_receipt(raw: dict, source_file: str = "",
                      threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Convert a raw receipt result into one flat dictionary."""
    out: dict[str, Any] = {"source_file": source_file}
    out.update({name: None for name in FIELD_MAP.values()})
    out.update({"currency": None, "confidence": {}, "raw_text": {},
                "warnings": [], "needs_review": False})

    documents = raw.get("documents") or []
    if not documents:
        out["warnings"].append("no receipt detected in the document")
        out["needs_review"] = True
        return out
    if len(documents) > 1:
        out["warnings"].append(f"{len(documents)} receipts detected; only the first is used")

    fields = documents[0].get("fields") or {}
    for service_name, name in FIELD_MAP.items():
        f = fields.get(service_name)
        out[name] = field_value(f)
        out["confidence"][name] = f.get("confidence") if f else None
        out["raw_text"][name] = f.get("content") if f else None
        if f and out["currency"] is None:
            out["currency"] = field_currency(f)

    for name in REQUIRED_FIELDS:
        if out[name] is None:
            out["warnings"].append(f"missing {name}")
    for name, conf in out["confidence"].items():
        if conf is not None and conf < threshold:
            out["warnings"].append(f"low confidence for {name}: {conf:.2f} < {threshold:.2f}")

    out["needs_review"] = bool(out["warnings"])
    return out


def extract_receipt(path: str | Path, threshold: float = DEFAULT_THRESHOLD,
                    client=None, use_cache: bool = True) -> dict:
    """Document path in, normalized dictionary out."""
    raw = analyze(path, client=client, use_cache=use_cache)
    return normalize_receipt(raw, source_file=Path(path).name, threshold=threshold)


def flatten_for_csv(record: dict) -> dict:
    """One CSV row: values plus one confidence column per field."""
    row = {k: v for k, v in record.items()
           if k not in ("confidence", "raw_text", "warnings")}
    for name, conf in record.get("confidence", {}).items():
        row[f"conf_{name}"] = conf
    row["warnings"] = "; ".join(record.get("warnings", []))
    return row
