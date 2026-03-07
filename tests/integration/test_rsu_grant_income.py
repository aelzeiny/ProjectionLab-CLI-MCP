"""
Integration test — RSU Grant income CRUD and field serialization.

Tests all major RSU grant configurations:
  - Basic once grant (minimal fields, all defaults)
  - Actual-dollar amount type
  - Age-based timing
  - Milestone timing (custom start)
  - Recurring frequency (once-per-year with start/end range)
  - Change over time: increase, match-inflation-plus
  - Tax: tax-exempt, no withholding, custom withhold %
  - Advanced tax flags: self-employment, wage, dividend, passive
  - Recurrence (repeat=True with interval, scaler, repeatEnd)
  - Recurrence with scaler scaling up each time
  - Full round-trip: export → parse as RsuGrant → re-serialize → restore → re-export

Each case asserts data integrity via re-export, then pauses for browser
visual verification before cleanup.

Usage:
    CDP_PORT=9222 python tests/integration/test_rsu_grant_income.py
"""
from __future__ import annotations
import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "projectionlab_mcp"))

if not os.getenv("CDP_PORT"):
    print("ERROR: CDP_PORT is not set. Run with: CDP_PORT=9222 python tests/integration/test_rsu_grant_income.py")
    sys.exit(1)

from projectionlab_mcp import plugin_api as api
from projectionlab_mcp.models.income import (
    RsuGrant, NewRsuGrant, IncomeTimeRef, IncomeYearlyChange,
)

TAG = "TEST-RSU-"
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


async def create_grant(plan_id: str, grant: RsuGrant) -> None:
    """Insert an RSU grant event into plan.income.events via restorePlans."""
    data = await api.export_data()
    plans = data.plans
    plan = api._find_plan(plans, plan_id)
    plan.setdefault("income", {}).setdefault("events", [])
    plan["income"]["events"].append(grant.model_dump(exclude_none=True))
    await api.restore_plans(plans)


async def delete_grant(plan_id: str, grant_id: str) -> None:
    data = await api.export_data()
    plans = data.plans
    plan = api._find_plan(plans, plan_id)
    events = plan.get("income", {}).get("events", [])
    remaining = [e for e in events if e.get("id") != grant_id]
    if len(remaining) == len(events):
        raise ValueError(f"Grant '{grant_id}' not found in plan '{plan_id}'.")
    plan["income"]["events"] = remaining
    await api.restore_plans(plans)


async def fetch_grant(plan_id: str, grant_id: str) -> dict:
    events = await _get_income_events(plan_id)
    for e in events:
        if e.get("id") == grant_id:
            return e
    raise ValueError(f"Grant '{grant_id}' not found after create.")


# ── test cases ────────────────────────────────────────────────────────────────

async def test_basic_once_grant(plan_id: str) -> str:
    """Minimal once grant: name + amount, all defaults."""
    section("TEST 1 — Basic Once Grant (minimal fields, all defaults)")
    g = NewRsuGrant(name=f"{TAG}basic", amount=50000).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    assert_eq("type", raw["type"], "rsu")
    assert_eq("name", raw["name"], f"{TAG}basic")
    assert_eq("title", raw["title"], "RSU Grant")
    assert_eq("icon", raw["icon"], "mdi-finance")
    assert_eq("owner", raw["owner"], "me")
    assert_approx("amount", raw["amount"], 50000)
    assert_eq("amountType", raw["amountType"], "today$")
    assert_eq("frequency", raw["frequency"], "once")
    assert_eq("frequencyChoices", raw["frequencyChoices"], True)
    assert_eq("start.type", raw["start"]["type"], "keyword")
    assert_eq("start.value", raw["start"]["value"], "now")
    assert_eq("start.modifier", raw["start"]["modifier"], "include")
    assert_eq("end.type", raw["end"]["type"], "milestone")
    assert_eq("end.value", raw["end"]["value"], "retirement")
    assert_eq("end.modifier", raw["end"]["modifier"], "exclude")
    assert_eq("yearlyChange.type", raw["yearlyChange"]["type"], "none")
    assert_eq("taxExempt", raw["taxExempt"], False)
    assert_eq("taxWithholding", raw["taxWithholding"], True)
    assert_approx("withhold", raw["withhold"], 30.0)
    assert_eq("repeat", raw["repeat"], False)

    ok(f"Basic grant created: {g.id}")
    return g.id


