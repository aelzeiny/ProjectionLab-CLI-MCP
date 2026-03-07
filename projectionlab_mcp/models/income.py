from __future__ import annotations
import uuid
from typing import Annotated, Literal, Optional
from pydantic import BaseModel, Field


class IncomeTimeRef(BaseModel):
    """A point in time used for income start/end/part-time/pension dates.

    type="keyword":
      value: "beforeCurrentYear" | "now" | "retirement" | "endOfPlan" | "never"
    type="age":
      value: numeric string e.g. "65"
    type="milestone":
      value: milestone ID string e.g. "retirement", "fi", or a custom milestone UUID

    modifier (optional):
      "exclude" — exclusive boundary (e.g. end *before* retirement)
      "include" — inclusive boundary (e.g. end *at* retirement)
    """
    type: Literal["keyword", "age", "milestone"]
    value: str
    modifier: Optional[Literal["include", "exclude"]] = None


class IncomeYearlyChange(BaseModel):
    """How the income amount changes year-over-year.

    type values:
      "none"                  — no change (stays flat in nominal terms)
      "increase"              — increases by `amount` % per year; optional `limitEnabled`/`limit`
      "decrease"              — decreases by `amount` % per year; optional `limitEnabled`/`limit`
      "match-inflation"       — tracks inflation (constant in Today's Currency)
      "match-inflation-plus"  — inflation + `amount` % extra per year
      "match-inflation-minus" — inflation - `amount` % per year
      "advanced"              — custom multi-point schedule (UI-only; stored as opaque data)

    limitType: "today$" | "actual$"  — currency unit for the cap value
    limitEnabled: when True, growth is capped at `limit`
    """
    type: Literal[
        "none", "increase", "decrease",
        "match-inflation", "match-inflation-plus", "match-inflation-minus",
        "advanced"
    ] = "match-inflation"
    amount: float = Field(default=0, description="% per year change (used by increase/decrease/match-inflation-plus/minus).")
    amountType: str = "today$"
    limit: float = Field(default=0, description="Cap on total amount (used when limitEnabled=True).")
    limitType: Literal["today$", "actual$"] = "today$"
    limitEnabled: bool = False


class Salary(BaseModel):
    """A salary income event as stored in plan.income.events.

    All fields are present — use model_dump(exclude_none=True) when writing back
    if you want to strip None values, but it is safer to round-trip the full object.
    """
    model_config = {"extra": "allow"}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    planPath: Literal["income"] = "income"
    type: Literal["salary"] = "salary"

    # Display
    name: str = Field(description="Internal name (also used as display label).")
    title: str = Field(description="Display title shown in UI (usually same as name).")
    icon: str = Field(default="mdi-office-building", description="Material Design icon name.")
    owner: Literal["me", "spouse"] = Field(default="me", description='Who earns this income: "me" or "spouse".')

    # Amount
    amount: float = Field(description="Annual income amount.")
    amountType: Literal["today$", "actual$"] = Field(default="today$", description='"today$" = entered in Today\'s Currency (inflation-adjusted); "actual$" = nominal future dollars.')
    frequency: Literal["yearly", "monthly", "weekly", "bi-weekly"] = Field(default="yearly", description="How often the amount is paid. The app normalises to an annual figure.")
    frequencyChoices: bool = Field(default=True, description="When True, the UI allows changing the payment frequency.")

    # Time range
    start: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="keyword", value="beforeCurrentYear"),
        description="When this income begins.",
    )
    end: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement"),
        description="When this income ends.",
    )

    # Change over time
    yearlyChange: IncomeYearlyChange = Field(default_factory=IncomeYearlyChange, description="How the income amount changes year-over-year.")

    # Tax handling
    taxExempt: bool = Field(default=False, description="If True, this income is fully exempt from income tax.")
    taxWithholding: bool = Field(default=True, description="If True, a portion is withheld each period and returned as a refund if over-withheld.")
    withhold: float = Field(default=25, description="% of income to withhold for taxes (only applies when taxWithholding=True).")

    # Advanced tax flags (visible under Advanced Options)
    selfEmployment: bool = Field(default=False, description="Counts as self-employment income (subject to SE tax).")
    wage: bool = Field(default=False, description="Counts as wage income. Mutually exclusive with selfEmployment.")
    isDividendIncome: bool = Field(default=False, description="Treat as dividend income.")
    isPassiveIncome: bool = Field(default=False, description="Counts as passive income.")

    # Send To (Advanced Options)
    preventOverflow: bool = Field(default=False, description="If True, income is directed to a specific account instead of normal cash flow.")

    # Recurrence
    repeat: bool = Field(default=False, description="Enable recurrence (repeating schedule).")

    # Part-time (More Options → Switch to part-time)
    goPartTime: bool = Field(default=False, description="If True, income drops to partTimeRate% for the period between partTimeStart and partTimeEnd.")
    partTimeStart: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="keyword", value="now"),
        description="When the part-time period begins.",
    )
    partTimeEnd: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement"),
        description="When the part-time period ends.",
    )
    partTimeRate: float = Field(default=50, description="Part-time income as % of full salary.")

    # Defined Benefit Pension (More Options → Has Defined Benefit Pension)
    hasPension: bool = Field(default=False, description="If True, a defined-benefit pension is attached to this income.")
    pensionContribution: float = Field(default=0, description="Contribution amount or rate (% or $) per year while working.")
    pensionContributionType: Literal["%", "$"] = Field(default="%", description='Whether pensionContribution is a percentage of salary ("%") or a fixed dollar amount ("$").')
    contribsReduceTaxableIncome: bool = Field(default=True, description="If True, pension contributions reduce taxable income in the year they are made.")
    pensionPayoutsStart: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement"),
        description="When pension payouts begin.",
    )
    pensionPayoutsEnd: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="keyword", value="endOfPlan"),
        description="When pension payouts end.",
    )
    pensionPayoutType: Literal["fap", "cap", "fixed"] = Field(
        default="fap",
        description='"fap" = % of Final Average Pay, "cap" = % of Career Average Pay, "fixed" = fixed annual amount in Today\'s Currency.'
    )
    pensionPayoutRate: float = Field(default=25, description="Payout as % of average pay (used for fap/cap types).")
    pensionPayoutAmount: float = Field(default=0, description="Fixed annual payout amount in Today's Currency (used for 'fixed' type).")
    pensionPayoutsAreTaxFree: bool = Field(default=False, description="If True, pension payouts are treated as tax-free income.")


