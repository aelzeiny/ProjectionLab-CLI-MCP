"""
Integration test — hourly wage income CRUD and field serialization.

Tests all major hourly wage configurations:
  - Basic wage (minimal fields, all defaults)
  - Custom hours per week (part-time 20h/week)
  - Age-based time range
  - Change over time: increase with cap, match-inflation-plus, decrease, none
  - Tax: tax-exempt, no withholding, custom withhold %
  - Advanced tax: self-employment, dividend income, passive income
  - Part-time work (custom start/end/rate)
  - Defined benefit pension (FAP and fixed-amount payout types)
  - Full round-trip: export → parse as HourlyWage → re-serialize → restore → re-export

Each case asserts data integrity via re-export, then pauses for browser
visual verification before cleanup.

Usage:
    CDP_PORT=9222 python tests/integration/test_hourly_wage_income.py
"""
from __future__ import annotations
import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "projectionlab_mcp"))

if not os.getenv("CDP_PORT"):
    print("ERROR: CDP_PORT is not set. Run with: CDP_PORT=9222 python tests/integration/test_hourly_wage_income.py")
    sys.exit(1)

from projectionlab_mcp import plugin_api as api
from projectionlab_mcp.models.income import HourlyWage, NewHourlyWage, IncomeTimeRef, IncomeYearlyChange

TAG = "TEST-HOURLY-"
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


async def create_wage(plan_id: str, wage: HourlyWage) -> None:
    """Insert a wage event into plan.income.events via restorePlans."""
    data = await api.export_data()
    plans = data.plans
    plan = api._find_plan(plans, plan_id)
    plan.setdefault("income", {}).setdefault("events", [])
    plan["income"]["events"].append(wage.model_dump(exclude_none=True))
    await api.restore_plans(plans)


async def delete_wage(plan_id: str, wage_id: str) -> None:
    data = await api.export_data()
    plans = data.plans
    plan = api._find_plan(plans, plan_id)
    events = plan.get("income", {}).get("events", [])
    remaining = [e for e in events if e.get("id") != wage_id]
    if len(remaining) == len(events):
        raise ValueError(f"Wage '{wage_id}' not found in plan '{plan_id}'.")
    plan["income"]["events"] = remaining
    await api.restore_plans(plans)


async def fetch_wage(plan_id: str, wage_id: str) -> dict:
    events = await _get_income_events(plan_id)
    for e in events:
        if e.get("id") == wage_id:
            return e
    raise ValueError(f"Wage '{wage_id}' not found after create.")


# ── test cases ────────────────────────────────────────────────────────────────

async def test_basic_wage(plan_id: str) -> str:
    """Minimal wage: just name, amount. All defaults should persist."""
    section("TEST 1 — Basic Hourly Wage (minimal fields, all defaults)")
    w = NewHourlyWage(name=f"{TAG}basic", amount=25.0).to_hourly_wage()
    await create_wage(plan_id, w)

    raw = await fetch_wage(plan_id, w.id)
    assert_eq("type", raw["type"], "hourly")
    assert_eq("name", raw["name"], f"{TAG}basic")
    assert_eq("title", raw["title"], f"{TAG}basic")
    assert_eq("owner", raw["owner"], "me")
    assert_approx("amount", raw["amount"], 25.0)
    assert_eq("amountType", raw["amountType"], "today$")
    assert_approx("hoursPerWeek", raw["hoursPerWeek"], 40.0)
    assert_eq("frequencyChoices", raw["frequencyChoices"], False)
    assert_eq("start.type", raw["start"]["type"], "keyword")
    assert_eq("start.value", raw["start"]["value"], "beforeCurrentYear")
    assert_eq("end.type", raw["end"]["type"], "milestone")
    assert_eq("end.value", raw["end"]["value"], "retirement")
    assert_eq("end.modifier", raw["end"].get("modifier"), "exclude")
    assert_eq("yearlyChange.type", raw["yearlyChange"]["type"], "match-inflation")
    assert_eq("taxExempt", raw["taxExempt"], False)
    assert_eq("taxWithholding", raw["taxWithholding"], True)
    assert_approx("withhold", raw["withhold"], 20.0)
    assert_eq("selfEmployment", raw.get("selfEmployment", False), False)
    assert_eq("goPartTime", raw["goPartTime"], False)
    assert_eq("hasPension", raw["hasPension"], False)
    assert_eq("icon", raw["icon"], "mdi-briefcase-clock")

    ok(f"Basic wage created: {w.id}")
    return w.id


