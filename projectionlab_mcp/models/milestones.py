from __future__ import annotations
import uuid
from typing import Annotated, Any, Literal, Optional, Union
from pydantic import BaseModel, Field


# --- Criterion Types ---

class DateCriterion(BaseModel):
    """Triggers at a specific date (or before it if modifier='exclude')."""
    type: Literal["date"]
    value: str  # "YYYY-MM-DD"
    modifier: Optional[Literal["include", "exclude"]] = None


class YearCriterion(BaseModel):
    """Triggers at a specific year (or before it if modifier='exclude')."""
    type: Literal["year"]
    value: str  # "YYYY-MM-DD" (only the year portion is used)
    modifier: Optional[Literal["include", "exclude"]] = None


class MilestoneRefCriterion(BaseModel):
    """Triggers at (or before) another milestone.

    modifier='include' → at the milestone; modifier='exclude' → before it.
    """
    type: Literal["milestone"]
    value: str  # ID of the referenced milestone
    modifier: Literal["include", "exclude"]


MetricType = Literal[
    "netWorth",
    "liquidNetWorth",
    "passiveIncome",
    "expenses",
    "spending",
    "discretionarySpending",
    "essentialSpending",
    "totalDebt",
    "preTaxSavingsRate",
    "afterTaxSavingsRate",
]


class MetricCriterion(BaseModel):
    """Triggers when a financial metric crosses a threshold.

    Fields:
      operator   — ">=" (at least), "<=" (at most), or "==" (exactly)
      value      — the threshold number
      valueType  — how to interpret value:
                     "spending"  → multiple of annual spending (e.g. 25x)
                     "today$"    → absolute amount in today's dollars
                     "absolute"  → absolute nominal amount
      measurement — "avg" (rolling average) or "single" (point-in-time)
      range       — number of years to average (used when measurement="avg")
      fixedRange  — if false, average grows until retirement then stays fixed
    """
    type: MetricType
    operator: Literal[">=", "<=", "=="]
    value: float
    valueType: Literal["spending", "today$", "absolute"]
    measurement: Optional[Literal["avg", "single"]] = None
    range: Optional[int] = None
    fixedRange: Optional[bool] = None


class GenericCriterion(BaseModel):
    """Catch-all for account/debt balance criteria and any unknown types."""
    model_config = {"extra": "allow"}
    type: str


MilestoneCriterion = Annotated[
    Union[
        DateCriterion,
        YearCriterion,
        MilestoneRefCriterion,
        MetricCriterion,
        GenericCriterion,
    ],
    Field(union_mode="left_to_right"),
]


# --- Milestone Models ---

class Milestone(BaseModel):
    """A milestone as returned by exportData."""
    id: str
    name: str
    color: str
    icon: str
    criteria: list[MilestoneCriterion]
    removable: Optional[bool] = None


class NewMilestone(BaseModel):
    """Parameters for creating a new user milestone."""
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID (auto-generated if omitted).",
    )
    name: Annotated[str, Field(description="Display name shown on the plan timeline.")]
    color: str = Field(
        default="blue-lighten-1",
        description='Material Design color class, e.g. "teal-lighten-1", "orange-lighten-1".',
    )
    icon: str = Field(
        default="mdi-flag-variant",
        description='MDI icon name, e.g. "mdi-palm-tree", "mdi-fire", "mdi-home".',
    )
    criteria: Annotated[
        list[MilestoneCriterion],
        Field(description="One or more criteria that define when this milestone is reached."),
    ]
    removable: bool = True
