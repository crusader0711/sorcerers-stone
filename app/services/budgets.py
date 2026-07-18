"""Budget service — category budgets with month-over-month tracking.

Provides budget creation, spend-vs-budget comparison, and historical trends.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class Budget:
    """A category budget for a given month."""
    category: str
    month: date  # first day of month
    limit: Decimal
    spent: Decimal = Decimal("0")

    @property
    def remaining(self) -> Decimal:
        return self.limit - self.spent

    @property
    def percent_used(self) -> float:
        if self.limit == 0:
            return 0.0
        return float(self.spent / self.limit * 100)

    @property
    def over_budget(self) -> bool:
        return self.spent > self.limit


@dataclass
class Goal:
    """A savings or financial goal."""
    name: str
    target: Decimal
    current: Decimal = Decimal("0")
    target_date: date | None = None

    @property
    def progress_percent(self) -> float:
        if self.target == 0:
            return 100.0
        return float(self.current / self.target * 100)

    @property
    def remaining(self) -> Decimal:
        return max(Decimal("0"), self.target - self.current)


async def get_budgets_for_month(session, month: date) -> list[Budget]:
    """Get all budgets for a given month with current spend calculated.

    Spend is computed from transactions in the same category within the month.
    """
    # Phase 5 full implementation: query transactions grouped by category
    # for the given month, compare against stored budget limits
    return []


async def get_goals(session) -> list[Goal]:
    """Get all active financial goals with current progress."""
    # Phase 5 full implementation: query goals table, compute current values
    return []
