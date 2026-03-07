"""
Integration test — salary income CRUD and field serialization.

Tests all major salary configurations:
  - Basic salary (minimal fields)
  - Time range (age-based start, milestone end)
  - Monthly frequency
  - Change over time: increase with cap, match-inflation-plus, decrease, none
  - Tax: tax-exempt, no withholding, custom withhold %
  - Advanced tax: self-employment, dividend income, passive income
  - Part-time work (custom start/end/rate)
  - Defined benefit pension (all three payout types)
  - Full round-trip: export → parse as Salary → re-serialize → restore → re-export

Each case asserts data integrity via re-export, then pauses for browser
visual verification before cleanup.

Usage:
    CDP_PORT=9222 python tests/integration/test_salary_income.py
"""
from __future__ import annotations
import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "projectionlab_mcp"))

if not os.getenv("CDP_PORT"):
    print("ERROR: CDP_PORT is not set. Run with: CDP_PORT=9222 python tests/integration/test_salary_income.py")
    sys.exit(1)

from projectionlab_mcp import plugin_api as api
from projectionlab_mcp.models.income import Salary, NewSalary, IncomeTimeRef, IncomeYearlyChange

TAG = "TEST-SALARY-"
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


async def create_salary(plan_id: str, salary: Salary) -> None:
    """Insert a salary event into plan.income.events via restorePlans."""
    data = await api.export_data()
    plans = data.plans
    plan = api._find_plan(plans, plan_id)
    plan.setdefault("income", {}).setdefault("events", [])
    plan["income"]["events"].append(salary.model_dump(exclude_none=True))
    await api.restore_plans(plans)


async def delete_salary(plan_id: str, salary_id: str) -> None:
    data = await api.export_data()
    plans = data.plans
    plan = api._find_plan(plans, plan_id)
    events = plan.get("income", {}).get("events", [])
    remaining = [e for e in events if e.get("id") != salary_id]
    if len(remaining) == len(events):
        raise ValueError(f"Salary '{salary_id}' not found in plan '{plan_id}'.")
    plan["income"]["events"] = remaining
    await api.restore_plans(plans)


async def fetch_salary(plan_id: str, salary_id: str) -> dict:
    events = await _get_income_events(plan_id)
    for e in events:
        if e.get("id") == salary_id:
            return e
    raise ValueError(f"Salary '{salary_id}' not found after create.")


# ── test cases ────────────────────────────────────────────────────────────────

async def test_basic_salary(plan_id: str) -> str:
    """Minimal salary: just name, amount, owner. All defaults should persist."""
    section("TEST 1 — Basic Salary (minimal fields, all defaults)")
    s = NewSalary(name=f"{TAG}basic", amount=80000).to_salary()
    await create_salary(plan_id, s)

    raw = await fetch_salary(plan_id, s.id)
    assert_eq("type", raw["type"], "salary")
    assert_eq("name", raw["name"], f"{TAG}basic")
    assert_eq("title", raw["title"], f"{TAG}basic")
    assert_eq("owner", raw["owner"], "me")
    assert_approx("amount", raw["amount"], 80000)
    assert_eq("amountType", raw["amountType"], "today$")
    assert_eq("frequency", raw["frequency"], "yearly")
    assert_eq("start.type", raw["start"]["type"], "keyword")
    assert_eq("start.value", raw["start"]["value"], "beforeCurrentYear")
    assert_eq("end.type", raw["end"]["type"], "milestone")
    assert_eq("end.value", raw["end"]["value"], "retirement")
    assert_eq("yearlyChange.type", raw["yearlyChange"]["type"], "match-inflation")
    assert_eq("taxExempt", raw["taxExempt"], False)
    assert_eq("taxWithholding", raw["taxWithholding"], True)
    assert_approx("withhold", raw["withhold"], 25)
    assert_eq("selfEmployment", raw.get("selfEmployment", False), False)
    assert_eq("goPartTime", raw["goPartTime"], False)
    assert_eq("hasPension", raw["hasPension"], False)

    ok(f"Basic salary created: {s.id}")
    return s.id


async def test_age_based_time_range(plan_id: str) -> str:
    """Salary that starts at age 30 and ends at age 60 (age-based TimeRef)."""
    section("TEST 2 — Age-based Time Range")
    s = NewSalary(
        name=f"{TAG}age-range",
        amount=95000,
        start=IncomeTimeRef(type="age", value="30"),
        end=IncomeTimeRef(type="age", value="60"),
    ).to_salary()
    await create_salary(plan_id, s)

    raw = await fetch_salary(plan_id, s.id)
    assert_eq("start.type", raw["start"]["type"], "age")
    assert_eq("start.value", raw["start"]["value"], "30")
    assert_eq("end.type", raw["end"]["type"], "age")
    assert_eq("end.value", raw["end"]["value"], "60")

    ok(f"Age-range salary created: {s.id}")
    return s.id