async def test_actual_dollar_amount(plan_id: str) -> str:
    """Grant entered in nominal (actual$) dollars."""
    section("TEST 2 — Actual$ Amount Type")
    g = NewRsuGrant(
        name=f"{TAG}actual-dollar",
        amount=120000,
        amountType="actual$",
    ).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    assert_eq("amountType", raw["amountType"], "actual$")
    assert_approx("amount", raw["amount"], 120000)

    ok(f"Actual-dollar grant created: {g.id}")
    return g.id


async def test_age_based_timing(plan_id: str) -> str:
    """Once grant that vests at age 35."""
    section("TEST 3 — Age-based Timing (vests at age 35)")
    g = NewRsuGrant(
        name=f"{TAG}age-timing",
        amount=80000,
        start=IncomeTimeRef(type="age", value="35"),
    ).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    assert_eq("start.type", raw["start"]["type"], "age")
    assert_eq("start.value", raw["start"]["value"], "35")

    ok(f"Age-timing grant created: {g.id}")
    return g.id


async def test_milestone_timing(plan_id: str) -> str:
    """Once grant timed to the FI milestone."""
    section("TEST 4 — Milestone Timing (vests at FI milestone)")
    g = NewRsuGrant(
        name=f"{TAG}fi-timing",
        amount=200000,
        start=IncomeTimeRef(type="milestone", value="fi"),
    ).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    assert_eq("start.type", raw["start"]["type"], "milestone")
    assert_eq("start.value", raw["start"]["value"], "fi")

    ok(f"FI-timing grant created: {g.id}")
    return g.id


async def test_recurring_once_per_year(plan_id: str) -> str:
    """Annual lump-sum RSU grant (once-per-year) from now until retirement."""
    section("TEST 5 — Recurring: once-per-year from now to retirement")
    g = NewRsuGrant(
        name=f"{TAG}annual",
        amount=100000,
        frequency="once-per-year",
        start=IncomeTimeRef(type="keyword", value="beforeCurrentYear"),
        end=IncomeTimeRef(type="milestone", value="retirement", modifier="exclude"),
    ).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    assert_eq("frequency", raw["frequency"], "once-per-year")
    assert_eq("start.value", raw["start"]["value"], "beforeCurrentYear")
    assert_eq("end.type", raw["end"]["type"], "milestone")
    assert_eq("end.value", raw["end"]["value"], "retirement")
    assert_eq("end.modifier", raw["end"]["modifier"], "exclude")

    ok(f"Annual grant created: {g.id}")
    return g.id


async def test_yearly_frequency(plan_id: str) -> str:
    """Yearly RSU (spread throughout year) from age 30 to age 50."""
    section("TEST 6 — Yearly Frequency (age 30 → 50)")
    g = NewRsuGrant(
        name=f"{TAG}yearly",
        amount=60000,
        frequency="yearly",
        start=IncomeTimeRef(type="age", value="30"),
        end=IncomeTimeRef(type="age", value="50"),
    ).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    assert_eq("frequency", raw["frequency"], "yearly")
    assert_eq("start.type", raw["start"]["type"], "age")
    assert_eq("start.value", raw["start"]["value"], "30")
    assert_eq("end.type", raw["end"]["type"], "age")
    assert_eq("end.value", raw["end"]["value"], "50")

    ok(f"Yearly grant created: {g.id}")
    return g.id


async def test_yearly_change_increase(plan_id: str) -> str:
    """Once-per-year grant with 5%/year increase."""
    section("TEST 7 — Change Over Time: Increase 5%/yr")
    g = NewRsuGrant(
        name=f"{TAG}increase",
        amount=75000,
        frequency="once-per-year",
        yearlyChange=IncomeYearlyChange(type="increase", amount=5.0),
    ).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    yc = raw["yearlyChange"]
    assert_eq("yearlyChange.type", yc["type"], "increase")
    assert_approx("yearlyChange.amount", yc["amount"], 5.0)

    ok(f"Increase grant created: {g.id}")
    return g.id


async def test_yearly_change_match_inflation_plus(plan_id: str) -> str:
    """Once-per-year grant growing at inflation +2%."""
    section("TEST 8 — Change Over Time: Match Inflation +2%")
    g = NewRsuGrant(
        name=f"{TAG}inf-plus",
        amount=90000,
        frequency="once-per-year",
        yearlyChange=IncomeYearlyChange(type="match-inflation-plus", amount=2.0),
    ).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    yc = raw["yearlyChange"]
    assert_eq("yearlyChange.type", yc["type"], "match-inflation-plus")
    assert_approx("yearlyChange.amount", yc["amount"], 2.0)

    ok(f"Inflation+2% grant created: {g.id}")
    return g.id


