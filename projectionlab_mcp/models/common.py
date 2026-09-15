from __future__ import annotations
from typing import Annotated, Any, Literal, Optional
from pydantic import BaseModel, Field


class TimeRef(BaseModel):
    """A point in time (start/end/effective dates on accounts, assets, debts, income, expenses, priorities).

    Every shape observed in real exportData() output (ProjectionLab 4.6):

      {"type": "keyword",   "value": "beforeCurrentYear"}                     — already owned/active
      {"type": "keyword",   "value": "now", "modifier": "exclude"}            — current year
      {"type": "keyword",   "value": "never"}                                 — no end
      {"type": "keyword",   "value": "endOfPlan", "modifier": "include"}      — until the plan ends
      {"type": "age",       "value": "65"}                                    — at a given age
      {"type": "milestone", "value": "retirement", "modifier": "exclude"}     — built-in milestone
      {"type": "milestone", "value": "spouseRetirement", "modifier": "exclude"}
      {"type": "milestone", "value": "<milestone uuid>", "modifier": "include"}
      {"type": "date",      "value": "2027-01-01"}                            — a specific month (day is 01)
      {"type": "date",      "value": "2027-01-01", "modifier": "include"}
      {"type": "year",      "value": "2059"}                                  — a specific year

    modifier (optional): "include" = inclusive boundary, "exclude" = exclusive boundary.
    Many UI-created refs omit it entirely; when present on `start` it is usually "include"
    and on `end` usually "exclude".
    """
    type: Literal["keyword", "age", "milestone", "date", "year"]
    value: Annotated[str, Field(description='keyword: "beforeCurrentYear" | "now" | "never" | "endOfPlan"; age: "65"; milestone: "retirement" | "spouseRetirement" | uuid; date: "YYYY-MM-01"; year: "YYYY".')]
    modifier: Optional[Literal["include", "exclude"]] = None


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
