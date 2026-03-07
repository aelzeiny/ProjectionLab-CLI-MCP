from __future__ import annotations
from typing import Annotated, Any, Literal
from pydantic import BaseModel, Field


class TimeRef(BaseModel):
    """A point in time used for asset/debt start, end, and effective dates.

    Use a keyword reference for common anchors:
      {"type": "keyword", "value": "beforeCurrentYear"}  — already owned/active
      {"type": "keyword", "value": "now"}                — current year
      {"type": "keyword", "value": "never"}              — no end / holds indefinitely
      {"type": "keyword", "value": "retirement"}         — at retirement age

    Use an age reference to trigger at a specific age:
      {"type": "age", "value": "65"}
    """
    type: Literal["keyword", "age"]
    value: Annotated[str, Field(description='For keyword: "beforeCurrentYear", "now", "never", "retirement". For age: a numeric string like "65".')]


class WithdrawAge(BaseModel):
    type: Literal["keyword", "age"]
    modifier: Literal["include", "exclude"]
    value: str  # "now" or a numeric age as string


class DateRef(BaseModel):
    """A date reference used for originalOwnerBirth/Death on inherited IRAs."""
    type: Literal["date"] = "date"
    value: str  # "YYYY-MM-DD"


class DisplayAge(BaseModel):
    """Used by 529 plans to track a beneficiary's age milestone."""
    type: Literal["keyword", "age"]
    value: str
    modifier: int  # beneficiary age in years (e.g. 18)


class AccountUpdate(BaseModel):
    account_id: Annotated[str, Field(description="The ID of the account to update.")]
    data: Annotated[dict[str, Any], Field(description='Key/value pairs to assign (e.g. {"balance": 5000}).')]
    force: Annotated[bool, Field(description="Allow assigning new properties that don't already exist on the account.")] = False


class Location(BaseModel):
    country: str
    state: str
