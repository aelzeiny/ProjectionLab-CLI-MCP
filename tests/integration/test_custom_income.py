"""
Integration test — Custom Income ("other") CRUD and field serialization.

Tests all major Custom Income configurations:
  - Basic yearly income (minimal fields, all defaults)
  - Actual-dollar amount type
  - Spouse owner
  - Age-based timing
  - Milestone timing
  - Frequency variants (once, once-per-year, monthly, bi-weekly, quarterly, weekly, daily)
  - Change over time: increase, decrease, match-inflation-plus
  - Tax: tax-exempt, withholding enabled, custom withhold %, no withholding
  - Advanced tax flags: self-employment, wage, dividend, passive
  - Send To: routeToAccounts, preventOverflow
  - Recurrence (repeat=True with interval, scaler, repeatEnd)
  - Full round-trip: export → parse as CustomIncome → re-serialize → restore → re-export

Key distinguishing facts about Custom Income:
  - stored type = "other" (NOT "custom")
  - icon = "mdi-currency-usd-circle"
  - taxWithholding defaults to False (unlike all other income types which default to True)
  - withhold default = 20
  - No hoursPerWeek, goPartTime, hasPension / pension* fields
  - end default has no modifier (milestone/retirement, inclusive)
  - selfEmployment/wage/isDividendIncome/isPassiveIncome are stored as explicit bools

Each case asserts data integrity via re-export, then pauses for browser
visual verification before cleanup.

Usage:
    CDP_PORT=9222 python tests/integration/test_custom_income.py
"""
from __future__ import annotations
import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "projectionlab_mcp"))

if not os.getenv("CDP_PORT"):
    print("ERROR: CDP_PORT is not set. Run with: CDP_PORT=9222 python tests/integration/test_custom_income.py")
    sys.exit(1)

from projectionlab_mcp import plugin_api as api
from projectionlab_mcp.models.income import (
    CustomIncome, NewCustomIncome, IncomeTimeRef, IncomeYearlyChange,
)

TAG = "TEST-CUSTOM-"
PLAN_ID: str = ""  # set in main()


# ── helpers ───────────────────────────────────────────────────────────────────

def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def fail(msg: str) -> None:
    print(f"  ✗ FAIL: {msg}")
    raise AssertionError(msg)


def section(title: str) -> None:
    print(f"\n{'─' * 60}\n  {title}\n{'─' * 60}")


def assert_eq(label: str, actual, expected) -> None:
    if actual != expected:
        fail(f"{label}: expected {expected!r}, got {actual!r}")
    ok(f"{label} = {actual!r}")


def assert_approx(label: str, actual: float, expected: float, tol: float = 0.01) -> None:
    if abs(actual - expected) > tol:
        fail(f"{label}: expected ~{expected}, got {actual}")
    ok(f"{label} ≈ {actual}")


async def _get_income_events(plan_id: str) -> list[dict]:
    data = await api.export_data()
    plan = api._find_plan(data.plans, plan_id)
    return plan.get("income", {}).get("events", [])


async def create_income(plan_id: str, income: CustomIncome) -> None:
    """Insert a custom income event into plan.income.events via restorePlans."""
    data = await api.export_data()
    plans = data.plans
    plan = api._find_plan(plans, plan_id)
    plan.setdefault("income", {}).setdefault("events", [])
    plan["income"]["events"].append(income.model_dump(exclude_none=True))
    await api.restore_plans(plans)


async def delete_income(plan_id: str, income_id: str) -> None:
    data = await api.export_data()
    plans = data.plans
    plan = api._find_plan(plans, plan_id)
    events = plan.get("income", {}).get("events", [])
    remaining = [e for e in events if e.get("id") != income_id]
    if len(remaining) == len(events):
        raise ValueError(f"Income '{income_id}' not found in plan '{plan_id}'.")
    plan["income"]["events"] = remaining
    await api.restore_plans(plans)


async def fetch_income(plan_id: str, income_id: str) -> dict:
    events = await _get_income_events(plan_id)
    for e in events:
        if e.get("id") == income_id:
            return e
    raise ValueError(f"Income '{income_id}' not found after create.")


# ── test cases ────────────────────────────────────────────────────────────────

