from __future__ import annotations
import uuid
from typing import Annotated, Literal
from pydantic import BaseModel, Field
from .common import WithdrawAge


class SavingsAccount(BaseModel):
    """A savings account in Current Finances (today.savingsAccounts).

    Verified against the record ProjectionLab 4.6 creates from the "Add Savings" button:
      color="teal-lighten-1", icon="mdi-piggy-bank", investmentGrowthType="none",
      dividendType="plan", repurpose=True, withdrawAge={keyword now include}.
    The Current Finances page only exposes Balance and Owner; the other fields are set
    from the plan editor. Unknown/extra fields are preserved.
    """
    model_config = {"extra": "allow"}

    id: str
    name: str
    title: str
    type: Literal["savings"]
    owner: Literal["me", "spouse"]
    balance: float
    color: str
    icon: str
    liquid: bool
    withdraw: bool
    repurpose: bool
    investmentGrowthType: str  # observed: "none", "plan" (investment accounts also use "plan")
    investmentGrowthRate: float
    dividendType: str          # observed: "plan"
    dividendRate: float
    withdrawAge: WithdrawAge


class NewSavingsAccount(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique ID (auto-generated if omitted).")
    name: Annotated[str, Field(description="Internal name/key for the account.")]
    title: Annotated[str, Field(description="Display title shown in ProjectionLab.")]
    type: Literal["savings"] = "savings"
    owner: Annotated[Literal["me", "spouse"], Field(description='Account owner: "me" or "spouse".')]
    balance: Annotated[float, Field(description="Current balance.")]
    color: str = "teal-lighten-1"
    icon: str = "mdi-piggy-bank"
    liquid: bool = True
    withdraw: bool = True
    repurpose: bool = True
    investmentGrowthType: str = "none"
    investmentGrowthRate: float = 0.0
    dividendType: str = "plan"
    dividendRate: float = 0.0
    withdrawAge: WithdrawAge = Field(
        default_factory=lambda: WithdrawAge(type="keyword", modifier="include", value="now")
    )
