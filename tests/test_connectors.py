"""Property-based tests for CSV parser + deduplication.

Tests:
  1. Arbitrary CSV input never crashes the parser (fuzz)
  2. Formula-injection characters never survive to NormalisedTransaction
  3. Deduplicate is idempotent: dedupe(dedupe(x)) == dedupe(x)
  4. Deduplication is stable under reordering
  5. Plaid ALLOWED_PRODUCTS rejects non-allowed products

Ref: .kiro/specs/phase-1-architecture/tasks.md Appendix
"""

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.connectors.csv_import import parse_csv, sanitize_cell
from app.services.connectors.plaid import PlaidConnector, ALLOWED_PRODUCTS
from app.services.deduplication import deduplicate, compute_row_hash
from app.services.connectors.base import NormalisedTransaction


# ── Strategies ────────────────────────────────────────────────────────────────

date_strategy = st.dates(min_value=date(2000, 1, 1), max_value=date(2030, 12, 31))
amount_strategy = st.decimals(
    min_value=Decimal("-999999"), max_value=Decimal("999999"),
    allow_nan=False, allow_infinity=False, places=2,
)
merchant_strategy = st.text(min_size=0, max_size=100).map(lambda s: s.strip() or None)

transaction_strategy = st.builds(
    NormalisedTransaction,
    external_id=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    posted=date_strategy,
    amount=amount_strategy,
    currency=st.just("USD"),
    category=st.one_of(st.none(), st.text(min_size=1, max_size=30)),
    merchant_norm=merchant_strategy,
    raw_merchant=merchant_strategy,
    pending=st.booleans(),
)


# ── CSV Parser Fuzz ───────────────────────────────────────────────────────────

@given(content=st.text(min_size=0, max_size=10000))
@settings(max_examples=200)
def test_csv_parser_never_crashes_on_arbitrary_input(content: str) -> None:
    """Arbitrary text input to CSV parser must never raise an unhandled exception."""
    result = parse_csv(content, source_filename="fuzz.csv")
    # Parser always returns a result object — never crashes
    assert result is not None
    assert isinstance(result.accepted, list)
    assert isinstance(result.quarantined, list)


@given(content=st.binary(min_size=0, max_size=5000))
@settings(max_examples=100)
def test_csv_parser_handles_binary_input(content: bytes) -> None:
    """Binary garbage to CSV parser must not crash."""
    result = parse_csv(content, source_filename="binary_fuzz.csv")
    assert result is not None


# ── Formula Injection Sanitization ────────────────────────────────────────────

@given(st.from_regex(r"^[=+\-@].+", fullmatch=True))
@settings(max_examples=200)
def test_formula_injection_characters_stripped(cell: str) -> None:
    """Cells starting with =, +, -, @ must have those characters removed."""
    sanitized = sanitize_cell(cell)
    assert not sanitized.startswith("=")
    assert not sanitized.startswith("+")
    assert not sanitized.startswith("-")
    assert not sanitized.startswith("@")


def test_formula_injection_corpus():
    """Known formula-injection payloads are neutralized."""
    payloads = [
        "=CMD('calc')",
        "+cmd|'/C calc'!A0",
        "-1+1",
        "@SUM(A1:A100)",
        "=HYPERLINK(\"http://evil.com\")",
        "+IMPORT('http://evil.com/data.csv')",
    ]
    for payload in payloads:
        sanitized = sanitize_cell(payload)
        assert sanitized[0] not in "=+-@", f"Payload not sanitized: {payload}"


def test_csv_with_injection_rows_accepted_safely():
    """CSV containing formula-injection rows parses without those chars in output."""
    csv_content = "date,amount,description\n2026-01-15,100.00,=CMD('calc')\n2026-01-16,50.00,Normal merchant\n"
    result = parse_csv(csv_content)
    for txn in result.accepted:
        if txn.raw_merchant:
            assert not txn.raw_merchant.startswith("=")
            assert not txn.raw_merchant.startswith("+")


# ── Deduplication Idempotency ─────────────────────────────────────────────────

@given(transactions=st.lists(transaction_strategy, min_size=0, max_size=50))
@settings(max_examples=100)
def test_deduplicate_idempotent(transactions: list[NormalisedTransaction]) -> None:
    """sync(sync(x)) == sync(x) — deduplicating twice produces the same result."""
    existing_ids: set[str] = set()
    existing_hashes: set[str] = set()

    # First pass
    new1, _ = deduplicate(transactions, existing_ids, existing_hashes)

    # Simulate that new1 was persisted — add their IDs/hashes to existing sets
    for txn in new1:
        if txn.external_id:
            existing_ids.add(txn.external_id)
        else:
            existing_hashes.add(compute_row_hash(txn.posted, txn.amount, txn.merchant_norm))

    # Second pass with same input — should produce nothing new
    new2, _ = deduplicate(transactions, existing_ids, existing_hashes)
    assert new2 == [], "Deduplicate is not idempotent — second pass produced new items"


@given(transactions=st.lists(transaction_strategy, min_size=2, max_size=30))
@settings(max_examples=50)
def test_deduplicate_order_independent(transactions: list[NormalisedTransaction]) -> None:
    """Reordering input doesn't change the deduplicated result set."""
    import random

    existing_ids: set[str] = set()
    existing_hashes: set[str] = set()

    new1, _ = deduplicate(transactions, existing_ids.copy(), existing_hashes.copy())

    # Shuffle and deduplicate again
    shuffled = transactions.copy()
    random.shuffle(shuffled)
    new2, _ = deduplicate(shuffled, existing_ids.copy(), existing_hashes.copy())

    # Same set of transactions should survive (order may differ)
    ids1 = {t.external_id or compute_row_hash(t.posted, t.amount, t.merchant_norm) for t in new1}
    ids2 = {t.external_id or compute_row_hash(t.posted, t.amount, t.merchant_norm) for t in new2}
    assert ids1 == ids2, "Deduplicate result changes under reordering"


# ── Plaid ALLOWED_PRODUCTS ────────────────────────────────────────────────────

def test_plaid_allowed_products_rejects_auth():
    """INV-2: Auth product must be rejected."""
    with pytest.raises(ValueError, match="INV-2 violation"):
        PlaidConnector.validate_products(["transactions", "auth"])


def test_plaid_allowed_products_rejects_payment():
    """INV-2: Payment products must be rejected."""
    with pytest.raises(ValueError, match="INV-2 violation"):
        PlaidConnector.validate_products(["payment_initiation"])


def test_plaid_allowed_products_accepts_valid():
    """Valid read-only products pass without error."""
    PlaidConnector.validate_products(["transactions", "investments", "liabilities", "balance"])


# ── Row Hash Stability ────────────────────────────────────────────────────────

@given(
    posted=date_strategy,
    amount=amount_strategy,
    merchant=st.one_of(st.none(), st.text(min_size=1, max_size=100)),
)
@settings(max_examples=100)
def test_row_hash_deterministic(posted: date, amount: Decimal, merchant: str | None) -> None:
    """Same inputs always produce the same hash."""
    h1 = compute_row_hash(posted, amount, merchant)
    h2 = compute_row_hash(posted, amount, merchant)
    assert h1 == h2
    assert len(h1) == 40  # SHA-256 truncated to 40 hex chars