class HourlyWage(BaseModel):
    """An hourly wage income event as stored in plan.income.events.

    Like Salary but amount is the hourly rate and hoursPerWeek controls total hours.
    The app computes annual income as: amount * hoursPerWeek * 52.

    Key differences from Salary:
      - type = "hourly"
      - amount = hourly rate (not annual)
      - hoursPerWeek = hours worked per week (default 40)
      - frequencyChoices = False (not user-configurable)
      - icon = "mdi-briefcase-clock"
      - default withhold = 20 (vs 25 for salary)
      - default end has modifier="exclude"
    """
    model_config = {"extra": "allow"}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    planPath: Literal["income"] = "income"
    type: Literal["hourly"] = "hourly"

    # Display
    name: str = Field(description="Internal name (also used as display label).")
    title: str = Field(description="Display title shown in UI (usually same as name).")
    icon: str = Field(default="mdi-briefcase-clock", description="Material Design icon name.")
    owner: Literal["me", "spouse"] = Field(default="me", description='Who earns this income: "me" or "spouse".')

    # Amount — hourly rate; app computes yearly = amount * hoursPerWeek * 52
    amount: float = Field(description="Hourly rate.")
    amountType: Literal["today$", "actual$"] = Field(default="today$", description='"today$" = entered in Today\'s Currency (inflation-adjusted); "actual$" = nominal future dollars.')
    hoursPerWeek: float = Field(default=40, description="Hours worked per week. Annual income = amount × hoursPerWeek × 52.")
    frequency: Literal["yearly"] = Field(default="yearly", description="Always 'yearly' for hourly wage (the app normalises internally); not user-configurable.")
    frequencyChoices: bool = Field(default=False, description="Always False for hourly wage — frequency is driven by hoursPerWeek, not a UI choice.")

    # Time range
    start: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="keyword", value="beforeCurrentYear"),
        description="When this income begins.",
    )
    end: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement", modifier="exclude"),
        description='When this income ends. Defaults to retirement (exclusive — ends the year before retirement).',
    )

    # Change over time
    yearlyChange: IncomeYearlyChange = Field(default_factory=IncomeYearlyChange, description="How the hourly rate changes year-over-year.")

    # Tax handling
    taxExempt: bool = Field(default=False, description="If True, this income is fully exempt from income tax.")
    taxWithholding: bool = Field(default=True, description="If True, a portion is withheld each period and returned as a refund if over-withheld.")
    withhold: float = Field(default=20, description="% of income to withhold for taxes (only applies when taxWithholding=True). Default is 20 for hourly (vs 25 for salary).")

    # Advanced tax flags
    selfEmployment: bool = Field(default=False, description="Counts as self-employment income (subject to SE tax).")
    wage: bool = Field(default=False, description="Counts as wage income. Mutually exclusive with selfEmployment.")
    isDividendIncome: bool = Field(default=False, description="Treat as dividend income.")
    isPassiveIncome: bool = Field(default=False, description="Counts as passive income.")

    # Send To
    routeToAccounts: Optional[str] = Field(default=None, description="Account ID to route income to. Null means automatic cash flow.")
    preventOverflow: bool = Field(default=False, description="If True, income is directed to a specific account instead of normal cash flow.")

    # Recurrence
    repeat: bool = Field(default=False, description="Enable recurrence (repeating schedule).")

    # Part-time
    goPartTime: bool = Field(default=False, description="If True, income drops to partTimeRate% for the period between partTimeStart and partTimeEnd.")
    partTimeStart: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="keyword", value="now"),
        description="When the part-time period begins.",
    )
    partTimeEnd: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement"),
        description="When the part-time period ends.",
    )
    partTimeRate: float = Field(default=50, description="Part-time income as % of full hourly wage.")

    # Defined Benefit Pension
    hasPension: bool = Field(default=False, description="If True, a defined-benefit pension is attached to this income.")
    pensionContribution: float = Field(default=0, description="Contribution amount or rate (% or $) per year while working.")
    pensionContributionType: Literal["%", "$"] = Field(default="%", description='Whether pensionContribution is a percentage of income ("%") or a fixed dollar amount ("$").')
    contribsReduceTaxableIncome: bool = Field(default=True, description="If True, pension contributions reduce taxable income in the year they are made.")
    pensionPayoutsStart: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement"),
        description="When pension payouts begin.",
    )
    pensionPayoutsEnd: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="keyword", value="endOfPlan"),
        description="When pension payouts end.",
    )
    pensionPayoutType: Literal["fap", "cap", "fixed"] = Field(
        default="fap",
        description='"fap" = % of Final Average Pay, "cap" = % of Career Average Pay, "fixed" = fixed annual amount in Today\'s Currency.'
    )
    pensionPayoutRate: float = Field(default=25, description="Payout as % of average pay (used for fap/cap types).")
    pensionPayoutAmount: float = Field(default=0, description="Fixed annual payout amount in Today's Currency (used for 'fixed' type).")
    pensionPayoutsAreTaxFree: bool = Field(default=False, description="If True, pension payouts are treated as tax-free income.")


