"""
Priority models for ProjectionLab plan cash-flow priorities.

NOTE — plugin API limitation (discovered 2026-03-06):
  `restorePlans()` silently strips `plan.priorities` — it has an internal
  field whitelist and priorities are not included.  Write operations
  (create, delete, reorder) must therefore bypass `restorePlans` and mutate
  `plan.priorities.events` directly inside the Pinia store:

      const planStore = pinia._s.get('plan');
      const plan = planStore.plans.find(p => p.id === planId);
      plan.priorities.events.push(newEvent);   // Vue reactivity auto-saves

  `plugin_api._pinia_mutate_priorities(plan_id, js_body)` encapsulates this.
  The MCP tools for priorities are intentionally omitted from server.py until
  this approach is validated as stable.
"""
from __future__ import annotations
import uuid
from typing import Annotated, Any, Literal, Optional
from pydantic import BaseModel, Field


class PriorityTimeRef(BaseModel):
    """A point in time used for priority start/end dates.

    Common keyword values:
      "beforeCurrentYear" — already active / started in the past
      "now"               — current year
      "endOfPlan"         — runs until the end of the plan
      "retirement"        — at retirement
      "never"             — no end

    Use modifier="exclude" for "before" semantics (exclusive start).
    Use modifier="include" for "at or through" semantics (inclusive end).
    """
    type: Literal["keyword", "age"]
    value: str
    modifier: Optional[Literal["include", "exclude"]] = None


class Priority(BaseModel):
    """Any priority event as returned by exportData. Extra fields are preserved."""
    model_config = {"extra": "allow"}

    id: str
    planPath: Literal["priorities"] = "priorities"
    type: str
    name: str
    goalIntent: str
    start: Optional[PriorityTimeRef] = None
    end: Optional[PriorityTimeRef] = None
    accountId: Optional[str] = None
    assetId: Optional[str] = None


# --- New priority models (for creating) ---

_DEFAULT_START = lambda: PriorityTimeRef(type="keyword", value="beforeCurrentYear")
_DEFAULT_END = lambda: PriorityTimeRef(type="keyword", value="endOfPlan", modifier="include")


class NewCashPriority(BaseModel):
    """Build and maintain a cash savings target (e.g. emergency fund).

    Requires an existing savings account ID.

    type values:
      "emergency-fund" — standard emergency fund goal
      "cash-reserves"  — equivalent cash reserves goal
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    planPath: Literal["priorities"] = "priorities"
    type: Literal["emergency-fund", "cash-reserves"] = "emergency-fund"
    name: Annotated[str, Field(description='Display name, e.g. "Emergency Fund".')]
    accountId: Annotated[str, Field(description="ID of the savings account to fund.")]
    owner: Literal["me", "spouse"] = "me"
    goalIntent: Literal["maintain", "save"] = "maintain"
    title: str = "Emergency Fund"
    icon: str = "mdi-piggy-bank"
    color: str = "teal-lighten-1"
    mode: Literal["target"] = "target"
    amount: Annotated[float, Field(description="Target balance to build up to.")] = 5000
    amountType: Literal["today$", "absolute"] = "today$"
    desiredContribution: Literal["max", "amount"] = "max"
    frequency: Literal["monthly", "yearly"] = "monthly"
    contribution: float = 0
    contributionType: Literal["today$", "absolute"] = "today$"
    contributionsAreFixed: bool = False
    tapFund: bool = False
    tapRate: float = 25
    showChartIcon: bool = True
    persistent: bool = False
    start: PriorityTimeRef = Field(default_factory=_DEFAULT_START)
    end: PriorityTimeRef = Field(default_factory=_DEFAULT_END)


class NewInvestmentPriority(BaseModel):
    """Contribute income to an investment or savings account (taxable, IRA, 401k, etc.).

    Common type values:
      "taxable"   — taxable brokerage account
      "ira"       — traditional IRA
      "roth"      — Roth IRA
      "401k"      — 401(k) / employer plan
      "savings"   — savings account
      "hsa"       — health savings account
      "crypto"    — cryptocurrency account
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    planPath: Literal["priorities"] = "priorities"
    type: Annotated[str, Field(description='Account category type, e.g. "taxable", "ira", "roth", "401k", "savings".')]
    name: Annotated[str, Field(description="Display name for this priority.")]
    accountId: Annotated[str, Field(description="ID of the investment or savings account.")]
    goalIntent: str = "invest"
    title: str = ""
    icon: str = "mdi-finance"
    color: str = "cyan"
    desiredContribution: Literal["max", "amount"] = "max"
    amount: float = 0
    amountType: Literal["today$", "absolute"] = "today$"
    frequency: Literal["monthly", "yearly"] = "monthly"
    start: PriorityTimeRef = Field(default_factory=_DEFAULT_START)
    end: PriorityTimeRef = Field(default_factory=_DEFAULT_END)