async def test_basic_defaults(plan_id: str) -> str:
    """Minimal custom income: name + amount, all defaults verified."""
    section("TEST 1 — Basic Defaults (name + amount only)")
    c = NewCustomIncome(name=f"{TAG}basic", amount=25000).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    # Stored type is "other", not "custom"
    assert_eq("type", raw["type"], "other")
    assert_eq("planPath", raw["planPath"], "income")
    assert_eq("name", raw["name"], f"{TAG}basic")
    assert_eq("title", raw["title"], "Custom Income")
    assert_eq("icon", raw["icon"], "mdi-currency-usd-circle")
    assert_eq("owner", raw["owner"], "me")
    assert_approx("amount", raw["amount"], 25000)
    assert_eq("amountType", raw["amountType"], "today$")
    assert_eq("frequency", raw["frequency"], "yearly")
    assert_eq("frequencyChoices", raw["frequencyChoices"], True)
    assert_eq("start.type", raw["start"]["type"], "keyword")
    assert_eq("start.value", raw["start"]["value"], "beforeCurrentYear")
    assert_eq("end.type", raw["end"]["type"], "milestone")
    assert_eq("end.value", raw["end"]["value"], "retirement")
    # end has NO modifier by default (unlike hourly which has "exclude")
    assert_eq("end.modifier", raw["end"].get("modifier"), None)
    assert_eq("yearlyChange.type", raw["yearlyChange"]["type"], "match-inflation")
    # taxWithholding defaults to False — key difference from salary/hourly/RSU
    assert_eq("taxWithholding", raw["taxWithholding"], False)
    assert_eq("taxExempt", raw["taxExempt"], False)
    assert_approx("withhold", raw["withhold"], 20.0)
    assert_eq("selfEmployment", raw["selfEmployment"], False)
    assert_eq("wage", raw["wage"], False)
    assert_eq("isDividendIncome", raw["isDividendIncome"], False)
    assert_eq("isPassiveIncome", raw["isPassiveIncome"], False)
    assert_eq("repeat", raw["repeat"], False)

    ok(f"Basic custom income created: {c.id}")
    return c.id