async def test_monthly_frequency(plan_id: str) -> str:
    """Salary paid monthly instead of yearly."""
    section("TEST 3 — Monthly Frequency")
    s = NewSalary(
        name=f"{TAG}monthly",
        amount=7500,  # $7,500/month
        yearlyChange=IncomeYearlyChange(type="match-inflation"),
    ).to_salary()
    s.frequency = "monthly"
    await create_salary(plan_id, s)

    raw = await fetch_salary(plan_id, s.id)
    assert_eq("frequency", raw["frequency"], "monthly")
    assert_approx("amount", raw["amount"], 7500)

    ok(f"Monthly salary created: {s.id}")
    return s.id


async def test_yearly_change_increase_with_cap(plan_id: str) -> str:
    """Salary that increases 5%/year, capped at $200K in Today's Currency."""
    section("TEST 4 — Yearly Change: Increase 5%/yr with $200K Today's Currency cap")
    s = NewSalary(
        name=f"{TAG}increase-capped",
        amount=100000,
        yearlyChange=IncomeYearlyChange(
            type="increase",
            amount=5.0,
            limitEnabled=True,
            limit=200000,
            limitType="today$",
        ),
    ).to_salary()
    await create_salary(plan_id, s)

    raw = await fetch_salary(plan_id, s.id)
    yc = raw["yearlyChange"]
    assert_eq("yearlyChange.type", yc["type"], "increase")
    assert_approx("yearlyChange.amount", yc["amount"], 5.0)
    assert_eq("yearlyChange.limitEnabled", yc["limitEnabled"], True)
    assert_approx("yearlyChange.limit", yc["limit"], 200000)
    assert_eq("yearlyChange.limitType", yc["limitType"], "today$")

    ok(f"Increase-capped salary created: {s.id}")
    return s.id


async def test_yearly_change_match_inflation_plus(plan_id: str) -> str:
    """Salary that grows at inflation + 2% per year."""
    section("TEST 5 — Yearly Change: Match Inflation +2%")
    s = NewSalary(
        name=f"{TAG}inf-plus",
        amount=120000,
        yearlyChange=IncomeYearlyChange(type="match-inflation-plus", amount=2.0),
    ).to_salary()
    await create_salary(plan_id, s)

    raw = await fetch_salary(plan_id, s.id)
    yc = raw["yearlyChange"]
    assert_eq("yearlyChange.type", yc["type"], "match-inflation-plus")
    assert_approx("yearlyChange.amount", yc["amount"], 2.0)

    ok(f"Inflation+2% salary created: {s.id}")
    return s.id


async def test_yearly_change_decrease(plan_id: str) -> str:
    """Salary that decreases 3%/year (e.g., winding down consulting)."""
    section("TEST 6 — Yearly Change: Decrease 3%/yr")
    s = NewSalary(
        name=f"{TAG}decrease",
        amount=60000,
        yearlyChange=IncomeYearlyChange(type="decrease", amount=3.0),
    ).to_salary()
    await create_salary(plan_id, s)

    raw = await fetch_salary(plan_id, s.id)
    yc = raw["yearlyChange"]
    assert_eq("yearlyChange.type", yc["type"], "decrease")
    assert_approx("yearlyChange.amount", yc["amount"], 3.0)

    ok(f"Decreasing salary created: {s.id}")
    return s.id


async def test_yearly_change_none(plan_id: str) -> str:
    """Salary frozen in nominal terms (yearlyChange type=none)."""
    section("TEST 7 — Yearly Change: None (flat in nominal terms)")
    s = NewSalary(
        name=f"{TAG}frozen",
        amount=50000,
        yearlyChange=IncomeYearlyChange(type="none"),
    ).to_salary()
    await create_salary(plan_id, s)

    raw = await fetch_salary(plan_id, s.id)
    assert_eq("yearlyChange.type", raw["yearlyChange"]["type"], "none")

    ok(f"Frozen salary created: {s.id}")
    return s.id


async def test_tax_exempt(plan_id: str) -> str:
    """Tax-exempt income (e.g., some government stipends)."""
    section("TEST 8 — Tax: Tax-Exempt, No Withholding")
    s = NewSalary(
        name=f"{TAG}tax-exempt",
        amount=40000,
        taxExempt=True,
        taxWithholding=False,
    ).to_salary()
    await create_salary(plan_id, s)

    raw = await fetch_salary(plan_id, s.id)
    assert_eq("taxExempt", raw["taxExempt"], True)
    assert_eq("taxWithholding", raw["taxWithholding"], False)

    ok(f"Tax-exempt salary created: {s.id}")
    return s.id