class NewAssetLoanPriority(BaseModel):
    """Make extra payments on a financed real asset (e.g. mortgage, car loan).

    Requires an existing real asset ID that has financing attached.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    planPath: Literal["priorities"] = "priorities"
    type: Literal["asset"] = "asset"
    name: Annotated[str, Field(description='Display name, e.g. "Extra Mortgage Payments".')]
    assetId: Annotated[str, Field(description="ID of the financed real asset.")]
    owner: Literal["me", "spouse"] = "me"
    goalIntent: Literal["pay-extra"] = "pay-extra"
    title: str = "Extra Financed Asset Payments"
    icon: str = "mdi-home"
    color: str = "indigo-lighten-1"
    desiredContribution: Literal["max", "amount"] = "amount"
    extra: Annotated[float, Field(description="Extra monthly/yearly payment amount.")] = 0
    extraType: Literal["today$", "absolute"] = "today$"
    contributionsAreFixed: bool = False
    frequency: Literal["monthly", "yearly"] = "monthly"
    start: PriorityTimeRef = Field(
        default_factory=lambda: PriorityTimeRef(type="keyword", value="now", modifier="exclude")
    )
    end: PriorityTimeRef = Field(default_factory=_DEFAULT_END)


class NewDebtPriority(BaseModel):
    """Make payments toward an unsecured debt account (credit card, student loans, etc.).

    Requires an existing debt account ID from Current Finances.

    Common type values:
      "credit-card"    — credit card debt
      "student-loans"  — student loan debt
      "medical"        — medical debt
      "debt"           — generic unsecured debt
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    planPath: Literal["priorities"] = "priorities"
    type: Annotated[str, Field(description='Debt category type, e.g. "debt", "credit-card", "student-loans", "medical".')]
    name: Annotated[str, Field(description="Display name for this priority.")]
    accountId: Annotated[str, Field(description="ID of the debt account.")]
    owner: Literal["me", "spouse"] = "me"
    goalIntent: str = "pay-debt"
    title: str = "Debt Payments"
    icon: str = "mdi-credit-card"
    color: str = "red-lighten-1"
    desiredContribution: Literal["max", "amount"] = "max"
    amount: float = 0
    amountType: Literal["today$", "absolute"] = "today$"
    frequency: Literal["monthly", "yearly"] = "monthly"
    contributionsAreFixed: bool = False
    start: PriorityTimeRef = Field(default_factory=_DEFAULT_START)
    end: PriorityTimeRef = Field(default_factory=_DEFAULT_END)


class NewTransferPriority(BaseModel):
    """Transfer funds between accounts on a schedule.

    fromAccountId and toAccountId must be existing account IDs.
    frequency="once" makes it a one-time transfer at the specified timing.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    planPath: Literal["priorities"] = "priorities"
    type: Literal["transfer"] = "transfer"
    name: Annotated[str, Field(description='Display name, e.g. "Roth Conversion".')] = "Transfer"
    fromAccountId: Annotated[str, Field(description="Source account ID.")]
    toAccountId: Annotated[str, Field(description="Destination account ID.")]
    goalIntent: Literal["transfer"] = "transfer"
    title: str = "Transfer"
    icon: str = "mdi-bank-transfer"
    color: str = "blue-grey-lighten-1"
    amount: Annotated[float, Field(description="Transfer amount.")] = 0
    amountType: Literal["today$", "absolute"] = "today$"
    frequency: Literal["once", "monthly", "yearly"] = "once"
    taxHandling: Literal["auto", "taxable", "tax-free"] = "auto"
    timing: PriorityTimeRef = Field(
        default_factory=lambda: PriorityTimeRef(type="keyword", value="now")
    )


class Priorities(BaseModel):
    """The priorities container stored in a plan."""
    events: list[Any] = []