async def test_tax_exempt(plan_id: str) -> str:
    """Tax-exempt RSU grant with no withholding."""
    section("TEST 9 — Tax: Tax-Exempt, No Withholding")
    g = NewRsuGrant(
        name=f"{TAG}tax-exempt",
        amount=50000,
        taxExempt=True,
        taxWithholding=False,
    ).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    assert_eq("taxExempt", raw["taxExempt"], True)
    assert_eq("taxWithholding", raw["taxWithholding"], False)

    ok(f"Tax-exempt grant created: {g.id}")
    return g.id


async def test_custom_withholding(plan_id: str) -> str:
    """RSU grant with 40% withholding (higher than 30% default)."""
    section("TEST 10 — Tax: Custom 40% Withholding")
    g = NewRsuGrant(
        name=f"{TAG}withhold-40",
        amount=150000,
        withhold=40.0,
    ).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    assert_eq("taxWithholding", raw["taxWithholding"], True)
    assert_approx("withhold", raw["withhold"], 40.0)

    ok(f"Custom-withhold grant created: {g.id}")
    return g.id


async def test_advanced_tax_wage(plan_id: str) -> str:
    """RSU grant flagged as wage income."""
    section("TEST 11 — Advanced Tax: Wage Income")
    g = NewRsuGrant(
        name=f"{TAG}wage",
        amount=50000,
        wage=True,
        selfEmployment=False,
    ).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    assert_eq("wage", raw.get("wage"), True)
    assert_eq("selfEmployment", raw.get("selfEmployment"), False)

    ok(f"Wage grant created: {g.id}")
    return g.id


async def test_advanced_tax_dividend_passive(plan_id: str) -> str:
    """RSU grant flagged as dividend + passive income."""
    section("TEST 12 — Advanced Tax: Dividend + Passive Income")
    g = NewRsuGrant(
        name=f"{TAG}div-passive",
        amount=50000,
        isDividendIncome=True,
        isPassiveIncome=True,
    ).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    assert_eq("isDividendIncome", raw.get("isDividendIncome"), True)
    assert_eq("isPassiveIncome", raw.get("isPassiveIncome"), True)

    ok(f"Dividend+passive grant created: {g.id}")
    return g.id


async def test_recurrence_basic(plan_id: str) -> str:
    """Once grant that repeats every 1 year until end of plan."""
    section("TEST 13 — Recurrence: repeat every 1 year until End of Plan")
    g = NewRsuGrant(
        name=f"{TAG}repeat-basic",
        amount=75000,
        repeat=True,
        repeatInterval=1,
        repeatEnd=IncomeTimeRef(type="keyword", value="endOfPlan", modifier="include"),
    ).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    assert_eq("repeat", raw["repeat"], True)
    assert_eq("repeatIntervalType", raw["repeatIntervalType"], "between")
    assert_eq("repeatInterval", raw["repeatInterval"], 1)
    assert_eq("repeatEnd.type", raw["repeatEnd"]["type"], "keyword")
    assert_eq("repeatEnd.value", raw["repeatEnd"]["value"], "endOfPlan")
    assert_eq("repeatEnd.modifier", raw["repeatEnd"]["modifier"], "include")

    ok(f"Recurrence (basic) grant created: {g.id}")
    return g.id


async def test_recurrence_with_scaler(plan_id: str) -> str:
    """Once grant repeating every 2 years, scaling up 10% each time."""
    section("TEST 14 — Recurrence: every 2 years, +10% scaler, until retirement")
    g = NewRsuGrant(
        name=f"{TAG}repeat-scaler",
        amount=100000,
        repeat=True,
        repeatInterval=2,
        repeatScaler=10.0,
        repeatEnd=IncomeTimeRef(type="milestone", value="retirement", modifier="exclude"),
    ).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    assert_eq("repeat", raw["repeat"], True)
    assert_eq("repeatIntervalType", raw["repeatIntervalType"], "between")
    assert_eq("repeatInterval", raw["repeatInterval"], 2)
    assert_approx("repeatScaler", raw["repeatScaler"], 10.0)
    assert_eq("repeatEnd.value", raw["repeatEnd"]["value"], "retirement")
    assert_eq("repeatEnd.modifier", raw["repeatEnd"]["modifier"], "exclude")

    ok(f"Recurrence+scaler grant created: {g.id}")
    return g.id


