from __future__ import annotations
import uuid
from enum import Enum
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field
from .common import WithdrawAge, DateRef, DisplayAge


class InvestmentAccountType(str, Enum):
    taxable = "taxable"
    crypto = "crypto"
    hsa = "hsa"
    plan_529 = "529"
    ira = "ira"
    roth_ira = "roth-ira"
    traditional_401k = "401k"
    roth_401k = "roth401k"
    plan_403b = "403b"
    roth_403b = "roth403b"
    plan_457b = "457b"
    roth_457b = "roth457b"
    pension = "pension"


class BaseInvestmentAccount(BaseModel):
    """Fields common to all investment account types."""
    model_config = {"extra": "allow"}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: Annotated[str, Field(description="Internal name/key for the account.")]
    title: Annotated[str, Field(description="Display title shown in ProjectionLab.")]
    subtitle: str = ""
    owner: Annotated[Literal["me", "spouse"], Field(description='Account owner: "me" or "spouse".')]
    balance: Annotated[float, Field(description="Current balance.")]
    color: str = "cyan"
    icon: str = "mdi-finance"
    liquid: bool = True
    withdraw: bool = True
    isPassiveIncome: bool = False
    dividendsArePassiveIncome: bool = True
    investmentGrowthType: str = "plan"  # "plan", "fixed", "portfolio"
    investmentGrowthRate: float = 0.0
    dividendType: str = "plan"          # "plan", "none", "reinvest", "income"
    dividendRate: float = 0.0
    yearlyFee: float = 0.0
    yearlyFeeType: str = "%"            # "%" or "$"
    withdrawAge: WithdrawAge = Field(
        default_factory=lambda: WithdrawAge(type="keyword", modifier="include", value="now")
    )


class TaxableInvestmentAccount(BaseInvestmentAccount):
    type: Literal["taxable"] = "taxable"
    dividendTaxType: str = "plan"       # "plan", "qualified", "ordinary"
    dividendReinvestment: bool = True
    costBasis: Optional[float] = None
    notes: Optional[str] = None
    hasNotes: Optional[bool] = None


class CryptoInvestmentAccount(BaseInvestmentAccount):
    type: Literal["crypto"] = "crypto"
    dividendTaxType: str = "income"
    dividendReinvestment: bool = True
    costBasis: Optional[float] = None


class HSAInvestmentAccount(BaseInvestmentAccount):
    type: Literal["hsa"] = "hsa"
    country: str = "US"
    hasEWPenalty: bool = True
    EWPenaltyRate: float = 20.0
    EWAge: int = 65


class Plan529InvestmentAccount(BaseInvestmentAccount):
    type: Literal["529"] = "529"
    country: str = "US"
    excludeFromFinances: bool = False
    costBasis: Optional[float] = None
    displayAge: DisplayAge = Field(
        default_factory=lambda: DisplayAge(type="keyword", value="now", modifier=18)
    )


class IRAInvestmentAccount(BaseInvestmentAccount):
    type: Literal["ira"] = "ira"
    country: str = "US"
    rmdType: str = "us"
    hasEWPenalty: bool = True
    EWPenaltyRate: float = 10.0
    EWAge: int = 60
    costBasis: Optional[float] = None


class InheritedIRAInvestmentAccount(IRAInvestmentAccount):
    subtype: Literal["inherited"]   # required — drives union discrimination
    rmdType: str = "us-inherited"
    hasEWPenalty: bool = False
    originalOwnerBirth: DateRef
    originalOwnerDeath: DateRef


class RothIRAInvestmentAccount(BaseInvestmentAccount):
    type: Literal["roth-ira"] = "roth-ira"
    country: str = "US"
    hasEWPenalty: bool = True
    EWPenaltyRate: float = 10.0
    EWAge: int = 60
    withdrawContribsFree: bool = True
    costBasis: Optional[float] = None


class InheritedRothIRAInvestmentAccount(RothIRAInvestmentAccount):
    subtype: Literal["inherited"]   # required — drives union discrimination
    rmdType: str = "us-inherited"
    hasEWPenalty: bool = False
    originalOwnerBirth: DateRef
    originalOwnerDeath: DateRef


# Inherited variants must come before their base types in the union so Pydantic
# matches them first (left-to-right). BaseInvestmentAccount is the fallback.
InvestmentAccount = Union[
    TaxableInvestmentAccount,
    CryptoInvestmentAccount,
    HSAInvestmentAccount,
    Plan529InvestmentAccount,
    InheritedIRAInvestmentAccount,
    IRAInvestmentAccount,
    InheritedRothIRAInvestmentAccount,
    RothIRAInvestmentAccount,
    BaseInvestmentAccount,
]
