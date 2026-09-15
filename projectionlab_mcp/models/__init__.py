from __future__ import annotations
from typing import Annotated, Any
from pydantic import BaseModel, Field

from .common import (
    TimeRef,
    WithdrawAge,
    DateRef,
    DisplayAge,
    AccountUpdate,
    Location,
)
from .savings import SavingsAccount, NewSavingsAccount
from .investments import (
    InvestmentAccountType,
    BaseInvestmentAccount,
    TaxableInvestmentAccount,
    CryptoInvestmentAccount,
    HSAInvestmentAccount,
    Plan529InvestmentAccount,
    IRAInvestmentAccount,
    InheritedIRAInvestmentAccount,
    RothIRAInvestmentAccount,
    InheritedRothIRAInvestmentAccount,
    InvestmentAccount,
)
from .real_assets import (
    YearlyChange,
    BaseAsset,
    RealEstateAsset, RentalPropertyAsset, BuildingAsset, CommercialPropertyAsset,
    BaseVehicleAsset, CarAsset, MotorcycleAsset, BoatAsset,
    LandAsset,
    JewelryAsset, PreciousMetalsAsset, FurnitureAsset, InstrumentAsset, MachineryAsset,
    CustomAsset,
    RealAsset,
)
from .unsecured_debts import ForgiveRef, AdditionalFields, BaseDebt, GenericDebt, StudentLoansDebt, UnsecuredDebt
from .priorities import (
    PriorityTimeRef,
    Priority,
    NewCashPriority,
    NewInvestmentPriority,
    NewAssetLoanPriority,
    NewDebtPriority,
    NewTransferPriority,
    Priorities,
)
from .income import (
    IncomeTimeRef,
    IncomeYearlyChange,
    BaseIncome,
    TaxedIncome,
    Salary,
    HourlyWage,
    RsuGrant,
    SideHustle,
    CustomIncome,
    Inheritance,
    TaxCredit,
    TaxDeduction,
    PensionIncome,
    SocialSecurity,
    Income,
    INCOME_MODELS,
    IncomeType,
    NewIncome,
    NewSalary,
    NewHourlyWage,
    NewRsuGrant,
    NewCustomIncome,
)
from .expenses import (
    ExpenseYearlyChange,
    BaseExpense,
    SpendingExpense,
    LivingExpense,
    RentExpense,
    DependentSupportExpense,
    EducationExpense,
    HealthCareExpense,
    MedicalExpense,
    VacationExpense,
    TravelExpense,
    WeddingExpense,
    CharityExpense,
    EmergencyExpense,
    CustomExpense,
    DebtExpense,
    MedicareExpense,
    Expense,
    EXPENSE_MODELS,
    ExpenseType,
    NewExpense,
    NewCustomExpense,
)
from .milestones import (
    DateCriterion,
    YearCriterion,
    MilestoneRefCriterion,
    MetricCriterion,
    GenericCriterion,
    MilestoneCriterion,
    Milestone,
    NewMilestone,
)


class Today(BaseModel):
    schema_version: float = Field(alias="schema")
    location: Location
    tab: int
    partnerStatus: str
    age: int
    birthYear: int
    birthMonth: int
    yourName: str
    yourColor: str
    yourIcon: str
    savingsAccounts: list[SavingsAccount]
    investmentAccounts: list[Annotated[InvestmentAccount, Field(union_mode="left_to_right")]]
    debts: list[Annotated[UnsecuredDebt, Field(union_mode="left_to_right")]]
    assets: list[Annotated[RealAsset, Field(union_mode="left_to_right")]]
    lastUpdated: int

    model_config = {"populate_by_name": True}


class Meta(BaseModel):
    version: str
    lastUpdated: int


class ProgressEntry(BaseModel):
    savings: float
    loans: float
    taxDeferred: float
    taxable: float
    crypto: float
    taxFree: float
    assets: float
    debt: float
    netWorth: float
    date: int


class Progress(BaseModel):
    data: list[ProgressEntry]
    lastUpdated: int


class PLExport(BaseModel):
    meta: Meta
    today: Today
    plans: list[Any]  # raw plan dicts; use list_milestones/get_milestone etc. for typed access
    settings: dict[str, Any]
    progress: Progress


__all__ = [
    # common
    "TimeRef",
    "WithdrawAge",
    "DateRef",
    "DisplayAge",
    "AccountUpdate",
    "Location",
    # savings
    "SavingsAccount",
    "NewSavingsAccount",
    # investments
    "InvestmentAccountType",
    "BaseInvestmentAccount",
    "TaxableInvestmentAccount",
    "CryptoInvestmentAccount",
    "HSAInvestmentAccount",
    "Plan529InvestmentAccount",
    "IRAInvestmentAccount",
    "InheritedIRAInvestmentAccount",
    "RothIRAInvestmentAccount",
    "InheritedRothIRAInvestmentAccount",
    "InvestmentAccount",
    # real assets
    "YearlyChange",
    "BaseAsset",
    "RealEstateAsset",
    "RentalPropertyAsset",
    "BuildingAsset",
    "CommercialPropertyAsset",
    "BaseVehicleAsset",
    "CarAsset",
    "MotorcycleAsset",
    "BoatAsset",
    "LandAsset",
    "JewelryAsset",
    "PreciousMetalsAsset",
    "FurnitureAsset",
    "InstrumentAsset",
    "MachineryAsset",
    "CustomAsset",
    "RealAsset",
    # unsecured debts
    "ForgiveRef",
    "AdditionalFields",
    "BaseDebt",
    "GenericDebt",
    "StudentLoansDebt",
    "UnsecuredDebt",
    # priorities
    "PriorityTimeRef",
    "Priority",
    "NewCashPriority",
    "NewInvestmentPriority",
    "NewAssetLoanPriority",
    "NewDebtPriority",
    "NewTransferPriority",
    "Priorities",
    # income
    "IncomeTimeRef",
    "IncomeYearlyChange",
    "BaseIncome",
    "TaxedIncome",
    "Salary",
    "HourlyWage",
    "RsuGrant",
    "SideHustle",
    "CustomIncome",
    "Inheritance",
    "TaxCredit",
    "TaxDeduction",
    "PensionIncome",
    "SocialSecurity",
    "Income",
    "INCOME_MODELS",
    "IncomeType",
    "NewIncome",
    "NewSalary",
    "NewHourlyWage",
    "NewRsuGrant",
    "NewCustomIncome",
    # expenses
    "ExpenseYearlyChange",
    "BaseExpense",
    "SpendingExpense",
    "LivingExpense",
    "RentExpense",
    "DependentSupportExpense",
    "EducationExpense",
    "HealthCareExpense",
    "MedicalExpense",
    "VacationExpense",
    "TravelExpense",
    "WeddingExpense",
    "CharityExpense",
    "EmergencyExpense",
    "CustomExpense",
    "DebtExpense",
    "MedicareExpense",
    "Expense",
    "EXPENSE_MODELS",
    "ExpenseType",
    "NewExpense",
    "NewCustomExpense",
    # milestones
    "DateCriterion",
    "YearCriterion",
    "MilestoneRefCriterion",
    "MetricCriterion",
    "GenericCriterion",
    "MilestoneCriterion",
    "Milestone",
    "NewMilestone",
    # top-level / export
    "Today",
    "Meta",
    "ProgressEntry",
    "Progress",
    "PLExport",
]
