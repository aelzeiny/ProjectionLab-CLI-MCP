from __future__ import annotations
import uuid
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field
from .common import TimeRef


class YearlyChange(BaseModel):
    type: Literal["appreciate", "depreciate", "fixed", "match-inflation", "none"] = Field(
        description='How the value changes each year: "appreciate", "depreciate", "fixed", or "match-inflation".'
    )
    amount: float = Field(description="Annual rate (%) or fixed dollar amount of change.")
    amountType: str = "today$"
    limit: float = 0
    limitType: str = "today$"
    limitEnabled: bool = False


class BaseAsset(BaseModel):
    """Fields common to all real asset types."""
    model_config = {"extra": "allow"}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique ID (auto-generated if omitted).")
    name: Annotated[str, Field(description="Internal name/key for the asset.")]
    title: Annotated[str, Field(description="Display title shown in ProjectionLab.")]
    owner: Annotated[Literal["me", "spouse"], Field(description='Asset owner: "me" or "spouse".')]
    planPath: str = "assets"
    color: str = Field(default="indigo-lighten-1", description="UI color for the asset card.")
    icon: str = Field(default="mdi-home", description="Material Design icon name.")
    order: int = Field(default=0, description="Display order among assets.")
    repeat: bool = Field(default=False, description="Whether this asset repeats on a schedule.")

    # Valuation
    initialValue: Annotated[float, Field(description="Original purchase price.")]
    initialValueType: str = "today$"
    amount: Annotated[float, Field(description="Current market value.")]
    amountType: str = "today$"

    # Financing
    paymentMethod: Literal["pay-in-full", "financed"] = Field(default="pay-in-full", description='"pay-in-full" for owned outright, "financed" for a loan.')
    downPayment: float = Field(default=0, description="Down payment amount.")
    downPaymentType: str = "today$"
    balance: float = Field(default=0, description="Remaining loan balance.")
    balanceType: str = "today$"
    monthlyPayment: float = Field(default=0, description="Monthly loan payment.")
    monthlyPaymentType: str = "today$"
    interestRate: float = Field(default=0, description="Annual interest rate (%).")
    interestType: Literal["simple", "compound"] = Field(default="simple", description='Interest calculation method: "simple" or "compound".')
    compounding: Literal["monthly", "daily"] = Field(default="monthly", description='Compounding frequency: "monthly" or "daily".')
    excludeLoanFromLNW: bool = Field(default=False, description="Exclude the loan balance from liquid net worth calculation.")

    # Appreciation / depreciation
    yearlyChange: YearlyChange = Field(
        default_factory=lambda: YearlyChange(type="appreciate", amount=3.9),
        description="Annual appreciation or depreciation settings."
    )

    # Tax / sale
    assessedValue: float = Field(default=0, description="Assessed value for tax purposes (0 = use market value).")
    assessedValueType: str = Field(default="market-value", description='"market-value" to track market value, or "fixed" for a static assessed value.')
    assessedValueGrowthRateLimit: float = Field(default=0, description="Cap on annual assessed value growth (%).")
    assessedValueGrowthRateLimitType: str = "auto"
    taxRate: float = Field(default=1.25, description="Annual property tax rate (% of assessed value).")
    taxRateType: str = "%"
    maintenanceRate: float = Field(default=2, description="Annual maintenance cost (% of current value).")
    maintenanceRateType: str = "%"
    insuranceRate: float = Field(default=0.5, description="Annual insurance cost (% of current value).")
    insuranceRateType: str = "%"
    brokersFee: float = Field(default=5.5, description="Broker fee charged on sale (% of sale price).")
    sellIfNeeded: bool = Field(default=False, description="Allow ProjectionLab to sell this asset if funds are needed.")

    # Timeline
    start: TimeRef = Field(
        default_factory=lambda: TimeRef(type="keyword", value="beforeCurrentYear"),
        description='When the asset is acquired. Use {"type": "keyword", "value": "beforeCurrentYear"} for already owned.'
    )
    end: TimeRef = Field(
        default_factory=lambda: TimeRef(type="keyword", value="never"),
        description='When the asset is sold. Use {"type": "keyword", "value": "never"} to hold indefinitely.'
    )


# ---------------------------------------------------------------------------
# Real estate
# ---------------------------------------------------------------------------

