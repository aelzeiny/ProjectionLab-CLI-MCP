"""
Integration test — priority CRUD, all types.

Creates test accounts and priorities of every type (both with new accounts and
with existing accounts where available), prints a summary for browser-based
visual verification, then deletes everything created.

Usage:
    CDP_PORT=9222 python tests/integration/test_priorities.py
"""
from __future__ import annotations
import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)
# Also insert the package dir so bare `import models` inside plugin_api works
sys.path.insert(0, os.path.join(PROJECT_ROOT, "projectionlab_mcp"))

if not os.getenv("CDP_PORT"):
    print("ERROR: CDP_PORT is not set.")
    sys.exit(1)

from projectionlab_mcp import plugin_api as api
import models

# ── helpers ──────────────────────────────────────────────────────────────────

TAG = "TEST-PRIORITY-"  # prefix all test entity names so cleanup is safe


async def create_real_asset(asset: models.BaseAsset) -> None:
    data = await api.export_data()
    today = data.today.model_dump(by_alias=True)
    today["assets"].append(asset.model_dump(exclude_none=True))
    await api.restore_current_finances(today)


async def delete_real_asset(asset_id: str) -> None:
    data = await api.export_data()
    remaining = [a for a in data.today.assets if a.id != asset_id]
    today = data.today.model_dump(by_alias=True)
    today["assets"] = [a.model_dump(exclude_none=True) for a in remaining]
    await api.restore_current_finances(today)


async def create_debt(debt: models.BaseDebt) -> None:
    data = await api.export_data()
    today = data.today.model_dump(by_alias=True)
    today["debts"].append(debt.model_dump(exclude_none=True))
    await api.restore_current_finances(today)


async def delete_debt(debt_id: str) -> None:
    data = await api.export_data()
    remaining = [d for d in data.today.debts if d.id != debt_id]
    today = data.today.model_dump(by_alias=True)
    today["debts"] = [d.model_dump(exclude_none=True) for d in remaining]
    await api.restore_current_finances(today)


def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def section(msg: str) -> None:
    print(f"\n{'─'*60}\n  {msg}\n{'─'*60}")