async def test_spouse_owner(plan_id: str) -> str:
    """RSU grant owned by spouse."""
    section("TEST 15 — Spouse Owner")
    g = NewRsuGrant(
        name=f"{TAG}spouse",
        amount=60000,
        owner="spouse",
    ).to_rsu_grant()
    await create_grant(plan_id, g)

    raw = await fetch_grant(plan_id, g.id)
    assert_eq("owner", raw["owner"], "spouse")

    ok(f"Spouse grant created: {g.id}")
    return g.id


async def test_round_trip(plan_id: str) -> str:
    """Full round-trip: create → export → parse as RsuGrant → mutate → re-save → re-export."""
    section("TEST 16 — Full Round-Trip: export → RsuGrant.model_validate → mutate → re-import")

    original = NewRsuGrant(
        name=f"{TAG}round-trip",
        amount=125000,
        frequency="once-per-year",
        owner="me",
        start=IncomeTimeRef(type="keyword", value="beforeCurrentYear"),
        end=IncomeTimeRef(type="milestone", value="retirement", modifier="exclude"),
        yearlyChange=IncomeYearlyChange(type="increase", amount=3.0),
        taxExempt=False,
        taxWithholding=True,
        withhold=35.0,
        isDividendIncome=True,
        repeat=True,
        repeatInterval=1,
        repeatScaler=5.0,
        repeatEnd=IncomeTimeRef(type="keyword", value="endOfPlan", modifier="include"),
    ).to_rsu_grant()
    await create_grant(plan_id, original)

    # Step 1: Export and parse
    raw1 = await fetch_grant(plan_id, original.id)
    parsed = RsuGrant.model_validate(raw1)

    assert_eq("round-trip name", parsed.name, f"{TAG}round-trip")
    assert_approx("round-trip amount", parsed.amount, 125000)
    assert_eq("round-trip frequency", parsed.frequency, "once-per-year")
    assert_eq("round-trip yearlyChange.type", parsed.yearlyChange.type, "increase")
    assert_approx("round-trip yearlyChange.amount", parsed.yearlyChange.amount, 3.0)
    assert_approx("round-trip withhold", parsed.withhold, 35.0)
    assert_eq("round-trip repeat", parsed.repeat, True)
    assert_eq("round-trip repeatInterval", parsed.repeatInterval, 1)
    assert_approx("round-trip repeatScaler", parsed.repeatScaler, 5.0)
    assert_eq("round-trip isDividendIncome", parsed.isDividendIncome, True)

    # Step 2: Mutate and re-save
    parsed.amount = 150000
    parsed.withhold = 38.0
    parsed.repeatScaler = 7.5

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
    raw2 = await fetch_grant(plan_id, original.id)
    assert_approx("mutated amount", raw2["amount"], 150000)
    assert_approx("mutated withhold", raw2["withhold"], 38.0)
    assert_approx("mutated repeatScaler", raw2["repeatScaler"], 7.5)
    # Unchanged fields should still be intact
    assert_eq("unchanged frequency", raw2["frequency"], "once-per-year")
    assert_eq("unchanged repeat", raw2["repeat"], True)
    assert_eq("unchanged repeatInterval", raw2["repeatInterval"], 1)
    assert_eq("unchanged isDividendIncome", raw2.get("isDividendIncome"), True)

    ok(f"Round-trip grant created: {original.id}")
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
        test_basic_once_grant,
        test_actual_dollar_amount,
        test_age_based_timing,
        test_milestone_timing,
        test_recurring_once_per_year,
        test_yearly_frequency,
        test_yearly_change_increase,
        test_yearly_change_match_inflation_plus,
        test_tax_exempt,
        test_custom_withholding,
        test_advanced_tax_wage,
        test_advanced_tax_dividend_passive,
        test_recurrence_basic,
        test_recurrence_with_scaler,
        test_spouse_owner,
        test_round_trip,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            grant_id = await test_fn(plan_id)
            created_ids.append(grant_id)
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
    print(f"  {len(created_ids)} RSU grants created (look for '{TAG}' prefix in Income section):")
    for gid in created_ids:
        print(f"    - {gid}")

    input("\n  Press ENTER after browser verification to DELETE all test data...")

    section("Cleanup")
    for gid in created_ids:
        try:
            await delete_grant(plan_id, gid)
            ok(f"Deleted grant {gid}")
        except Exception as e:
            print(f"  ✗ Could not delete {gid}: {e}")

    section("Done")


if __name__ == "__main__":
    asyncio.run(main())