class RealEstateAsset(BaseAsset):
    type: Literal["real-estate"] = "real-estate"
    icon: str = "mdi-home"

    initialBuildingValue: float = Field(default=0, description="Initial value of the building only (land excluded), used for depreciation.")
    initialBuildingValueType: str = "today$"
    classification: str = Field(default="residential", description='Property classification: "residential" or "commercial".')

    # Rental income
    generateIncome: bool = Field(default=False, description="Whether this property generates rental income.")
    incomeRate: float = Field(default=8, description="Gross rental yield (% of current value per year).")
    incomeRateType: str = "%"
    isPassiveIncome: bool = Field(default=False, description="Whether rental income is classified as passive.")
    percentRented: float = Field(default=50, description="Percentage of the year the property is rented out.")
    cancelRent: bool = Field(default=True, description="Cancel any rent expense when this property is owned.")
    estimateRentalDeductions: bool = Field(default=True, description="Automatically estimate rental expense deductions.")
    estimateQBI: bool = Field(default=False, description="Estimate qualified business income (QBI) deduction for rental income.")
    managementRate: float = Field(default=0, description="Property management fee (% of rental income).")
    managementRateType: str = "%"
    selfEmployment: bool = Field(default=False, description="Treat rental income as self-employment income.")

    # Operating costs
    improvementRate: float = Field(default=0, description="Annual capital improvements (% of current value).")
    improvementRateType: str = "%"
    monthlyHOA: float = Field(default=0, description="Monthly HOA fee.")


class RentalPropertyAsset(RealEstateAsset):
    subtype: Literal["rental"]  # required — drives union discrimination
    icon: str = "mdi-home-city"
    generateIncome: bool = Field(default=True, description="Whether this property generates rental income.")
    cancelRent: bool = Field(default=False, description="Cancel any rent expense when this property is owned.")


class BuildingAsset(RealEstateAsset):
    subtype: Literal["building"]  # required — drives union discrimination
    icon: str = "mdi-home-variant"
    classification: str = "commercial"
    cancelRent: bool = Field(default=False, description="Cancel any rent expense when this property is owned.")


class CommercialPropertyAsset(RealEstateAsset):
    subtype: Literal["rental-building"]  # required — drives union discrimination
    icon: str = "mdi-city-variant"
    classification: str = "commercial"
    generateIncome: bool = Field(default=True, description="Whether this property generates rental income.")
    cancelRent: bool = Field(default=False, description="Cancel any rent expense when this property is owned.")


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------

class BaseVehicleAsset(BaseAsset):
    """Common base for depreciating vehicle assets."""
    icon: str = "mdi-car"
    brokersFee: float = Field(default=0, description="Broker fee charged on sale (% of sale price).")
    taxRate: float = Field(default=1, description="Annual property tax rate (% of assessed value).")
    maintenanceRate: float = Field(default=5, description="Annual maintenance cost (% of current value).")
    insuranceRate: float = Field(default=4, description="Annual insurance cost (% of current value).")
    yearlyChange: YearlyChange = Field(
        default_factory=lambda: YearlyChange(type="depreciate", amount=8),
        description="Annual depreciation settings."
    )


class CarAsset(BaseVehicleAsset):
    type: Literal["car"] = "car"
    icon: str = "mdi-car"


class MotorcycleAsset(BaseVehicleAsset):
    type: Literal["motorcycle"] = "motorcycle"
    icon: str = "mdi-motorbike"
    yearlyChange: YearlyChange = Field(
        default_factory=lambda: YearlyChange(type="depreciate", amount=5),
        description="Annual depreciation settings."
    )


class BoatAsset(BaseVehicleAsset):
    type: Literal["boat"] = "boat"
    icon: str = "mdi-sail-boat"
    taxRate: float = Field(default=0, description="Annual property tax rate (% of assessed value).")
    yearlyChange: YearlyChange = Field(
        default_factory=lambda: YearlyChange(type="depreciate", amount=8.5),
        description="Annual depreciation settings."
    )


# ---------------------------------------------------------------------------
# Land
# ---------------------------------------------------------------------------

class LandAsset(BaseAsset):
    type: Literal["land"] = "land"
    icon: str = "mdi-island"
    taxRate: float = Field(default=1.5, description="Annual property tax rate (% of assessed value).")
    maintenanceRate: float = Field(default=0, description="Annual maintenance cost (% of current value).")
    insuranceRate: float = Field(default=0, description="Annual insurance cost (% of current value).")
    yearlyChange: YearlyChange = Field(
        default_factory=lambda: YearlyChange(type="appreciate", amount=3.9),
        description="Annual appreciation settings."
    )


# ---------------------------------------------------------------------------
# Collectibles & personal property
# ---------------------------------------------------------------------------

class JewelryAsset(BaseAsset):
    type: Literal["jewelry"] = "jewelry"
    icon: str = "mdi-diamond-stone"
    taxRate: float = Field(default=0, description="Annual property tax rate (% of assessed value).")
    maintenanceRate: float = Field(default=0, description="Annual maintenance cost (% of current value).")
    insuranceRate: float = Field(default=4, description="Annual insurance cost (% of current value).")
    brokersFee: float = Field(default=0, description="Broker fee charged on sale (% of sale price).")
    yearlyChange: YearlyChange = Field(
        default_factory=lambda: YearlyChange(type="depreciate", amount=0.3),
        description="Annual depreciation settings."
    )