# ── main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    # ── 0. Find the active plan ───────────────────────────────────────────────
    section("0. Finding active plan")
    plans = await api.list_plans()
    active = next((p for p in plans if p.get("active")), plans[0])
    plan_id = active["id"]
    print(f"  Active plan: {active['name']} ({plan_id})")

    # Read existing accounts for "existing account" test cases
    data = await api.export_data()
    existing_savings = data.today.savingsAccounts
    existing_investments = data.today.investmentAccounts
    existing_debts = data.today.debts
    existing_assets = data.today.assets

    print(f"  Existing: {len(existing_savings)} savings, {len(existing_investments)} investments, "
          f"{len(existing_debts)} debts, {len(existing_assets)} assets")

    # ── 1. Create test accounts ───────────────────────────────────────────────
    section("1. Creating test accounts")

    # Savings account
    new_savings = models.NewSavingsAccount(
        name=f"{TAG}savings",
        title="[Test] Emergency Savings",
        owner="me",
        balance=10000.0,
    )
    await api.create_savings_account(new_savings)
    ok(f"Savings account created: {new_savings.id}")

    # Taxable investment account
    new_taxable = models.TaxableInvestmentAccount(
        name=f"{TAG}taxable",
        title="[Test] Taxable Brokerage",
        owner="me",
        balance=50000.0,
    )
    await api.create_investment_account(new_taxable)
    ok(f"Taxable account created: {new_taxable.id}")

    # Roth IRA
    new_roth = models.RothIRAInvestmentAccount(
        name=f"{TAG}roth",
        title="[Test] Roth IRA",
        owner="me",
        balance=25000.0,
    )
    await api.create_investment_account(new_roth)
    ok(f"Roth IRA created: {new_roth.id}")

    # Financed real estate asset (needed for NewAssetLoanPriority)
    new_home = models.RealEstateAsset(
        name=f"{TAG}home",
        title="[Test] Financed Home",
        owner="me",
        initialValue=400000.0,
        amount=420000.0,
        paymentMethod="financed",
        balance=320000.0,
        monthlyPayment=2000.0,
        interestRate=6.5,
    )
    await create_real_asset(new_home)
    ok(f"Financed real estate created: {new_home.id}")

    # Credit card debt
    new_cc = models.GenericDebt(
        name=f"{TAG}credit-card",
        title="[Test] Credit Card",
        owner="me",
        type="debt",
        amount=8000.0,
        monthlyPayment=300.0,
        interestRate=22.0,
        icon="mdi-credit-card",
        color="red-lighten-1",
    )
    await create_debt(new_cc)
    ok(f"Credit card debt created: {new_cc.id}")

    # Student loan debt
    new_student = models.StudentLoansDebt(
        name=f"{TAG}student-loan",
        title="[Test] Student Loan",
        owner="me",
        subtype="student-loans",
        amount=30000.0,
        monthlyPayment=400.0,
        interestRate=5.5,
        icon="mdi-school",
    )
    await create_debt(new_student)
    ok(f"Student loan created: {new_student.id}")

    # ── 2. Create priorities — every type ─────────────────────────────────────
    section("2. Creating priorities")

    created_priority_ids: list[str] = []

    async def make(priority) -> str:
        p = await api.create_priority(plan_id, priority)
        created_priority_ids.append(p.id)
        ok(f"{p.type!r:20s} '{p.name}' → {p.id}")
        return p.id

    # 2a. Cash — emergency-fund — new savings account
    await make(models.NewCashPriority(
        name="[Test] Emergency Fund (new account)",
        accountId=new_savings.id,
        type="emergency-fund",
        amount=10000.0,
    ))

    # 2b. Cash — cash-reserves — existing savings account (if any, else new)
    cash_acct_id = existing_savings[0].id if existing_savings else new_savings.id
    cash_acct_label = "existing" if existing_savings else "same new"
    await make(models.NewCashPriority(
        name=f"[Test] Cash Reserves ({cash_acct_label} account)",
        accountId=cash_acct_id,
        type="cash-reserves",
        amount=5000.0,
    ))

    # 2c. Investment — taxable — new account
    await make(models.NewInvestmentPriority(
        name="[Test] Taxable Brokerage (new account)",
        accountId=new_taxable.id,
        type="taxable",
    ))

    # 2d. Investment — roth — new account
    await make(models.NewInvestmentPriority(
        name="[Test] Roth IRA (new account)",
        accountId=new_roth.id,
        type="roth-ira",
    ))

    # 2e. Investment — existing investment account (if any)
    if existing_investments:
        ex_inv = existing_investments[0]
        await make(models.NewInvestmentPriority(
            name=f"[Test] {ex_inv.type.upper()} (existing account)",
            accountId=ex_inv.id,
            type=ex_inv.type,
        ))

    # 2f. Asset loan — financed real estate — new asset
    await make(models.NewAssetLoanPriority(
        name="[Test] Extra Mortgage Payments (new asset)",
        assetId=new_home.id,
        extra=500.0,
    ))

    # 2g. Debt — credit card — new debt
    await make(models.NewDebtPriority(
        name="[Test] Credit Card Payoff (new debt)",
        accountId=new_cc.id,
        type="credit-card",
    ))

    # 2h. Debt — student loans — new debt
    await make(models.NewDebtPriority(
        name="[Test] Student Loan Payoff (new debt)",
        accountId=new_student.id,
        type="student-loans",
    ))

    # 2i. Debt — existing debt (if any)
    if existing_debts:
        ex_debt = existing_debts[0]
        await make(models.NewDebtPriority(
            name=f"[Test] Existing Debt (existing account)",
            accountId=ex_debt.id,
            type=ex_debt.type,
        ))

    # 2j. Transfer — from new savings to new taxable
    await make(models.NewTransferPriority(
        name="[Test] Savings → Taxable Transfer",
        fromAccountId=new_savings.id,
        toAccountId=new_taxable.id,
        amount=1000.0,
        amountType="today$",
        frequency="yearly",
    ))

    # ── 3. Summary for visual verification ────────────────────────────────────
    section("3. Summary — verify in browser, then cleanup runs automatically")
    print(f"  Plan ID : {plan_id}")
    print(f"  Plan URL: https://app.projectionlab.com/plan/{plan_id}")
    print(f"\n  {len(created_priority_ids)} priorities created:")
    for pid in created_priority_ids:
        print(f"    - {pid}")

    # ── 4. Cleanup ────────────────────────────────────────────────────────────
    section("4. Cleanup")
    input("  Press ENTER after verifying in the browser to delete test data...")

    # Delete priorities
    for pid in created_priority_ids:
        try:
            await api.delete_priority(plan_id, pid)
            ok(f"Deleted priority {pid}")
        except Exception as e:
            print(f"  ✗ Could not delete priority {pid}: {e}")

    # Delete test accounts
    try:
        await api.delete_savings_account(new_savings.id)
        ok(f"Deleted savings account {new_savings.id}")
    except Exception as e:
        print(f"  ✗ {e}")

    try:
        await api.delete_investment_account(new_taxable.id)
        ok(f"Deleted taxable account {new_taxable.id}")
    except Exception as e:
        print(f"  ✗ {e}")

    try:
        await api.delete_investment_account(new_roth.id)
        ok(f"Deleted roth account {new_roth.id}")
    except Exception as e:
        print(f"  ✗ {e}")

    try:
        await delete_real_asset(new_home.id)
        ok(f"Deleted real estate asset {new_home.id}")
    except Exception as e:
        print(f"  ✗ {e}")

    try:
        await delete_debt(new_cc.id)
        ok(f"Deleted credit card debt {new_cc.id}")
    except Exception as e:
        print(f"  ✗ {e}")

    try:
        await delete_debt(new_student.id)
        ok(f"Deleted student loan debt {new_student.id}")
    except Exception as e:
        print(f"  ✗ {e}")

    section("Done")


if __name__ == "__main__":
    asyncio.run(main())
