"""CSV/OFX import connector — streaming parser with formula-injection sanitization.

Ref: REQ-IMP-1, REQ-IMP-2, REQ-IMP-3, REQ-U6
Security: INV-6 (data minimization), formula-injection prevention

Strips leading =, +, -, @ characters from cell values before any processing.
Validates rows through a strict Pydantic model. Invalid rows are quarantined.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, field_validator, ValidationError

from app.logging_config import get_logger
from app.services.connectors.base import NormalisedTransaction

logger = get_logger(__name__)

# Characters that could trigger formula injection in downstream tools
FORMULA_INJECTION_PATTERN = re.compile(r"^[=+\-@]")


def sanitize_cell(value: str) -> str:
    """Strip formula-injection characters from a cell value (REQ-U6).

    Leading =, +, -, @ are removed. This prevents CSV injection when data
    is later exported or viewed in spreadsheet applications.
    """
    if FORMULA_INJECTION_PATTERN.match(value):
        return FORMULA_INJECTION_PATTERN.sub("", value).lstrip()
    return value


class CsvTransactionRow(BaseModel):
    """Strict Pydantic model for CSV row validation.

    Only these fields survive to the database — all others are dropped (INV-6).
    """

    date: str
    amount: str
    description: str | None = None
    category: str | None = None
    currency: str = "USD"

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        # Must be parseable as ISO date
        try:
            date.fromisoformat(v.strip())
        except ValueError:
            raise ValueError(f"Invalid date format: {v}")
        return v.strip()

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: str) -> str:
        try:
            Decimal(v.strip().replace(",", ""))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Invalid amount: {v}")
        return v.strip().replace(",", "")


class CsvImportResult:
    """Result of a CSV import operation."""

    def __init__(self) -> None:
        self.accepted: list[NormalisedTransaction] = []
        self.quarantined: list[dict] = []  # {row_num, raw, reason}
        self.total_rows: int = 0


def parse_csv(
    content: str | bytes,
    source_filename: str = "upload.csv",
) -> CsvImportResult:
    """Parse and validate a CSV file into NormalisedTransactions.

    Steps:
      1. Decode content (UTF-8)
      2. Sanitize every cell for formula injection (REQ-U6)
      3. Validate each row through CsvTransactionRow Pydantic model
      4. Convert valid rows to NormalisedTransaction
      5. Quarantine invalid rows with reason

    Returns:
        CsvImportResult with accepted transactions and quarantined rows.
    """
    result = CsvImportResult()

    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
    else:
        text = content

    reader = csv.DictReader(io.StringIO(text))

    for row_num, raw_row in enumerate(reader, start=2):  # row 1 = header
        result.total_rows += 1

        # Sanitize all cells for formula injection
        sanitized = {k: sanitize_cell(v) if v else "" for k, v in raw_row.items()}

        # Map common CSV column names to our model fields
        mapped = _map_columns(sanitized)

        # Validate through Pydantic
        try:
            validated = CsvTransactionRow(**mapped)
        except ValidationError as e:
            result.quarantined.append({
                "row_num": row_num,
                "raw": str(sanitized)[:1024],  # truncate for storage
                "reason": str(e.errors()[0]["msg"]) if e.errors() else str(e),
            })
            continue

        # Convert to NormalisedTransaction
        try:
            txn = NormalisedTransaction(
                external_id=None,  # CSV has no stable external_id
                posted=date.fromisoformat(validated.date),
                amount=Decimal(validated.amount),
                currency=validated.currency,
                category=validated.category,
                merchant_norm=_normalize_merchant(validated.description),
                raw_merchant=validated.description,
                pending=False,
            )
            result.accepted.append(txn)
        except Exception as e:
            result.quarantined.append({
                "row_num": row_num,
                "raw": str(sanitized)[:1024],
                "reason": f"Conversion error: {e}",
            })

    logger.info(
        "csv_import_parsed",
        filename=source_filename,
        total=result.total_rows,
        accepted=len(result.accepted),
        quarantined=len(result.quarantined),
    )

    return result


def _map_columns(row: dict[str, str]) -> dict[str, str]:
    """Map common CSV column name variants to CsvTransactionRow fields."""
    # Normalize keys to lowercase
    lower = {k.lower().strip(): v for k, v in row.items()}

    return {
        "date": lower.get("date") or lower.get("posted") or lower.get("transaction_date") or "",
        "amount": lower.get("amount") or lower.get("debit") or lower.get("credit") or "0",
        "description": lower.get("description") or lower.get("memo") or lower.get("name") or lower.get("payee"),
        "category": lower.get("category") or lower.get("type"),
        "currency": lower.get("currency") or "USD",
    }


def _normalize_merchant(description: str | None) -> str | None:
    """Basic merchant normalization — trim, collapse whitespace, title case."""
    if not description:
        return None
    normalized = " ".join(description.split())
    return normalized.strip()[:255]
