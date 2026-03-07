from __future__ import annotations
import uuid
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field
from .real_assets import TimeRef, YearlyChange


class ForgiveRef(BaseModel):
    """Time reference used for the loan forgiveness date."""
    type: Literal["keyword", "age"]
    value: str
    modifier: Literal["include", "exclude"]


class AdditionalFields(BaseModel):
    disabled: bool = False
    whitelist: list[str] = ["fundWithAccounts", "taxDeductible", "itemized"]


class BaseDebt(BaseModel):
    model_config = {"extra": "allow"}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique ID (auto-generated if omitted).")
    name: Annotated[str, Field(description="Internal name/key for the debt.")]
    title: Annotated[str, Field(description="Display title shown in ProjectionLab.")]
    owner: Annotated[Literal["me", "spouse"], Field(description='Debt owner: "me" or "spouse".')]
    type: Literal["debt"] = "debt"
    planPath: str = "expenses"
    color: str = "orange-lighten-1"
    icon: str = Field(default="mdi-weight-pound", description="Material Design icon name.")
    order: int = Field(default=0, description="Display order among debts.")

    # Balance
    amount: Annotated[float, Field(description="Current outstanding balance.")]
    amountType: str = "today$"

    # Payments & interest
    monthlyPayment: float = Field(default=0, description="Monthly payment amount.")
    monthlyPaymentType: str = "today$"
    interestRate: float = Field(default=0, description="Annual interest rate (%).")
    interestType: Literal["simple", "compound"] = Field(default="compound", description='Interest calculation method: "simple" or "compound".')
    compounding: Literal["daily", "monthly"] = Field(default="daily", description='Compounding frequency: "daily" or "monthly".')

    # Schedule
    frequency: str = "monthly"
    frequencyChoices: bool = True
    start: TimeRef = Field(
        default_factory=lambda: TimeRef(type="keyword", value="beforeCurrentYear"),
        description='When the debt begins. Use {"type": "keyword", "value": "beforeCurrentYear"} for existing debt.'
    )
    end: TimeRef = Field(
        default_factory=lambda: TimeRef(type="keyword", value="never"),
        description='When the debt ends (paid off). Use {"type": "keyword", "value": "never"} to let payments determine payoff.'
    )
    effectiveDate: TimeRef = Field(
        default_factory=lambda: TimeRef(type="keyword", value="beforeCurrentYear"),
        description="Date the interest rate takes effect."
    )
    yearlyChange: YearlyChange = Field(
        default_factory=lambda: YearlyChange(type="none", amount=0),
        description="Annual change to the balance (typically none for debts)."
    )

    # Forgiveness
    hasForgiveness: bool = Field(default=False, description="Whether this debt has a forgiveness provision.")
    forgiveAt: ForgiveRef = Field(
        default_factory=lambda: ForgiveRef(type="keyword", value="now", modifier="include"),
        description="When loan forgiveness applies, if hasForgiveness is true."
    )

    additionalFields: AdditionalFields = Field(default_factory=AdditionalFields)


class GenericDebt(BaseDebt):
    """General-purpose unsecured debt (also covers credit card and medical debt)."""
    icon: str = "mdi-weight-pound"
    additionalFields: AdditionalFields = Field(
        default_factory=lambda: AdditionalFields(whitelist=["fundWithAccounts", "taxDeductible", "itemized"])
    )


class StudentLoansDebt(BaseDebt):
    subtype: Literal["student-loans"]  # required — drives union discrimination
    icon: str = "mdi-school"
    additionalFields: AdditionalFields = Field(
        default_factory=lambda: AdditionalFields(whitelist=["fundWithAccounts"])
    )


# StudentLoansDebt must come first so the subtype discriminates correctly
UnsecuredDebt = Union[StudentLoansDebt, GenericDebt]