async def test_custom_hours(plan_id: str) -> str:
    """Part-time 20 hours/week wage."""
    section("TEST 2 — Custom Hours Per Week (20h/week)")
    w = NewHourlyWage(
        name=f"{TAG}20hrs",
        amount=35.0,
        hoursPerWeek=20,
    ).to_hourly_wage()
    await create_wage(plan_id, w)

    raw = await fetch_wage(plan_id, w.id)
    assert_approx("hoursPerWeek", raw["hoursPerWeek"], 20.0)
    assert_approx("amount", raw["amount"], 35.0)

    ok(f"20h/week wage created: {w.id}")
    return w.id


async def test_age_based_time_range(plan_id: str) -> str:
    """Wage active from age 22 to age 55 (age-based TimeRef)."""
    section("TEST 3 — Age-based Time Range (22 → 55)")
    w = NewHourlyWage(
        name=f"{TAG}age-range",
        amount=18.0,
        start=IncomeTimeRef(type="age", value="22"),
        end=IncomeTimeRef(type="age", value="55"),
    ).to_hourly_wage()
    await create_wage(plan_id, w)

    raw = await fetch_wage(plan_id, w.id)
    assert_eq("start.type", raw["start"]["type"], "age")
    assert_eq("start.value", raw["start"]["value"], "22")
    assert_eq("end.type", raw["end"]["type"], "age")
    assert_eq("end.value", raw["end"]["value"], "55")

    ok(f"Age-range wage created: {w.id}")
    return w.id


async def test_yearly_change_increase_with_cap(plan_id: str) -> str:
    """Wage that increases 3%/year, capped at $50/hr in Today's Currency."""
    section("TEST 4 — Yearly Change: Increase 3%/yr with $50/hr cap")
    w = NewHourlyWage(
        name=f"{TAG}increase-capped",
        amount=30.0,
        yearlyChange=IncomeYearlyChange(
            type="increase",
            amount=3.0,
            limitEnabled=True,
            limit=50.0,
            limitType="today$",
        ),
    ).to_hourly_wage()
    await create_wage(plan_id, w)

    raw = await fetch_wage(plan_id, w.id)
    yc = raw["yearlyChange"]
    assert_eq("yearlyChange.type", yc["type"], "increase")
    assert_approx("yearlyChange.amount", yc["amount"], 3.0)
    assert_eq("yearlyChange.limitEnabled", yc["limitEnabled"], True)
    assert_approx("yearlyChange.limit", yc["limit"], 50.0)
    assert_eq("yearlyChange.limitType", yc["limitType"], "today$")

    ok(f"Increase-capped wage created: {w.id}")
    return w.id


async def test_yearly_change_match_inflation_plus(plan_id: str) -> str:
    """Wage that grows at inflation +1.5% per year."""
    section("TEST 5 — Yearly Change: Match Inflation +1.5%")
    w = NewHourlyWage(
        name=f"{TAG}inf-plus",
        amount=22.0,
        yearlyChange=IncomeYearlyChange(type="match-inflation-plus", amount=1.5),
    ).to_hourly_wage()
    await create_wage(plan_id, w)

    raw = await fetch_wage(plan_id, w.id)
    yc = raw["yearlyChange"]
    assert_eq("yearlyChange.type", yc["type"], "match-inflation-plus")
    assert_approx("yearlyChange.amount", yc["amount"], 1.5)

    ok(f"Inflation+1.5% wage created: {w.id}")
    return w.id