class NewHourlyWage(BaseModel):
    """Input model for creating a new HourlyWage income event.

    Only the most important fields are required; the rest have sensible defaults.
    """
    name: Annotated[str, Field(description="Display name for this income event.")]
    amount: Annotated[float, Field(description="Hourly rate (in today's dollars by default).")]
    owner: Annotated[Literal["me", "spouse"], Field(description='Who earns this income: "me" or "spouse".')] = "me"
    hoursPerWeek: Annotated[float, Field(description="Hours worked per week. Annual income = rate × hours × 52.")] = 40

    start: Annotated[IncomeTimeRef, Field(
        description='When this income begins. Default: already active ("beforeCurrentYear").'
    )] = Field(default_factory=lambda: IncomeTimeRef(type="keyword", value="beforeCurrentYear"))

    end: Annotated[IncomeTimeRef, Field(
        description='When this income ends. Default: at retirement (exclusive — ends the year before).'
    )] = Field(default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement", modifier="exclude"))

    yearlyChange: Annotated[IncomeYearlyChange, Field(
        description="How the hourly rate changes over time. Default: match inflation."
    )] = Field(default_factory=IncomeYearlyChange)

    taxExempt: Annotated[bool, Field(description="If True, this income is fully exempt from income tax.")] = False
    taxWithholding: Annotated[bool, Field(description="If True, withhold a portion each period for taxes.")] = True
    withhold: Annotated[float, Field(description="% to withhold for taxes (if taxWithholding=True). Default 20 for hourly.")] = 20

    selfEmployment: Annotated[bool, Field(description="Counts as self-employment income (subject to SE tax).")] = False
    wage: Annotated[bool, Field(description="Counts as wage income. Mutually exclusive with selfEmployment.")] = False
    isDividendIncome: Annotated[bool, Field(description="Treat as dividend income.")] = False
    isPassiveIncome: Annotated[bool, Field(description="Counts as passive income.")] = False

    goPartTime: Annotated[bool, Field(description="If True, income drops to partTimeRate% between partTimeStart and partTimeEnd.")] = False
    partTimeStart: Annotated[IncomeTimeRef, Field(description="When the part-time period begins.")] = Field(default_factory=lambda: IncomeTimeRef(type="keyword", value="now"))
    partTimeEnd: Annotated[IncomeTimeRef, Field(description="When the part-time period ends.")] = Field(default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement"))
    partTimeRate: Annotated[float, Field(description="Part-time income as % of full hourly wage.")] = 50

    hasPension: Annotated[bool, Field(description="If True, a defined-benefit pension is attached to this income.")] = False
    pensionContribution: Annotated[float, Field(description="Contribution amount or rate per year while working.")] = 0
    pensionContributionType: Annotated[Literal["%", "$"], Field(description='Whether pensionContribution is a percentage ("%") or fixed dollar amount ("$").')] = "%"
    contribsReduceTaxableIncome: Annotated[bool, Field(description="If True, contributions reduce taxable income.")] = True
    pensionPayoutsStart: Annotated[IncomeTimeRef, Field(description="When pension payouts begin.")] = Field(default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement"))
    pensionPayoutsEnd: Annotated[IncomeTimeRef, Field(description="When pension payouts end.")] = Field(default_factory=lambda: IncomeTimeRef(type="keyword", value="endOfPlan"))
    pensionPayoutType: Annotated[Literal["fap", "cap", "fixed"], Field(description='"fap" = % of Final Average Pay, "cap" = % of Career Average Pay, "fixed" = fixed annual amount.')] = "fap"
    pensionPayoutRate: Annotated[float, Field(description="Payout as % of average pay (fap/cap types).")] = 25
    pensionPayoutAmount: Annotated[float, Field(description="Fixed annual payout in Today's Currency ('fixed' type).")] = 0
    pensionPayoutsAreTaxFree: Annotated[bool, Field(description="If True, pension payouts are tax-free.")] = False

    def to_hourly_wage(self) -> HourlyWage:
        """Convert to a full HourlyWage object with all required fields filled in."""
        data = self.model_dump(exclude_none=True)
        data.setdefault("title", data["name"])
        return HourlyWage.model_validate(data)


class RsuGrant(BaseModel):
    """An RSU (Restricted Stock Unit) grant income event as stored in plan.income.events.

    RSU grants are lump-sum or periodic income events representing stock vesting.
    Key differences from Salary/HourlyWage:
      - type = "rsu"
      - icon = "mdi-finance"
      - title defaults to "RSU Grant" (not the display name)
      - withhold default = 30 (vs 20/25 for salary/hourly)
      - yearlyChange defaults to type="none" (not "match-inflation")
      - start.modifier = "include" for keyword refs
      - frequency includes "once" option (one-time grant)
      - No hoursPerWeek, goPartTime, hasPension fields
      - Recurrence via repeat/repeatInterval/repeatScaler/repeatEnd
    """
    model_config = {"extra": "allow"}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    planPath: Literal["income"] = "income"
    type: Literal["rsu"] = "rsu"

    # Display
    name: str = Field(description="Internal name shown in the plan income list.")
    title: str = Field(default="RSU Grant", description='Display title. Defaults to "RSU Grant" (not the name).')
    icon: str = Field(default="mdi-finance", description="Material Design icon name.")
    owner: Literal["me", "spouse"] = Field(default="me", description='Who receives this grant: "me" or "spouse".')

    # Amount
    amount: float = Field(description="Vested amount (lump sum or per-period).")
    amountType: Literal["today$", "actual$"] = Field(default="today$", description='"today$" = Today\'s Currency (inflation-adjusted); "actual$" = nominal future dollars.')

    # Frequency
    frequency: Literal["once", "yearly", "once-per-year", "quarterly", "monthly", "bi-weekly", "weekly", "daily"] = Field(
        default="once",
        description='"once" = single one-time grant. Other values repeat over a time range.',
    )
    frequencyChoices: bool = Field(default=True, description="Always True for RSU grants — frequency is user-configurable.")

    # Time range
    start: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="keyword", value="now", modifier="include"),
        description="When this grant vests / begins. Defaults to now (inclusive).",
    )
    end: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement", modifier="exclude"),
        description="When this grant ends (for recurring frequencies).",
    )

    # Change over time
    yearlyChange: IncomeYearlyChange = Field(
        default_factory=lambda: IncomeYearlyChange(type="none"),
        description='How the amount changes year-over-year. Defaults to "none" (flat in nominal terms).',
    )

    # Tax handling
    taxExempt: bool = Field(default=False, description="If True, this income is fully exempt from income tax.")
    taxWithholding: bool = Field(default=True, description="If True, a portion is withheld and returned as refund if over-withheld.")
    withhold: float = Field(default=30, description="% of grant to withhold for taxes (only when taxWithholding=True). Default 30 for RSU.")

    # Advanced tax flags (absent by default; present only when user enables them)
    selfEmployment: Optional[bool] = Field(default=None, description="Counts as self-employment income (subject to SE tax).")
    wage: Optional[bool] = Field(default=None, description="Counts as wage income. Mutually exclusive with selfEmployment.")
    isDividendIncome: Optional[bool] = Field(default=None, description="Treat as dividend income.")
    isPassiveIncome: Optional[bool] = Field(default=None, description="Counts as passive income.")

    # Send To
    preventOverflow: Optional[bool] = Field(default=None, description="If True, income routes to a specific account instead of normal cash flow.")
    routeToAccounts: Optional[str] = Field(default=None, description="Account ID to route grant proceeds to. Null = automatic cash flow.")

    # Recurrence (when repeat=True)
    repeat: bool = Field(default=False, description="Enable recurrence — grant repeats on a schedule.")
    repeatIntervalType: Optional[Literal["between"]] = Field(default=None, description='Always "between" when repeat=True.')
    repeatInterval: Optional[int] = Field(default=None, description="Number of years between each repeated grant.")
    repeatScaler: Optional[float] = Field(default=None, description="% to scale the amount up (positive) or down (negative) each repetition.")
    repeatEnd: Optional[IncomeTimeRef] = Field(default=None, description="When the recurrence stops. Defaults to End of Plan.")


