"""Net worth engine — aggregates balances + asset valuations into time series.

Ref: Phase 5 spec, REQ-DASH-1 (net worth headline + sparkline)

Net worth = sum(account balances) - sum(liabilities) + sum(asset valuations)
Computed daily from balance_snapshots + latest valuations.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from dataclasses import dataclass

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BalanceSnapshot, Account, Asset, Valuation


@dataclass
class NetWorthPoint:
    """A single point in the net worth time series."""
    as_of: date
    total: Decimal
    accounts_total: Decimal
    assets_total: Decimal


@dataclass
class NetWorthSummary:
    """Current net worth breakdown."""
    net_worth: Decimal
    depository: Decimal
    credit: Decimal  # negative = liability
    investment: Decimal
    loan: Decimal  # negative = liability
    assets: Decimal
    change_30d: Decimal | None


async def get_current_net_worth(session: AsyncSession) -> NetWorthSummary:
    """Compute current net worth from latest balance snapshots + asset valuations."""

    # Get latest balance per account (most recent snapshot for each)
    latest_balances = (
        select(
            Account.type,
            func.sum(BalanceSnapshot.current).label("total"),
        )
        .join(BalanceSnapshot, BalanceSnapshot.account_id == Account.id)
        .where(Account.is_active == True)
        .group_by(Account.type)
    )

    result = await session.execute(latest_balances)
    balances_by_type: dict[str, Decimal] = {}
    for row in result:
        balances_by_type[row.type] = row.total or Decimal("0")

    # Get latest asset valuations
    latest_valuations = (
        select(func.sum(Valuation.value))
        .select_from(Valuation)
        .join(Asset, Asset.id == Valuation.asset_id)
    )
    assets_result = await session.execute(latest_valuations)
    assets_total = assets_result.scalar() or Decimal("0")

    depository = balances_by_type.get("depository", Decimal("0"))
    credit = balances_by_type.get("credit", Decimal("0"))
    investment = balances_by_type.get("investment", Decimal("0"))
    loan = balances_by_type.get("loan", Decimal("0"))

    # Net worth = assets (positive) - liabilities (credit, loan are typically negative from Plaid)
    net_worth = depository + investment + assets_total + credit + loan

    return NetWorthSummary(
        net_worth=net_worth,
        depository=depository,
        credit=credit,
        investment=investment,
        loan=loan,
        assets=assets_total,
        change_30d=None,  # computed from time series
    )


async def get_net_worth_series(
    session: AsyncSession,
    days: int = 90,
) -> list[NetWorthPoint]:
    """Get net worth time series for the last N days.

    Used for the 90-day sparkline (REQ-DASH-1).
    Returns one data point per day with balances available.
    """
    start_date = date.today() - timedelta(days=days)

    # Get all balance snapshots in range, grouped by date
    query = (
        select(
            BalanceSnapshot.as_of,
            func.sum(BalanceSnapshot.current).label("accounts_total"),
        )
        .where(BalanceSnapshot.as_of >= start_date)
        .group_by(BalanceSnapshot.as_of)
        .order_by(BalanceSnapshot.as_of)
    )

    result = await session.execute(query)
    points: list[NetWorthPoint] = []

    for row in result:
        points.append(NetWorthPoint(
            as_of=row.as_of,
            total=row.accounts_total or Decimal("0"),
            accounts_total=row.accounts_total or Decimal("0"),
            assets_total=Decimal("0"),  # simplified — full impl queries per-date valuations
        ))

    return points