async def test_yearly_change_decrease(plan_id: str) -> str:
    """Wage that decreases 2%/year."""
    section("TEST 6 — Yearly Change: Decrease 2%/yr")
    w = NewHourlyWage(
        name=f"{TAG}decrease",
        amount=45.0,
        yearlyChange=IncomeYearlyChange(type="decrease", amount=2.0),
    ).to_hourly_wage()
    await create_wage(plan_id, w)

    raw = await fetch_wage(plan_id, w.id)
    yc = raw["yearlyChange"]
    assert_eq("yearlyChange.type", yc["type"], "decrease")
    assert_approx("yearlyChange.amount", yc["amount"], 2.0)

    ok(f"Decreasing wage created: {w.id}")
    return w.id


async def test_yearly_change_none(plan_id: str) -> str:
    """Wage frozen in nominal terms (no yearly change)."""
    section("TEST 7 — Yearly Change: None (flat in nominal terms)")
    w = NewHourlyWage(
        name=f"{TAG}frozen",
        amount=15.0,
        yearlyChange=IncomeYearlyChange(type="none"),
    ).to_hourly_wage()
    await create_wage(plan_id, w)

    raw = await fetch_wage(plan_id, w.id)
    assert_eq("yearlyChange.type", raw["yearlyChange"]["type"], "none")

    ok(f"Frozen wage created: {w.id}")
    return w.id


async def test_tax_exempt(plan_id: str) -> str:
    """Tax-exempt hourly wage with no withholding."""
    section("TEST 8 — Tax: Tax-Exempt, No Withholding")
    w = NewHourlyWage(
        name=f"{TAG}tax-exempt",
        amount=20.0,
        taxExempt=True,
        taxWithholding=False,
    ).to_hourly_wage()
    await create_wage(plan_id, w)

    raw = await fetch_wage(plan_id, w.id)
    assert_eq("taxExempt", raw["taxExempt"], True)
    assert_eq("taxWithholding", raw["taxWithholding"], False)

    ok(f"Tax-exempt wage created: {w.id}")
    return w.id


async def test_custom_withholding(plan_id: str) -> str:
    """Wage with custom 30% withholding (higher than 20% default)."""
    section("TEST 9 — Tax: Custom 30% Withholding")
    w = NewHourlyWage(
        name=f"{TAG}withhold-30",
        amount=60.0,
        taxWithholding=True,
        withhold=30.0,
    ).to_hourly_wage()
    await create_wage(plan_id, w)

    raw = await fetch_wage(plan_id, w.id)
    assert_eq("taxWithholding", raw["taxWithholding"], True)
    assert_approx("withhold", raw["withhold"], 30.0)

    ok(f"Custom-withhold wage created: {w.id}")
    return w.id


async def test_self_employment(plan_id: str) -> str:
    """Self-employment hourly wage (freelance/1099 style)."""
    section("TEST 10 — Advanced Tax: Self-Employment")
    w = NewHourlyWage(
        name=f"{TAG}self-employed",
        amount=75.0,
        selfEmployment=True,
        wage=False,
    ).to_hourly_wage()
    await create_wage(plan_id, w)

    raw = await fetch_wage(plan_id, w.id)
    assert_eq("selfEmployment", raw.get("selfEmployment"), True)
    assert_eq("wage", raw.get("wage", False), False)

    ok(f"Self-employment wage created: {w.id}")
    return w.id


async def test_dividend_and_passive(plan_id: str) -> str:
    """Hourly wage flagged as dividend + passive income."""
    section("TEST 11 — Advanced Tax: Dividend Income + Passive Income")
    w = NewHourlyWage(
        name=f"{TAG}dividend-passive",
        amount=12.0,
        isDividendIncome=True,
        isPassiveIncome=True,
    ).to_hourly_wage()
    await create_wage(plan_id, w)

    raw = await fetch_wage(plan_id, w.id)
    assert_eq("isDividendIncome", raw.get("isDividendIncome"), True)
    assert_eq("isPassiveIncome", raw.get("isPassiveIncome"), True)

    ok(f"Dividend+passive wage created: {w.id}")
    return w.id


