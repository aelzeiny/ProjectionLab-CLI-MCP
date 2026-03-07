from __future__ import annotations
import uuid
from typing import Annotated, Literal
from pydantic import BaseModel, Field
from .common import WithdrawAge


class SavingsAccount(BaseModel):
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
    isPassiveIncome: bool
    investmentGrowthType: Literal["fixed", "portfolio"]
    investmentGrowthRate: float
    dividendType: Literal["none", "reinvest", "income"]
    dividendRate: float
    withdrawAge: WithdrawAge


class NewSavingsAccount(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique ID (auto-generated if omitted).")
    name: Annotated[str, Field(description="Internal name/key for the account.")]
    title: Annotated[str, Field(description="Display title shown in ProjectionLab.")]
    type: Literal["savings"] = "savings"
    owner: Annotated[Literal["me", "spouse"], Field(description='Account owner: "me" or "spouse".')]
    balance: Annotated[float, Field(description="Current balance.")]
    color: str = "#4CAF50"
    icon: str = "savings"
    liquid: bool = True
    withdraw: bool = True
    repurpose: bool = False
    isPassiveIncome: bool = False
    investmentGrowthType: Literal["fixed", "portfolio"] = "fixed"
    investmentGrowthRate: float = 0.05
    dividendType: Literal["none", "reinvest", "income"] = "none"
    dividendRate: float = 0.0
    withdrawAge: WithdrawAge = Field(
        default_factory=lambda: WithdrawAge(type="keyword", modifier="include", value="now")
    )