async def test_custom_withholding(plan_id: str) -> str:
    """Salary with custom 35% withholding."""
    section("TEST 9 — Tax: Custom 35% Withholding")
    s = NewSalary(
        name=f"{TAG}withhold-35",
        amount=200000,
        taxWithholding=True,
        withhold=35.0,
    ).to_salary()
    await create_salary(plan_id, s)

    raw = await fetch_salary(plan_id, s.id)
    assert_eq("taxWithholding", raw["taxWithholding"], True)
    assert_approx("withhold", raw["withhold"], 35.0)

    ok(f"Custom-withhold salary created: {s.id}")
    return s.id


async def test_self_employment(plan_id: str) -> str:
    """Self-employment income flag (triggers SE tax in US estimator)."""
    section("TEST 10 — Advanced Tax: Self-Employment")
    s = NewSalary(
        name=f"{TAG}self-employed",
        amount=90000,
        selfEmployment=True,
        wage=False,
    ).to_salary()
    await create_salary(plan_id, s)

    raw = await fetch_salary(plan_id, s.id)
    assert_eq("selfEmployment", raw.get("selfEmployment"), True)
    # wage should be false (mutually exclusive)
    assert_eq("wage", raw.get("wage", False), False)

    ok(f"Self-employment salary created: {s.id}")
    return s.id


async def test_dividend_and_passive(plan_id: str) -> str:
    """Salary flagged as both dividend income and passive income."""
    section("TEST 11 — Advanced Tax: Dividend Income + Passive Income")
    s = NewSalary(
        name=f"{TAG}dividend-passive",
        amount=30000,
        isDividendIncome=True,
        isPassiveIncome=True,
    ).to_salary()
    await create_salary(plan_id, s)

    raw = await fetch_salary(plan_id, s.id)
    assert_eq("isDividendIncome", raw.get("isDividendIncome"), True)
    assert_eq("isPassiveIncome", raw.get("isPassiveIncome"), True)

    ok(f"Dividend+passive salary created: {s.id}")
    return s.id


async def test_part_time(plan_id: str) -> str:
    """Salary with a part-time period from age 55 to retirement at 50% rate."""
    section("TEST 12 — Part-Time: age 55 → retirement at 50%")
    s = NewSalary(
        name=f"{TAG}part-time",
        amount=150000,
        goPartTime=True,
        partTimeStart=IncomeTimeRef(type="age", value="55"),
        partTimeEnd=IncomeTimeRef(type="milestone", value="retirement"),
        partTimeRate=50.0,
    ).to_salary()
    await create_salary(plan_id, s)

    raw = await fetch_salary(plan_id, s.id)
    assert_eq("goPartTime", raw["goPartTime"], True)
    assert_eq("partTimeStart.type", raw["partTimeStart"]["type"], "age")
    assert_eq("partTimeStart.value", raw["partTimeStart"]["value"], "55")
    assert_eq("partTimeEnd.type", raw["partTimeEnd"]["type"], "milestone")
    assert_eq("partTimeEnd.value", raw["partTimeEnd"]["value"], "retirement")
    assert_approx("partTimeRate", raw["partTimeRate"], 50.0)

    ok(f"Part-time salary created: {s.id}")
    return s.id


async def test_pension_fap(plan_id: str) -> str:
    """Salary with defined-benefit pension — % of Final Average Pay type."""
    section("TEST 13 — Pension: 5% contribution, FAP 30% payout, tax-free payouts")
    s = NewSalary(
        name=f"{TAG}pension-fap",
        amount=110000,
        hasPension=True,
        pensionContribution=5.0,
        pensionContributionType="%",
        contribsReduceTaxableIncome=True,
        pensionPayoutsStart=IncomeTimeRef(type="milestone", value="retirement"),
        pensionPayoutsEnd=IncomeTimeRef(type="keyword", value="endOfPlan"),
        pensionPayoutType="fap",
        pensionPayoutRate=30.0,
        pensionPayoutsAreTaxFree=True,
    ).to_salary()
    await create_salary(plan_id, s)

    raw = await fetch_salary(plan_id, s.id)
    assert_eq("hasPension", raw["hasPension"], True)
    assert_approx("pensionContribution", raw["pensionContribution"], 5.0)
    assert_eq("pensionContributionType", raw["pensionContributionType"], "%")
    assert_eq("contribsReduceTaxableIncome", raw["contribsReduceTaxableIncome"], True)
    assert_eq("pensionPayoutType", raw["pensionPayoutType"], "fap")
    assert_approx("pensionPayoutRate", raw["pensionPayoutRate"], 30.0)
    assert_eq("pensionPayoutsAreTaxFree", raw["pensionPayoutsAreTaxFree"], True)
    assert_eq("pensionPayoutsStart.value", raw["pensionPayoutsStart"]["value"], "retirement")
    assert_eq("pensionPayoutsEnd.value", raw["pensionPayoutsEnd"]["value"], "endOfPlan")

    ok(f"Pension (FAP) salary created: {s.id}")
    return s.id