async def test_part_time(plan_id: str) -> str:
    """Wage with a part-time period from age 50 to retirement at 60% rate."""
    section("TEST 12 — Part-Time: age 50 → retirement at 60%")
    w = NewHourlyWage(
        name=f"{TAG}part-time",
        amount=55.0,
        goPartTime=True,
        partTimeStart=IncomeTimeRef(type="age", value="50"),
        partTimeEnd=IncomeTimeRef(type="milestone", value="retirement"),
        partTimeRate=60.0,
    ).to_hourly_wage()
    await create_wage(plan_id, w)

    raw = await fetch_wage(plan_id, w.id)
    assert_eq("goPartTime", raw["goPartTime"], True)
    assert_eq("partTimeStart.type", raw["partTimeStart"]["type"], "age")
    assert_eq("partTimeStart.value", raw["partTimeStart"]["value"], "50")
    assert_eq("partTimeEnd.type", raw["partTimeEnd"]["type"], "milestone")
    assert_eq("partTimeEnd.value", raw["partTimeEnd"]["value"], "retirement")
    assert_approx("partTimeRate", raw["partTimeRate"], 60.0)

    ok(f"Part-time wage created: {w.id}")
    return w.id


async def test_pension_fap(plan_id: str) -> str:
    """Hourly wage with defined-benefit pension — % of Final Average Pay."""
    section("TEST 13 — Pension: 4% contribution, FAP 20% payout, tax-free payouts")
    w = NewHourlyWage(
        name=f"{TAG}pension-fap",
        amount=40.0,
        hasPension=True,
        pensionContribution=4.0,
        pensionContributionType="%",
        contribsReduceTaxableIncome=True,
        pensionPayoutsStart=IncomeTimeRef(type="milestone", value="retirement"),
        pensionPayoutsEnd=IncomeTimeRef(type="keyword", value="endOfPlan"),
        pensionPayoutType="fap",
        pensionPayoutRate=20.0,
        pensionPayoutsAreTaxFree=True,
    ).to_hourly_wage()
    await create_wage(plan_id, w)

    raw = await fetch_wage(plan_id, w.id)
    assert_eq("hasPension", raw["hasPension"], True)
    assert_approx("pensionContribution", raw["pensionContribution"], 4.0)
    assert_eq("pensionContributionType", raw["pensionContributionType"], "%")
    assert_eq("contribsReduceTaxableIncome", raw["contribsReduceTaxableIncome"], True)
    assert_eq("pensionPayoutType", raw["pensionPayoutType"], "fap")
    assert_approx("pensionPayoutRate", raw["pensionPayoutRate"], 20.0)
    assert_eq("pensionPayoutsAreTaxFree", raw["pensionPayoutsAreTaxFree"], True)
    assert_eq("pensionPayoutsStart.value", raw["pensionPayoutsStart"]["value"], "retirement")
    assert_eq("pensionPayoutsEnd.value", raw["pensionPayoutsEnd"]["value"], "endOfPlan")

    ok(f"Pension (FAP) wage created: {w.id}")
    return w.id


async def test_pension_fixed_amount(plan_id: str) -> str:
    """Hourly wage with pension using fixed annual payout amount."""
    section("TEST 14 — Pension: Fixed payout amount ($18K/yr in today's dollars)")
    w = NewHourlyWage(
        name=f"{TAG}pension-fixed",
        amount=28.0,
        hasPension=True,
        pensionContribution=1500,
        pensionContributionType="$",
        contribsReduceTaxableIncome=False,
        pensionPayoutType="fixed",
        pensionPayoutAmount=18000,
        pensionPayoutsAreTaxFree=False,
    ).to_hourly_wage()
    await create_wage(plan_id, w)

    raw = await fetch_wage(plan_id, w.id)
    assert_eq("pensionPayoutType", raw["pensionPayoutType"], "fixed")
    assert_approx("pensionPayoutAmount", raw["pensionPayoutAmount"], 18000)
    assert_eq("pensionContributionType", raw["pensionContributionType"], "$")
    assert_approx("pensionContribution", raw["pensionContribution"], 1500)
    assert_eq("contribsReduceTaxableIncome", raw["contribsReduceTaxableIncome"], False)

    ok(f"Pension (fixed amount) wage created: {w.id}")
    return w.id