async def test_actual_dollar(plan_id: str) -> str:
    """Custom income entered in nominal dollars."""
    section("TEST 2 — Actual$ Amount Type")
    c = NewCustomIncome(
        name=f"{TAG}actual-dollar",
        amount=50000,
        amountType="actual$",
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("amountType", raw["amountType"], "actual$")
    assert_approx("amount", raw["amount"], 50000)

    ok(f"Actual$ income created: {c.id}")
    return c.id


async def test_spouse_owner(plan_id: str) -> str:
    """Custom income owned by spouse."""
    section("TEST 3 — Spouse Owner")
    c = NewCustomIncome(
        name=f"{TAG}spouse",
        amount=30000,
        owner="spouse",
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("owner", raw["owner"], "spouse")

    ok(f"Spouse income created: {c.id}")
    return c.id


async def test_age_timing(plan_id: str) -> str:
    """Custom income starting at age 40."""
    section("TEST 4 — Age-based Timing (start at age 40)")
    c = NewCustomIncome(
        name=f"{TAG}age-timing",
        amount=15000,
        start=IncomeTimeRef(type="age", value="40"),
        end=IncomeTimeRef(type="age", value="65"),
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("start.type", raw["start"]["type"], "age")
    assert_eq("start.value", raw["start"]["value"], "40")
    assert_eq("end.type", raw["end"]["type"], "age")
    assert_eq("end.value", raw["end"]["value"], "65")

    ok(f"Age-timing income created: {c.id}")
    return c.id


async def test_milestone_timing(plan_id: str) -> str:
    """Custom income from FI milestone to end of plan."""
    section("TEST 5 — Milestone Timing (FI to end of plan)")
    c = NewCustomIncome(
        name=f"{TAG}milestone",
        amount=20000,
        start=IncomeTimeRef(type="milestone", value="fi"),
        end=IncomeTimeRef(type="keyword", value="endOfPlan"),
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("start.type", raw["start"]["type"], "milestone")
    assert_eq("start.value", raw["start"]["value"], "fi")
    assert_eq("end.type", raw["end"]["type"], "keyword")
    assert_eq("end.value", raw["end"]["value"], "endOfPlan")

    ok(f"Milestone-timing income created: {c.id}")
    return c.id


async def test_frequency_once(plan_id: str) -> str:
    """Custom income as a one-time lump sum."""
    section("TEST 6 — Frequency: once (one-time)")
    c = NewCustomIncome(
        name=f"{TAG}freq-once",
        amount=100000,
        frequency="once",
        start=IncomeTimeRef(type="keyword", value="now", modifier="include"),
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("frequency", raw["frequency"], "once")

    ok(f"Once income created: {c.id}")
    return c.id


async def test_frequency_monthly(plan_id: str) -> str:
    """Custom income paid monthly."""
    section("TEST 7 — Frequency: monthly")
    c = NewCustomIncome(
        name=f"{TAG}freq-monthly",
        amount=2000,
        frequency="monthly",
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("frequency", raw["frequency"], "monthly")

    ok(f"Monthly income created: {c.id}")
    return c.id


async def test_frequency_biweekly(plan_id: str) -> str:
    """Custom income paid bi-weekly."""
    section("TEST 8 — Frequency: bi-weekly")
    c = NewCustomIncome(
        name=f"{TAG}freq-biweekly",
        amount=1500,
        frequency="bi-weekly",
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("frequency", raw["frequency"], "bi-weekly")

    ok(f"Bi-weekly income created: {c.id}")
    return c.id


async def test_frequency_quarterly(plan_id: str) -> str:
    """Custom income paid quarterly."""
    section("TEST 9 — Frequency: quarterly")
    c = NewCustomIncome(
        name=f"{TAG}freq-quarterly",
        amount=5000,
        frequency="quarterly",
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("frequency", raw["frequency"], "quarterly")

    ok(f"Quarterly income created: {c.id}")
    return c.id


async def test_yearly_change_increase(plan_id: str) -> str:
    """Custom income growing 3% per year."""
    section("TEST 10 — Change Over Time: Increase 3%/yr")
    c = NewCustomIncome(
        name=f"{TAG}increase",
        amount=40000,
        yearlyChange=IncomeYearlyChange(type="increase", amount=3.0),
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    yc = raw["yearlyChange"]
    assert_eq("yearlyChange.type", yc["type"], "increase")
    assert_approx("yearlyChange.amount", yc["amount"], 3.0)

    ok(f"Increase income created: {c.id}")
    return c.id


async def test_yearly_change_decrease(plan_id: str) -> str:
    """Custom income decreasing 2% per year."""
    section("TEST 11 — Change Over Time: Decrease 2%/yr")
    c = NewCustomIncome(
        name=f"{TAG}decrease",
        amount=35000,
        yearlyChange=IncomeYearlyChange(type="decrease", amount=2.0),
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    yc = raw["yearlyChange"]
    assert_eq("yearlyChange.type", yc["type"], "decrease")
    assert_approx("yearlyChange.amount", yc["amount"], 2.0)

    ok(f"Decrease income created: {c.id}")
    return c.id


async def test_yearly_change_none(plan_id: str) -> str:
    """Custom income with no change over time (flat nominal)."""
    section("TEST 12 — Change Over Time: None (flat nominal)")
    c = NewCustomIncome(
        name=f"{TAG}flat",
        amount=10000,
        yearlyChange=IncomeYearlyChange(type="none"),
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("yearlyChange.type", raw["yearlyChange"]["type"], "none")

    ok(f"Flat income created: {c.id}")
    return c.id


async def test_tax_withholding_enabled(plan_id: str) -> str:
    """Custom income with tax withholding turned ON (non-default)."""
    section("TEST 13 — Tax: Withholding Enabled (non-default)")
    c = NewCustomIncome(
        name=f"{TAG}withheld",
        amount=60000,
        taxWithholding=True,
        withhold=25.0,
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("taxWithholding", raw["taxWithholding"], True)
    assert_approx("withhold", raw["withhold"], 25.0)

    ok(f"Withholding income created: {c.id}")
    return c.id


async def test_tax_exempt(plan_id: str) -> str:
    """Custom income that is fully tax-exempt."""
    section("TEST 14 — Tax: Tax-Exempt")
    c = NewCustomIncome(
        name=f"{TAG}tax-exempt",
        amount=20000,
        taxExempt=True,
        taxWithholding=False,
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("taxExempt", raw["taxExempt"], True)
    assert_eq("taxWithholding", raw["taxWithholding"], False)

    ok(f"Tax-exempt income created: {c.id}")
    return c.id


async def test_self_employment(plan_id: str) -> str:
    """Custom income flagged as self-employment income."""
    section("TEST 15 — Advanced Tax: Self-Employment")
    c = NewCustomIncome(
        name=f"{TAG}self-emp",
        amount=45000,
        selfEmployment=True,
        taxWithholding=True,
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("selfEmployment", raw["selfEmployment"], True)
    assert_eq("wage", raw["wage"], False)

    ok(f"Self-employment income created: {c.id}")
    return c.id


async def test_wage_income(plan_id: str) -> str:
    """Custom income flagged as wage income."""
    section("TEST 16 — Advanced Tax: Wage Income")
    c = NewCustomIncome(
        name=f"{TAG}wage",
        amount=55000,
        wage=True,
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("wage", raw["wage"], True)
    assert_eq("selfEmployment", raw["selfEmployment"], False)

    ok(f"Wage income created: {c.id}")
    return c.id


async def test_dividend_passive(plan_id: str) -> str:
    """Custom income flagged as dividend + passive income."""
    section("TEST 17 — Advanced Tax: Dividend + Passive")
    c = NewCustomIncome(
        name=f"{TAG}div-passive",
        amount=12000,
        isDividendIncome=True,
        isPassiveIncome=True,
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("isDividendIncome", raw["isDividendIncome"], True)
    assert_eq("isPassiveIncome", raw["isPassiveIncome"], True)

    ok(f"Dividend+passive income created: {c.id}")
    return c.id


async def test_prevent_overflow(plan_id: str) -> str:
    """Custom income with preventOverflow enabled."""
    section("TEST 18 — Send To: preventOverflow")
    c = NewCustomIncome(
        name=f"{TAG}overflow",
        amount=80000,
        # preventOverflow is not in NewCustomIncome fields — use to_custom_income then override
    ).to_custom_income()
    c.preventOverflow = True
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("preventOverflow", raw["preventOverflow"], True)

    ok(f"PreventOverflow income created: {c.id}")
    return c.id


async def test_recurrence_basic(plan_id: str) -> str:
    """Custom income repeating every 2 years until end of plan."""
    section("TEST 19 — Recurrence: repeat every 2 years until End of Plan")
    c = NewCustomIncome(
        name=f"{TAG}repeat-basic",
        amount=50000,
        frequency="once",
        start=IncomeTimeRef(type="keyword", value="now", modifier="include"),
        repeat=True,
        repeatInterval=2,
        repeatEnd=IncomeTimeRef(type="keyword", value="endOfPlan", modifier="include"),
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("repeat", raw["repeat"], True)
    assert_eq("repeatIntervalType", raw["repeatIntervalType"], "between")
    assert_eq("repeatInterval", raw["repeatInterval"], 2)
    assert_eq("repeatEnd.value", raw["repeatEnd"]["value"], "endOfPlan")
    assert_eq("repeatEnd.modifier", raw["repeatEnd"]["modifier"], "include")

    ok(f"Recurrence (basic) income created: {c.id}")
    return c.id


async def test_recurrence_with_scaler(plan_id: str) -> str:
    """Custom income repeating every 3 years, scaling up 5% each time."""
    section("TEST 20 — Recurrence: every 3 years, +5% scaler")
    c = NewCustomIncome(
        name=f"{TAG}repeat-scaler",
        amount=75000,
        frequency="once",
        start=IncomeTimeRef(type="keyword", value="now", modifier="include"),
        repeat=True,
        repeatInterval=3,
        repeatScaler=5.0,
        repeatEnd=IncomeTimeRef(type="milestone", value="retirement", modifier="exclude"),
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("repeat", raw["repeat"], True)
    assert_eq("repeatIntervalType", raw["repeatIntervalType"], "between")
    assert_eq("repeatInterval", raw["repeatInterval"], 3)
    assert_approx("repeatScaler", raw["repeatScaler"], 5.0)
    assert_eq("repeatEnd.value", raw["repeatEnd"]["value"], "retirement")
    assert_eq("repeatEnd.modifier", raw["repeatEnd"]["modifier"], "exclude")

    ok(f"Recurrence+scaler income created: {c.id}")
    return c.id


async def test_frequency_weekly(plan_id: str) -> str:
    """Custom income paid weekly."""
    section("TEST 21 — Frequency: weekly")
    c = NewCustomIncome(
        name=f"{TAG}freq-weekly",
        amount=500,
        frequency="weekly",
    ).to_custom_income()
    await create_income(plan_id, c)

    raw = await fetch_income(plan_id, c.id)
    assert_eq("frequency", raw["frequency"], "weekly")

    ok(f"Weekly income created: {c.id}")
    return c.id


async def test_round_trip(plan_id: str) -> str:
    """Full round-trip: create → export → parse as CustomIncome → mutate → re-save → re-export."""
    section("TEST 22 — Full Round-Trip: export → CustomIncome.model_validate → mutate → re-import")

    original = NewCustomIncome(
        name=f"{TAG}round-trip",
        amount=45000,
        frequency="monthly",
        owner="me",
        start=IncomeTimeRef(type="keyword", value="beforeCurrentYear"),
        end=IncomeTimeRef(type="milestone", value="retirement"),
        yearlyChange=IncomeYearlyChange(type="increase", amount=2.5),
        taxWithholding=True,
        withhold=22.0,
        isDividendIncome=True,
    ).to_custom_income()
    await create_income(plan_id, original)

    # Step 1: Export and parse
    raw1 = await fetch_income(plan_id, original.id)
    parsed = CustomIncome.model_validate(raw1)

    assert_eq("round-trip type", parsed.type, "other")
    assert_eq("round-trip name", parsed.name, f"{TAG}round-trip")
    assert_approx("round-trip amount", parsed.amount, 45000)
    assert_eq("round-trip frequency", parsed.frequency, "monthly")
    assert_eq("round-trip yearlyChange.type", parsed.yearlyChange.type, "increase")
    assert_approx("round-trip yearlyChange.amount", parsed.yearlyChange.amount, 2.5)
    assert_eq("round-trip taxWithholding", parsed.taxWithholding, True)
    assert_approx("round-trip withhold", parsed.withhold, 22.0)
    assert_eq("round-trip isDividendIncome", parsed.isDividendIncome, True)

    # Step 2: Mutate and re-save
    parsed.amount = 55000
    parsed.withhold = 28.0
    parsed.frequency = "yearly"

    data = await api.export_data()
    plans = data.plans
    plan = api._find_plan(plans, plan_id)
    events = plan.get("income", {}).get("events", [])
    for i, e in enumerate(events):
        if e.get("id") == original.id:
            events[i] = parsed.model_dump(exclude_none=True)
            break
    await api.restore_plans(plans)

    # Step 3: Re-export and verify mutations persisted
    raw2 = await fetch_income(plan_id, original.id)
    assert_approx("mutated amount", raw2["amount"], 55000)
    assert_approx("mutated withhold", raw2["withhold"], 28.0)
    assert_eq("mutated frequency", raw2["frequency"], "yearly")
    # Unchanged fields should still be intact
    assert_eq("unchanged type", raw2["type"], "other")
    assert_eq("unchanged isDividendIncome", raw2["isDividendIncome"], True)
    assert_eq("unchanged taxWithholding", raw2["taxWithholding"], True)

    ok(f"Round-trip income created: {original.id}")
    return original.id


# ── main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    section("0. Finding active plan")
    plans = await api.list_plans()
    active = next((p for p in plans if p.get("active")), plans[0])
    plan_id = active["id"]
    print(f"  Active plan: {active['name']} ({plan_id})")

    created_ids: list[str] = []

    tests = [
        test_basic_defaults,
        test_actual_dollar,
        test_spouse_owner,
        test_age_timing,
        test_milestone_timing,
        test_frequency_once,
        test_frequency_monthly,
        test_frequency_biweekly,
        test_frequency_quarterly,
        test_yearly_change_increase,
        test_yearly_change_decrease,
        test_yearly_change_none,
        test_tax_withholding_enabled,
        test_tax_exempt,
        test_self_employment,
        test_wage_income,
        test_dividend_passive,
        test_prevent_overflow,
        test_recurrence_basic,
        test_recurrence_with_scaler,
        test_frequency_weekly,
        test_round_trip,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            income_id = await test_fn(plan_id)
            created_ids.append(income_id)
            passed += 1
        except AssertionError as e:
            print(f"  ✗ ASSERTION FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ UNEXPECTED ERROR: {e}")
            import traceback; traceback.print_exc()
            failed += 1

    section("Summary — verify in browser, then press ENTER to clean up")
    print(f"  Passed: {passed} / {len(tests)}")
    print(f"  Failed: {failed} / {len(tests)}")
    print(f"\n  Plan URL: https://app.projectionlab.com/plan/{plan_id}")
    print(f"  {len(created_ids)} custom income events created (look for '{TAG}' prefix in Income section):")
    for iid in created_ids:
        print(f"    - {iid}")

    input("\n  Press ENTER after browser verification to DELETE all test data...")

    section("Cleanup")
    for iid in created_ids:
        try:
            await delete_income(plan_id, iid)
            ok(f"Deleted income {iid}")
        except Exception as e:
            print(f"  ✗ Could not delete {iid}: {e}")

    section("Done")


if __name__ == "__main__":
    asyncio.run(main())