class NewRsuGrant(BaseModel):
    """Input model for creating a new RSU Grant income event.

    Only name and amount are required; all other fields have sensible defaults
    matching what the ProjectionLab UI creates.
    """
    name: Annotated[str, Field(description="Display name for this grant.")]
    amount: Annotated[float, Field(description="Vested amount (in today's dollars by default).")]
    owner: Annotated[Literal["me", "spouse"], Field(description='Who receives this grant: "me" or "spouse".')] = "me"

    frequency: Annotated[
        Literal["once", "yearly", "once-per-year", "quarterly", "monthly", "bi-weekly", "weekly", "daily"],
        Field(description='"once" = one-time grant (default). Other values repeat over the start→end range.'),
    ] = "once"

    start: Annotated[IncomeTimeRef, Field(
        description="When the grant vests / income begins. Default: now (inclusive)."
    )] = Field(default_factory=lambda: IncomeTimeRef(type="keyword", value="now", modifier="include"))

    end: Annotated[IncomeTimeRef, Field(
        description="When the grant ends (for recurring frequencies). Default: retirement (exclusive)."
    )] = Field(default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement", modifier="exclude"))

    amountType: Annotated[Literal["today$", "actual$"], Field(
        description='"today$" = entered in Today\'s Currency; "actual$" = nominal future dollars.'
    )] = "today$"

    yearlyChange: Annotated[IncomeYearlyChange, Field(
        description='How the amount changes over time. Default: none (flat in nominal terms).'
    )] = Field(default_factory=lambda: IncomeYearlyChange(type="none"))

    taxExempt: Annotated[bool, Field(description="If True, fully exempt from income tax.")] = False
    taxWithholding: Annotated[bool, Field(description="If True, withhold a portion for taxes.")] = True
    withhold: Annotated[float, Field(description="% to withhold for taxes (if taxWithholding=True). Default 30 for RSU.")] = 30

    selfEmployment: Annotated[Optional[bool], Field(description="Counts as self-employment income.")] = None
    wage: Annotated[Optional[bool], Field(description="Counts as wage income.")] = None
    isDividendIncome: Annotated[Optional[bool], Field(description="Treat as dividend income.")] = None
    isPassiveIncome: Annotated[Optional[bool], Field(description="Counts as passive income.")] = None

    repeat: Annotated[bool, Field(description="Enable recurrence.")] = False
    repeatInterval: Annotated[Optional[int], Field(description="Years between each repeated grant (when repeat=True).")] = None
    repeatScaler: Annotated[Optional[float], Field(description="% to scale amount each repetition (when repeat=True).")] = None
    repeatEnd: Annotated[Optional[IncomeTimeRef], Field(description="When recurrence stops (when repeat=True). Default: End of Plan.")] = None

    def to_rsu_grant(self) -> RsuGrant:
        """Convert to a full RsuGrant object with all required fields filled in."""
        data = self.model_dump(exclude_none=True)
        data.setdefault("title", "RSU Grant")
        if data.get("repeat") and data.get("repeatInterval") is not None:
            data["repeatIntervalType"] = "between"
        if data.get("repeat") and "repeatEnd" not in data:
            data["repeatEnd"] = IncomeTimeRef(type="keyword", value="endOfPlan", modifier="include").model_dump()
        return RsuGrant.model_validate(data)


class NewSalary(BaseModel):
    """Input model for creating a new Salary income event.

    Only the most important fields are required; the rest have sensible defaults.
    Use Salary.model_validate(new_salary.model_dump(exclude_none=True)) to build
    the full object, or pass directly to income CRUD helpers.
    """
    name: Annotated[str, Field(description="Display name for this income event.")]
    amount: Annotated[float, Field(description="Annual income amount (in today's dollars by default).")]
    owner: Annotated[Literal["me", "spouse"], Field(description='Who earns this income: "me" or "spouse".')] = "me"

    start: Annotated[IncomeTimeRef, Field(
        description='When this income begins. Default: already active ("beforeCurrentYear").'
    )] = Field(default_factory=lambda: IncomeTimeRef(type="keyword", value="beforeCurrentYear"))

    end: Annotated[IncomeTimeRef, Field(
        description='When this income ends. Default: at retirement milestone.'
    )] = Field(default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement"))

    yearlyChange: Annotated[IncomeYearlyChange, Field(
        description="How income changes over time. Default: match inflation."
    )] = Field(default_factory=IncomeYearlyChange)

    taxExempt: Annotated[bool, Field(description="If True, this income is fully exempt from income tax.")] = False
    taxWithholding: Annotated[bool, Field(description="If True, withhold a portion each period for taxes.")] = True
    withhold: Annotated[float, Field(description="% to withhold for taxes (if taxWithholding=True). Default 25 for salary.")] = 25

    selfEmployment: Annotated[bool, Field(description="Counts as self-employment income (subject to SE tax).")] = False
    wage: Annotated[bool, Field(description="Counts as wage income. Mutually exclusive with selfEmployment.")] = False
    isDividendIncome: Annotated[bool, Field(description="Treat as dividend income.")] = False
    isPassiveIncome: Annotated[bool, Field(description="Counts as passive income.")] = False

    goPartTime: Annotated[bool, Field(description="If True, income drops to partTimeRate% between partTimeStart and partTimeEnd.")] = False
    partTimeStart: Annotated[IncomeTimeRef, Field(description="When the part-time period begins.")] = Field(default_factory=lambda: IncomeTimeRef(type="keyword", value="now"))
    partTimeEnd: Annotated[IncomeTimeRef, Field(description="When the part-time period ends.")] = Field(default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement"))
    partTimeRate: Annotated[float, Field(description="Part-time income as % of full salary.")] = 50

    hasPension: Annotated[bool, Field(description="If True, a defined-benefit pension is attached to this income.")] = False
    pensionContribution: Annotated[float, Field(description="Contribution amount or rate per year while working.")] = 0
    pensionContributionType: Annotated[Literal["%", "$"], Field(description='Whether pensionContribution is a percentage ("%") or fixed dollar amount ("$").')] = "%"
    contribsReduceTaxableIncome: Annotated[bool, Field(description="If True, contributions reduce taxable income.")] = True
    pensionPayoutsStart: Annotated[IncomeTimeRef, Field(description="When pension payouts begin.")] = Field(default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement"))
    pensionPayoutsEnd: Annotated[IncomeTimeRef, Field(description="When pension payouts end.")] = Field(default_factory=lambda: IncomeTimeRef(type="keyword", value="endOfPlan"))
    pensionPayoutType: Annotated[Literal["fap", "cap", "fixed"], Field(description='"fap" = % of Final Average Pay, "cap" = % of Career Average Pay, "fixed" = fixed annual amount.')] = "fap"
    pensionPayoutRate: Annotated[float, Field(description="Payout as % of average pay (fap/cap types).")] = 25
    pensionPayoutAmount: Annotated[float, Field(description="Fixed annual payout in Today's Currency ('fixed' type).")] = 0
    pensionPayoutsAreTaxFree: Annotated[bool, Field(description="If True, pension payouts are tax-free.")] = False

    def to_salary(self) -> Salary:
        """Convert to a full Salary object with all required fields filled in."""
        data = self.model_dump(exclude_none=True)
        data.setdefault("title", data["name"])
        return Salary.model_validate(data)


class CustomIncome(BaseModel):
    """A custom income event as stored in plan.income.events.

    The ProjectionLab UI calls this "Custom Income" but the stored type is "other".

    Key differences from Salary/HourlyWage/RsuGrant:
      - type = "other" (not "custom" — important!)
      - icon = "mdi-currency-usd-circle"
      - taxWithholding = False by default (all other income types default to True)
      - withhold default = 20 (same as hourly; vs 25 salary, 30 RSU)
      - No hoursPerWeek, goPartTime, hasPension / pension* fields
      - No repeatIntervalType/repeatInterval/repeatScaler/repeatEnd (but repeat flag is present)
      - end default has no modifier (unlike hourly which uses modifier="exclude")
      - selfEmployment/wage/isDividendIncome/isPassiveIncome are plain bool (not Optional)
        because the app always stores them explicitly
    """
    model_config = {"extra": "allow"}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    planPath: Literal["income"] = "income"
    type: Literal["other"] = "other"

    # Display
    name: str = Field(description="Internal name shown in the plan income list.")
    title: str = Field(default="Custom Income", description='Display title. Defaults to "Custom Income".')
    icon: str = Field(default="mdi-currency-usd-circle", description="Material Design icon name.")
    owner: Literal["me", "spouse"] = Field(default="me", description='Who earns this income: "me" or "spouse".')

    # Amount
    amount: float = Field(description="Income amount per period.")
    amountType: Literal["today$", "actual$"] = Field(
        default="today$",
        description='"today$" = Today\'s Currency (inflation-adjusted); "actual$" = nominal future dollars.',
    )

    # Frequency
    frequency: Literal["once", "yearly", "quarterly", "monthly", "bi-weekly", "weekly", "daily"] = Field(
        default="yearly",
        description="How often the income is received. Defaults to yearly.",
    )
    frequencyChoices: bool = Field(default=True, description="Always True for custom income — frequency is user-configurable.")

    # Time range
    start: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="keyword", value="beforeCurrentYear"),
        description="When this income begins. Defaults to already active (before current year).",
    )
    end: IncomeTimeRef = Field(
        default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement"),
        description="When this income ends. Defaults to retirement (no modifier — inclusive boundary).",
    )

    # Change over time
    yearlyChange: IncomeYearlyChange = Field(
        default_factory=IncomeYearlyChange,
        description='How the amount changes year-over-year. Defaults to "match-inflation".',
    )

    # Tax handling — NOTE: taxWithholding defaults to False (unlike all other income types)
    taxExempt: bool = Field(default=False, description="If True, this income is fully exempt from income tax.")
    taxWithholding: bool = Field(
        default=False,
        description="If True, withhold a portion each period and return as refund if over-withheld. "
                    "Defaults to False for custom income (unlike salary/hourly/RSU which default to True).",
    )
    withhold: float = Field(default=20, description="% to withhold for taxes (only when taxWithholding=True). Default 20.")

    # Advanced tax flags — always stored explicitly (not Optional like RSU)
    selfEmployment: bool = Field(default=False, description="Counts as self-employment income (subject to SE tax).")
    wage: bool = Field(default=False, description="Counts as wage income. Mutually exclusive with selfEmployment.")
    isDividendIncome: bool = Field(default=False, description="Treat as dividend income.")
    isPassiveIncome: bool = Field(default=False, description="Counts as passive income.")

    # Send To
    routeToAccounts: Optional[str] = Field(default=None, description="Account ID to route income to. Null = automatic cash flow.")
    preventOverflow: bool = Field(default=False, description="If True, income routes to a specific account instead of normal cash flow.")

    # Recurrence
    repeat: bool = Field(default=False, description="Enable recurrence — income repeats on a schedule.")
    repeatIntervalType: Optional[Literal["between"]] = Field(default=None, description='Always "between" when repeat=True.')
    repeatInterval: Optional[int] = Field(default=None, description="Number of years between each repeated event.")
    repeatScaler: Optional[float] = Field(default=None, description="% to scale the amount each repetition.")
    repeatEnd: Optional[IncomeTimeRef] = Field(default=None, description="When recurrence stops.")


class NewCustomIncome(BaseModel):
    """Input model for creating a new Custom Income event.

    Only name and amount are required; all other fields have sensible defaults
    matching what the ProjectionLab UI creates for a new "Custom Income".

    Note: the stored type is "other" (not "custom") — this is how ProjectionLab
    identifies custom income internally.
    """
    name: Annotated[str, Field(description="Display name for this income event.")]
    amount: Annotated[float, Field(description="Income amount per period (in today's dollars by default).")]
    owner: Annotated[Literal["me", "spouse"], Field(description='Who earns this income: "me" or "spouse".')] = "me"

    frequency: Annotated[
        Literal["once", "yearly", "quarterly", "monthly", "bi-weekly", "weekly", "daily"],
        Field(description="How often the income is received. Defaults to yearly."),
    ] = "yearly"

    start: Annotated[IncomeTimeRef, Field(
        description='When this income begins. Default: already active ("beforeCurrentYear").'
    )] = Field(default_factory=lambda: IncomeTimeRef(type="keyword", value="beforeCurrentYear"))

    end: Annotated[IncomeTimeRef, Field(
        description="When this income ends. Default: at retirement (no modifier — inclusive)."
    )] = Field(default_factory=lambda: IncomeTimeRef(type="milestone", value="retirement"))

    amountType: Annotated[Literal["today$", "actual$"], Field(
        description='"today$" = entered in Today\'s Currency; "actual$" = nominal future dollars.'
    )] = "today$"

    yearlyChange: Annotated[IncomeYearlyChange, Field(
        description="How the amount changes over time. Default: match inflation."
    )] = Field(default_factory=IncomeYearlyChange)

    taxExempt: Annotated[bool, Field(description="If True, fully exempt from income tax.")] = False
    taxWithholding: Annotated[bool, Field(
        description="If True, withhold a portion for taxes. Defaults to False for custom income."
    )] = False
    withhold: Annotated[float, Field(description="% to withhold for taxes (if taxWithholding=True). Default 20.")] = 20

    selfEmployment: Annotated[bool, Field(description="Counts as self-employment income (subject to SE tax).")] = False
    wage: Annotated[bool, Field(description="Counts as wage income. Mutually exclusive with selfEmployment.")] = False
    isDividendIncome: Annotated[bool, Field(description="Treat as dividend income.")] = False
    isPassiveIncome: Annotated[bool, Field(description="Counts as passive income.")] = False

    repeat: Annotated[bool, Field(description="Enable recurrence.")] = False
    repeatInterval: Annotated[Optional[int], Field(description="Years between each repeated event (when repeat=True).")] = None
    repeatScaler: Annotated[Optional[float], Field(description="% to scale amount each repetition (when repeat=True).")] = None
    repeatEnd: Annotated[Optional[IncomeTimeRef], Field(description="When recurrence stops (when repeat=True).")] = None

    def to_custom_income(self) -> CustomIncome:
        """Convert to a full CustomIncome object with all required fields filled in."""
        data = self.model_dump(exclude_none=True)
        data.setdefault("title", "Custom Income")
        if data.get("repeat") and data.get("repeatInterval") is not None:
            data["repeatIntervalType"] = "between"
        if data.get("repeat") and "repeatEnd" not in data:
            data["repeatEnd"] = IncomeTimeRef(type="keyword", value="endOfPlan", modifier="include").model_dump()
        return CustomIncome.model_validate(data)
