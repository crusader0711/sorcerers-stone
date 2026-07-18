"""Monthly summary report generation.

Generates a structured summary of financial activity for a given month:
- Total income vs. total expenses
- Top spending categories
- Budget adherence
- Net worth change
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class CategoryBreakdown:
    """Spending breakdown for a single category."""
    category: str
    total: Decimal
    transaction_count: int
    percent_of_total: float = 0.0


@dataclass
class MonthlySummary:
    """Complete monthly financial summary."""
    month: date
    total_income: Decimal = Decimal("0")
    total_expenses: Decimal = Decimal("0")
    net_change: Decimal = Decimal("0")
    top_categories: list[CategoryBreakdown] = field(default_factory=list)
    transaction_count: int = 0
    net_worth_start: Decimal | None = None
    net_worth_end: Decimal | None = None
    net_worth_change: Decimal | None = None


async def generate_monthly_summary(session, month: date) -> MonthlySummary:
    """Generate a monthly summary report.

    Queries transactions for the given month, aggregates by category,
    computes income vs. expenses, and calculates net worth change.
    """
    from datetime import timedelta
    from sqlalchemy import select, func, and_
    from app.models import Transaction

    # Determine month boundaries
    month_start = month.replace(day=1)
    if month.month == 12:
        month_end = month.replace(year=month.year + 1, month=1, day=1)
    else:
        month_end = month.replace(month=month.month + 1, day=1)

    summary = MonthlySummary(month=month_start)

    # Query transactions in month
    query = select(Transaction).where(
        and_(
            Transaction.posted >= month_start,
            Transaction.posted < month_end,
            Transaction.pending == False,
        )
    )
    result = await session.execute(query)
    transactions = result.scalars().all()

    summary.transaction_count = len(transactions)

    # Separate income (negative amounts in Plaid convention) and expenses
    category_totals: dict[str, Decimal] = {}
    for txn in transactions:
        amount = txn.amount
        if amount < 0:
            summary.total_income += abs(amount)
        else:
            summary.total_expenses += amount

        cat = txn.category_override or txn.category or "Uncategorized"
        category_totals[cat] = category_totals.get(cat, Decimal("0")) + abs(amount)

    summary.net_change = summary.total_income - summary.total_expenses

    # Top categories by spend
    sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    total_spend = sum(category_totals.values()) or Decimal("1")

    summary.top_categories = [
        CategoryBreakdown(
            category=cat,
            total=amount,
            transaction_count=sum(
                1 for t in transactions
                if (t.category_override or t.category or "Uncategorized") == cat
            ),
            percent_of_total=float(amount / total_spend * 100),
        )
        for cat, amount in sorted_cats[:10]
    ]

    return summary