async def test_pension_fixed_amount(plan_id: str) -> str:
    """Salary with pension using fixed annual payout amount in Today's Currency."""
    section("TEST 14 — Pension: Fixed payout amount ($24K/yr in today's dollars)")
    s = NewSalary(
        name=f"{TAG}pension-fixed",
        amount=85000,
        hasPension=True,
        pensionContribution=3000,
        pensionContributionType="$",
        contribsReduceTaxableIncome=False,
        pensionPayoutType="fixed",
        pensionPayoutAmount=24000,
        pensionPayoutsAreTaxFree=False,
    ).to_salary()
    await create_salary(plan_id, s)

    raw = await fetch_salary(plan_id, s.id)
    assert_eq("pensionPayoutType", raw["pensionPayoutType"], "fixed")
    assert_approx("pensionPayoutAmount", raw["pensionPayoutAmount"], 24000)
    assert_eq("pensionContributionType", raw["pensionContributionType"], "$")
    assert_approx("pensionContribution", raw["pensionContribution"], 3000)
    assert_eq("contribsReduceTaxableIncome", raw["contribsReduceTaxableIncome"], False)

    ok(f"Pension (fixed amount) salary created: {s.id}")
    return s.id


async def test_round_trip(plan_id: str) -> str:
    """Full round-trip: create → export → parse as Salary → re-serialize → restore → re-export."""
    section("TEST 15 — Full Round-Trip: export → Salary.model_validate → re-serialize → re-import")

    # Create a feature-rich salary
    original = NewSalary(
        name=f"{TAG}round-trip",
        amount=130000,
        owner="me",
        start=IncomeTimeRef(type="keyword", value="beforeCurrentYear"),
        end=IncomeTimeRef(type="age", value="62"),
        yearlyChange=IncomeYearlyChange(type="increase", amount=3.0, limitEnabled=True, limit=180000),
        taxExempt=False,
        taxWithholding=True,
        withhold=28.0,
        selfEmployment=False,
        wage=True,
        goPartTime=True,
        partTimeStart=IncomeTimeRef(type="age", value="58"),
        partTimeEnd=IncomeTimeRef(type="age", value="62"),
        partTimeRate=40.0,
        hasPension=True,
        pensionContribution=4.0,
        pensionContributionType="%",
        pensionPayoutType="fap",
        pensionPayoutRate=25.0,
    ).to_salary()
    await create_salary(plan_id, original)

    # Step 1: Export and parse
    raw1 = await fetch_salary(plan_id, original.id)
    parsed = Salary.model_validate(raw1)

    assert_eq("round-trip name", parsed.name, f"{TAG}round-trip")
    assert_approx("round-trip amount", parsed.amount, 130000)
    assert_eq("round-trip end.type", parsed.end.type, "age")
    assert_eq("round-trip end.value", parsed.end.value, "62")
    assert_eq("round-trip yearlyChange.type", parsed.yearlyChange.type, "increase")
    assert_eq("round-trip goPartTime", parsed.goPartTime, True)
    assert_eq("round-trip hasPension", parsed.hasPension, True)

    # Step 2: Mutate one field and re-save
    parsed.amount = 135000
    parsed.withhold = 30.0

    data = await api.export_data()
    plans = data.plans
    plan = api._find_plan(plans, plan_id)
    events = plan.get("income", {}).get("events", [])
    for i, e in enumerate(events):
        if e.get("id") == original.id:
            events[i] = parsed.model_dump(exclude_none=True)
            break
    await api.restore_plans(plans)

    # Step 3: Re-export and verify mutation persisted
    raw2 = await fetch_salary(plan_id, original.id)
    assert_approx("mutated amount", raw2["amount"], 135000)
    assert_approx("mutated withhold", raw2["withhold"], 30.0)
    # Unchanged fields should still be there
    assert_eq("unchanged goPartTime", raw2["goPartTime"], True)
    assert_eq("unchanged partTimeRate", raw2["partTimeRate"], 40.0)

    ok(f"Round-trip salary created: {original.id}")
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
        test_basic_salary,
        test_age_based_time_range,
        test_monthly_frequency,
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
            salary_id = await test_fn(plan_id)
            created_ids.append(salary_id)
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
    print(f"  {len(created_ids)} salary events created (look for '{TAG}' prefix in Income section):")
    for sid in created_ids:
        print(f"    - {sid}")

    input("\n  Press ENTER after browser verification to DELETE all test data...")

    section("Cleanup")
    for sid in created_ids:
        try:
            await delete_salary(plan_id, sid)
            ok(f"Deleted salary {sid}")
        except Exception as e:
            print(f"  ✗ Could not delete {sid}: {e}")

    section("Done")


if __name__ == "__main__":
    asyncio.run(main())