async def test_round_trip(plan_id: str) -> str:
    """Full round-trip: create → export → parse as HourlyWage → re-serialize → restore → re-export."""
    section("TEST 15 — Full Round-Trip: export → HourlyWage.model_validate → re-serialize → re-import")

    original = NewHourlyWage(
        name=f"{TAG}round-trip",
        amount=50.0,
        hoursPerWeek=32,
        owner="me",
        start=IncomeTimeRef(type="keyword", value="beforeCurrentYear"),
        end=IncomeTimeRef(type="age", value="60"),
        yearlyChange=IncomeYearlyChange(type="increase", amount=2.0, limitEnabled=True, limit=80.0),
        taxExempt=False,
        taxWithholding=True,
        withhold=22.0,
        selfEmployment=False,
        wage=True,
        goPartTime=True,
        partTimeStart=IncomeTimeRef(type="age", value="55"),
        partTimeEnd=IncomeTimeRef(type="age", value="60"),
        partTimeRate=50.0,
        hasPension=True,
        pensionContribution=3.0,
        pensionContributionType="%",
        pensionPayoutType="fap",
        pensionPayoutRate=15.0,
    ).to_hourly_wage()
    await create_wage(plan_id, original)

    # Step 1: Export and parse
    raw1 = await fetch_wage(plan_id, original.id)
    parsed = HourlyWage.model_validate(raw1)

    assert_eq("round-trip name", parsed.name, f"{TAG}round-trip")
    assert_approx("round-trip amount", parsed.amount, 50.0)
    assert_approx("round-trip hoursPerWeek", parsed.hoursPerWeek, 32.0)
    assert_eq("round-trip end.type", parsed.end.type, "age")
    assert_eq("round-trip end.value", parsed.end.value, "60")
    assert_eq("round-trip yearlyChange.type", parsed.yearlyChange.type, "increase")
    assert_eq("round-trip goPartTime", parsed.goPartTime, True)
    assert_eq("round-trip hasPension", parsed.hasPension, True)
    assert_eq("round-trip wage", parsed.wage, True)

    # Step 2: Mutate fields and re-save
    parsed.amount = 55.0
    parsed.hoursPerWeek = 40.0
    parsed.withhold = 25.0

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
    raw2 = await fetch_wage(plan_id, original.id)
    assert_approx("mutated amount", raw2["amount"], 55.0)
    assert_approx("mutated hoursPerWeek", raw2["hoursPerWeek"], 40.0)
    assert_approx("mutated withhold", raw2["withhold"], 25.0)
    # Unchanged fields
    assert_eq("unchanged goPartTime", raw2["goPartTime"], True)
    assert_approx("unchanged partTimeRate", raw2["partTimeRate"], 50.0)
    assert_eq("unchanged hasPension", raw2["hasPension"], True)

    ok(f"Round-trip wage created: {original.id}")
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
        test_basic_wage,
        test_custom_hours,
        test_age_based_time_range,
        test_yearly_change_increase_with_cap,
        test_yearly_change_match_inflation_plus,
        test_yearly_change_decrease,
        test_yearly_change_none,
        test_tax_exempt,
        test_custom_withholding,
        test_self_employment,
        test_dividend_and_passive,
        test_part_time,
        test_pension_fap,
        test_pension_fixed_amount,
        test_round_trip,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            wage_id = await test_fn(plan_id)
            created_ids.append(wage_id)
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
    print(f"  {len(created_ids)} wage events created (look for '{TAG}' prefix in Income section):")
    for wid in created_ids:
        print(f"    - {wid}")

    input("\n  Press ENTER after browser verification to DELETE all test data...")

    section("Cleanup")
    for wid in created_ids:
        try:
            await delete_wage(plan_id, wid)
            ok(f"Deleted wage {wid}")
        except Exception as e:
            print(f"  ✗ Could not delete {wid}: {e}")

    section("Done")


if __name__ == "__main__":
    asyncio.run(main())
