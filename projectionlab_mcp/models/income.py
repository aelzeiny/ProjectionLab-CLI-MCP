"""
Plan-level income events (plan.income.events[]).

Every type, field, default and enum value here was captured on 2026-09-13 from ProjectionLab
4.6's "New Income" dialog: one event of each kind was added with only a name and amount, and
one Custom Income per dropdown option was added to learn what each option stores. Raw captures
live in docs/fixtures/income/; tests/schema/test_income_fixtures.py pins the defaults to them.
Models allow extra fields so nothing the app writes is dropped on a round trip.

UI choice        stored `type`
  Salary           salary
  Hourly Wage      hourly
  RSU Grant        rsu
  Inheritance      inheritance
  Side Hustle      side-hustle
  Tax Credit       tax-credit
  Tax Deduction    tax-deduction
  Pension Income   pension
  Social Security  social-security
  Custom Income    other

Dropdown label -> stored value (from the Custom Income form; the same selects appear on the
other types where relevant):

  Frequency:           Yearly=yearly  Once Per Year=yearly-lump-sum  Quarterly=quarterly
                       Monthly=monthly  Bi-Weekly=bi-weekly  Weekly=weekly  Daily=daily
                       Once=once (also sets start to {keyword now include})
  Change Over Time:    None=none  Increase=increase  Decrease=decrease  Match Inflation=match-inflation
                       Match Inflation +X%=inflation+  Match Inflation -X%=inflation-  Advanced=(not captured)
                       (`yearlyChange.amount` holds the X)
  Tax Handling Type:   Auto=auto  Wage=wage  Self-Employment=selfEmployment  Ordinary=ordinary
                       Dividend=dividend  Capital Gains=capGains            -> `taxCharacter`
  Withholding:         Auto=auto  Fixed Rate=fixed (+ `withholdingRate`)  None=none -> `withholdingMode`
  Passive Income:      Auto=(field absent)  Yes=true  No=false             -> `isPassiveIncome`
  Send To:             Automatic=(field absent)  Specific Account=`routeToAccounts: [<plan.accounts event id>]`
  Recurrence / Repeat: `repeat: true, repeatEnd {keyword endOfPlan include}, repeatInterval 0,
                        repeatIntervalType "between", repeatScaler 0`
  Earner:              You=me  <spouse name>=spouse  Joint=(not captured)
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal, Optional
from pydantic import BaseModel, Field

from .common import TimeRef

# Kept for backwards compatibility; the shared TimeRef covers every observed shape.
IncomeTimeRef = TimeRef


def _kw(value: str, modifier: str | None = None) -> TimeRef:
    return TimeRef(type="keyword", value=value, modifier=modifier)


def _ms(value: str, modifier: str | None = "include") -> TimeRef:
    return TimeRef(type="milestone", value=value, modifier=modifier)


class IncomeYearlyChange(BaseModel):
    """"Change Over Time". `type` ∈ none | increase | decrease | match-inflation | inflation+ | inflation-
    (plus an "Advanced" mode that has not been captured). `amount` is the yearly % for
    increase/decrease/inflation±."""
    model_config = {"extra": "allow"}

    type: str = "match-inflation"
    amount: float = 0
    amountType: str = "today$"
    limit: Optional[float] = 0
    limitEnabled: Optional[bool] = False
    limitType: Optional[str] = "today$"


YC_INFLATION = lambda: IncomeYearlyChange()               # noqa: E731
YC_NONE = lambda: IncomeYearlyChange(type="none")         # noqa: E731


class BaseIncome(BaseModel):
    """Fields present on every income event the UI creates."""
    model_config = {"extra": "allow"}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    name: str
    title: str
    icon: str
    owner: str = "me"                   # observed: "me", "spouse" (UI also offers "Joint": value not captured)
    planPath: Literal["income"] = "income"
    amount: float = 0
    amountType: str = "today$"
    frequency: str = "yearly"           # see module docstring for every value
    frequencyChoices: bool = True
    start: TimeRef = Field(default_factory=lambda: _kw("beforeCurrentYear"))
    end: TimeRef = Field(default_factory=lambda: _ms("retirement"))
    yearlyChange: IncomeYearlyChange = Field(default_factory=YC_INFLATION)
    # Optional extras the UI writes only when set (see module docstring).
    key: Optional[float] = None
    hidden: Optional[bool] = None
    isPassiveIncome: Optional[bool] = None
    routeToAccounts: Optional[list[str]] = None
    repeatEnd: Optional[TimeRef] = None
    repeatInterval: Optional[float] = None
    repeatIntervalType: Optional[str] = None
    repeatScaler: Optional[float] = None


class TaxedIncome(BaseIncome):
    """Income with Tax Handling Type + Withholding + Tax-Exempt controls."""
    taxCharacter: str = "auto"
    taxExempt: bool = False
    withholdingMode: str = "auto"
    withholdingRate: Optional[float] = None   # only when withholdingMode == "fixed"


class _EmploymentFields(BaseModel):
    """Part-Time Work and Defined Benefit Pension sub-forms (Salary and Hourly Wage)."""
    contribsReduceTaxableIncome: bool = True
    goPartTime: bool = False
    partTimeStart: TimeRef = Field(default_factory=lambda: _kw("now", "include"))
    partTimeEnd: TimeRef = Field(default_factory=lambda: _ms("retirement"))
    partTimeRate: float = 50
    hasPension: bool = False
    pensionContribution: float = 0
    pensionContributionType: str = "%"
    pensionPayoutAmount: float = 0
    pensionPayoutRate: float = 25
    pensionPayoutType: str = "fap"
    pensionPayoutsAreTaxFree: bool = False
    pensionPayoutsStart: TimeRef = Field(default_factory=lambda: _ms("retirement"))
    pensionPayoutsEnd: TimeRef = Field(default_factory=lambda: _kw("endOfPlan", "include"))


class Salary(TaxedIncome, _EmploymentFields):
    type: Literal["salary"] = "salary"
    title: str = "Salary"
    icon: str = "mdi-office-building"


class HourlyWage(TaxedIncome, _EmploymentFields):
    """`amount` is the hourly rate; `hoursPerWeek` × rate gives the yearly figure."""
    type: Literal["hourly"] = "hourly"
    title: str = "Hourly Wage"
    icon: str = "mdi-briefcase-clock"
    frequencyChoices: bool = False
    hoursPerWeek: float = 40


class RsuGrant(TaxedIncome):
    type: Literal["rsu"] = "rsu"
    title: str = "RSU Grant"
    icon: str = "mdi-finance"
    frequency: str = "once"
    start: TimeRef = Field(default_factory=lambda: _kw("now", "include"))
    yearlyChange: IncomeYearlyChange = Field(default_factory=YC_NONE)
    repeat: bool = False


class SideHustle(TaxedIncome):
    type: Literal["side-hustle"] = "side-hustle"
    title: str = "Side Hustle"
    icon: str = "mdi-piggy-bank"
    taxCharacter: str = "selfEmployment"
    yearlyChange: IncomeYearlyChange = Field(default_factory=YC_NONE)
    repeat: bool = False


class CustomIncome(TaxedIncome):
    """UI: "Custom Income" (stored type "other")."""
    type: Literal["other"] = "other"
    title: str = "Custom Income"
    icon: str = "mdi-currency-usd-circle"
    preventOverflow: bool = False
    repeat: bool = False


class Inheritance(BaseIncome):
    """Has Tax Handling Type and Tax-Exempt but no Withholding control."""
    type: Literal["inheritance"] = "inheritance"
    title: str = "Inheritance"
    icon: str = "mdi-gift"
    frequency: str = "once"
    start: TimeRef = Field(default_factory=lambda: _kw("now", "include"))
    yearlyChange: IncomeYearlyChange = Field(default_factory=YC_NONE)
    taxCharacter: str = "auto"
    taxExempt: bool = False
    repeat: bool = False


class TaxCredit(BaseIncome):
    """`amount` is the credit; reduces tax in `jurisdictions` for `taxType`."""
    type: Literal["tax-credit"] = "tax-credit"
    title: str = "Tax Credit"
    icon: str = "mdi-file-document-outline"
    frequency: str = "once"
    start: TimeRef = Field(default_factory=lambda: _kw("now", "include"))
    yearlyChange: IncomeYearlyChange = Field(default_factory=YC_NONE)
    jurisdictions: list[str] = Field(default_factory=lambda: ["federal"])
    taxType: str = "income"
    refundable: bool = False
    repeat: bool = False


class TaxDeduction(BaseIncome):
    type: Literal["tax-deduction"] = "tax-deduction"
    title: str = "Tax Deduction"
    icon: str = "mdi-file-document-outline"
    frequency: str = "once"
    start: TimeRef = Field(default_factory=lambda: _kw("now", "include"))
    yearlyChange: IncomeYearlyChange = Field(default_factory=YC_NONE)
    jurisdictions: list[str] = Field(default_factory=lambda: ["federal"])
    taxType: str = "income"
    itemized: bool = False
    repeat: bool = False


class PensionIncome(BaseIncome):
    """Runs from retirement to end of plan; Withholding + Tax-Exempt but no Tax Handling Type."""
    type: Literal["pension"] = "pension"
    title: str = "Pension Income"
    icon: str = "mdi-account-clock"
    start: TimeRef = Field(default_factory=lambda: _ms("retirement"))
    end: TimeRef = Field(default_factory=lambda: _kw("endOfPlan", "include"))
    taxExempt: bool = False
    withholdingMode: str = "auto"
    withholdingRate: Optional[float] = None


class SocialSecurity(BaseIncome):
    """`amount` stays 0; the benefit comes from `primaryInsuranceAmount` × `expectedPercent`
    (or is estimated when `estimateIncome`). The UI sets `start` to a date derived from the
    earner's birth date (age 67 for the captured record), so pass it explicitly."""
    type: Literal["social-security"] = "social-security"
    title: str = "Social Security"
    icon: str = "mdi-account-supervisor-circle-outline"
    end: TimeRef = Field(default_factory=lambda: _kw("endOfPlan", "include"))
    taxExempt: bool = False
    country: str = "US"
    estimateIncome: bool = True
    expectedPercent: float = 100
    primaryInsuranceAmount: float = 0