class PreciousMetalsAsset(BaseAsset):
    type: Literal["precious-metals"] = "precious-metals"
    icon: str = "mdi-gold"
    taxRate: float = Field(default=0, description="Annual property tax rate (% of assessed value).")
    maintenanceRate: float = Field(default=0, description="Annual maintenance cost (% of current value).")
    insuranceRate: float = Field(default=0, description="Annual insurance cost (% of current value).")
    brokersFee: float = Field(default=0, description="Broker fee charged on sale (% of sale price).")
    yearlyChange: YearlyChange = Field(
        default_factory=lambda: YearlyChange(type="appreciate", amount=9),
        description="Annual appreciation settings."
    )


class FurnitureAsset(BaseAsset):
    type: Literal["furniture"] = "furniture"
    icon: str = "mdi-table-furniture"
    taxRate: float = Field(default=0, description="Annual property tax rate (% of assessed value).")
    maintenanceRate: float = Field(default=0, description="Annual maintenance cost (% of current value).")
    insuranceRate: float = Field(default=4, description="Annual insurance cost (% of current value).")
    brokersFee: float = Field(default=0, description="Broker fee charged on sale (% of sale price).")
    yearlyChange: YearlyChange = Field(
        default_factory=lambda: YearlyChange(type="depreciate", amount=5),
        description="Annual depreciation settings."
    )


class InstrumentAsset(BaseAsset):
    type: Literal["instrument"] = "instrument"
    icon: str = "mdi-saxophone"
    taxRate: float = Field(default=0, description="Annual property tax rate (% of assessed value).")
    maintenanceRate: float = Field(default=0, description="Annual maintenance cost (% of current value).")
    insuranceRate: float = Field(default=5, description="Annual insurance cost (% of current value).")
    brokersFee: float = Field(default=0, description="Broker fee charged on sale (% of sale price).")
    yearlyChange: YearlyChange = Field(
        default_factory=lambda: YearlyChange(type="depreciate", amount=3),
        description="Annual depreciation settings."
    )


class MachineryAsset(BaseAsset):
    type: Literal["machinery"] = "machinery"
    icon: str = "mdi-slot-machine"
    taxRate: float = Field(default=0, description="Annual property tax rate (% of assessed value).")
    maintenanceRate: float = Field(default=6, description="Annual maintenance cost (% of current value).")
    insuranceRate: float = Field(default=5, description="Annual insurance cost (% of current value).")
    brokersFee: float = Field(default=0, description="Broker fee charged on sale (% of sale price).")
    yearlyChange: YearlyChange = Field(
        default_factory=lambda: YearlyChange(type="depreciate", amount=3),
        description="Annual depreciation settings."
    )


# ---------------------------------------------------------------------------
# Custom Asset
# ---------------------------------------------------------------------------

class CustomAsset(BaseAsset):
    """Flexible asset type with optional income generation."""
    type: Literal["other"] = "other"
    icon: str = "mdi-currency-usd-circle"
    taxRate: float = Field(default=0, description="Annual property tax rate (% of assessed value).")
    maintenanceRate: float = Field(default=0, description="Annual maintenance cost (% of current value).")
    insuranceRate: float = Field(default=0, description="Annual insurance cost (% of current value).")
    brokersFee: float = Field(default=0, description="Broker fee charged on sale (% of sale price).")
    yearlyChange: YearlyChange = Field(
        default_factory=lambda: YearlyChange(type="match-inflation", amount=0),
        description="Annual value change settings."
    )
    generateIncome: bool = Field(default=False, description="Whether this asset generates income.")
    incomeRate: float = Field(default=12, description="Income rate (% of current value per year).")
    incomeRateType: str = "%"
    isPassiveIncome: bool = Field(default=False, description="Whether income is classified as passive.")
    managementRate: float = Field(default=0, description="Management fee (% of income).")
    managementRateType: str = "%"
    selfEmployment: bool = Field(default=False, description="Treat income as self-employment income.")


# ---------------------------------------------------------------------------
# Union — subtypes must come before their base types
# ---------------------------------------------------------------------------

RealAsset = Union[
    RentalPropertyAsset,
    BuildingAsset,
    CommercialPropertyAsset,
    RealEstateAsset,
    CarAsset,
    MotorcycleAsset,
    BoatAsset,
    LandAsset,
    JewelryAsset,
    PreciousMetalsAsset,
    FurnitureAsset,
    InstrumentAsset,
    MachineryAsset,
    CustomAsset,
]