Income = Annotated[
    Salary | HourlyWage | RsuGrant | SideHustle | CustomIncome | Inheritance
    | TaxCredit | TaxDeduction | PensionIncome | SocialSecurity,
    Field(discriminator="type"),
]

INCOME_MODELS: dict[str, type[BaseIncome]] = {
    "salary": Salary,
    "hourly": HourlyWage,
    "rsu": RsuGrant,
    "side-hustle": SideHustle,
    "other": CustomIncome,
    "inheritance": Inheritance,
    "tax-credit": TaxCredit,
    "tax-deduction": TaxDeduction,
    "pension": PensionIncome,
    "social-security": SocialSecurity,
}

IncomeType = Literal[
    "salary", "hourly", "rsu", "side-hustle", "other", "inheritance",
    "tax-credit", "tax-deduction", "pension", "social-security",
]


# ── creation parameters ──────────────────────────────────────────────────────

class NewIncome(BaseModel):
    """Parameters for adding an income event of any verified type to a plan.

    Only `type`, `name` and `amount` are required; everything else defaults to exactly what
    the ProjectionLab "New Income" dialog stores for that type. Enum values are listed in the
    module docstring of models/income.py.
    """
    type: Annotated[IncomeType, Field(description="Income kind (UI choice).")]
    name: Annotated[str, Field(description="Display name.")]
    amount: Annotated[float, Field(description="Amount per `frequency` in today's dollars (hourly: the hourly rate; social-security: leave 0 and set primaryInsuranceAmount in extra).")]
    owner: Annotated[str, Field(description='"me" or "spouse".')] = "me"
    frequency: Annotated[Optional[str], Field(description="yearly | yearly-lump-sum | quarterly | monthly | bi-weekly | weekly | daily | once")] = None
    start: Optional[TimeRef] = None
    end: Optional[TimeRef] = None
    yearlyChange: Optional[IncomeYearlyChange] = None
    taxCharacter: Annotated[Optional[str], Field(description="auto | wage | selfEmployment | ordinary | dividend | capGains (types with a Tax Handling control only)")] = None
    withholdingMode: Annotated[Optional[str], Field(description="auto | fixed | none (types with a Withholding control only)")] = None
    withholdingRate: Annotated[Optional[float], Field(description="Percent, used with withholdingMode='fixed'.")] = None
    taxExempt: Optional[bool] = None
    isPassiveIncome: Optional[bool] = None
    routeToAccounts: Annotated[Optional[list[str]], Field(description="plan.accounts event ids to send this income to.")] = None
    extra: Annotated[dict[str, Any], Field(description="Any other type-specific fields (hoursPerWeek, goPartTime, hasPension, jurisdictions, primaryInsuranceAmount, repeat...).")] = Field(default_factory=dict)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    _PASSTHROUGH = ("frequency", "start", "end", "yearlyChange", "isPassiveIncome", "routeToAccounts")
    _TAXED = ("taxCharacter", "withholdingMode", "withholdingRate", "taxExempt")

    def to_income(self) -> BaseIncome:
        model = INCOME_MODELS[self.type]
        kwargs: dict[str, Any] = {"id": self.id, "name": self.name, "amount": self.amount, "owner": self.owner}
        for f in self._PASSTHROUGH:
            if getattr(self, f) is not None:
                kwargs[f] = getattr(self, f)
        for f in self._TAXED:
            v = getattr(self, f)
            if v is not None and f in model.model_fields:
                kwargs[f] = v
        kwargs.update(self.extra)
        return model(**kwargs)


class NewSalary(NewIncome):
    type: Literal["salary"] = "salary"

    def to_salary(self) -> Salary:
        return self.to_income()  # type: ignore[return-value]


class NewHourlyWage(NewIncome):
    type: Literal["hourly"] = "hourly"
    amount: Annotated[float, Field(description="Hourly rate in today's dollars.")]
    hoursPerWeek: float = 40

    def to_hourly_wage(self) -> HourlyWage:
        self.extra.setdefault("hoursPerWeek", self.hoursPerWeek)
        return self.to_income()  # type: ignore[return-value]


class NewRsuGrant(NewIncome):
    type: Literal["rsu"] = "rsu"

    def to_rsu_grant(self) -> RsuGrant:
        return self.to_income()  # type: ignore[return-value]


class NewCustomIncome(NewIncome):
    type: Literal["other"] = "other"

    def to_custom_income(self) -> CustomIncome:
        return self.to_income()  # type: ignore[return-value]
