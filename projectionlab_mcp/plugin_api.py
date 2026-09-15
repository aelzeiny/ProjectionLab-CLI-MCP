import json
import os
from dotenv import load_dotenv
from .browser import get_page
from . import models
from .reports import Report, REPORTS, list_reports, resolve_report, download_report  # noqa: F401  (re-exported)

load_dotenv()

API_KEY = os.getenv("PROJECTIONLAB_API_KEY", "")


async def _call(method: str, *args, **opts) -> object:
    page = await get_page()
    options = json.dumps({**opts, "key": API_KEY})
    script = (
        f"async () => {{"
        f"  const args = {json.dumps(list(args))};"
        f"  return await window.projectionlabPluginAPI.{method}(...args, {options});"
        f"}}"
    )
    try:
        return await page.evaluate(script)
    except Exception as e:
        if "projectionlabPluginAPI" in str(e) or "Cannot read properties of undefined" in str(e):
            raise RuntimeError(
                "window.projectionlabPluginAPI is not available. "
                "Enable plugins in ProjectionLab Account Settings and ensure PROJECTIONLAB_API_KEY is set."
            ) from e
        raise


async def export_data() -> models.PLExport:
    raw = await _call("exportData")
    return models.PLExport.model_validate(raw)


async def update_account(account_id: str, data: dict, force: bool = False) -> None:
    await _call("updateAccount", account_id, data, force=force)


async def restore_current_finances(new_state: dict) -> None:
    await _call("restoreCurrentFinances", new_state)


async def restore_plans(new_plans: object) -> None:
    await _call("restorePlans", new_plans)


async def restore_progress(new_progress: dict) -> None:
    await _call("restoreProgress", new_progress)


async def restore_settings(new_settings: dict) -> None:
    await _call("restoreSettings", new_settings)


async def validate_api_key() -> None:
    await _call("validateApiKey")


# --- Savings CRUD ---

async def list_savings_accounts() -> list[models.SavingsAccount]:
    data = await export_data()
    return data.today.savingsAccounts


async def get_savings_account(account_id: str) -> models.SavingsAccount:
    data = await export_data()
    for acct in data.today.savingsAccounts:
        if acct.id == account_id:
            return acct
    raise ValueError(f"Savings account '{account_id}' not found.")


async def create_savings_account(account: models.NewSavingsAccount) -> models.SavingsAccount:
    data = await export_data()
    today = data.today.model_dump(by_alias=True)
    today["savingsAccounts"].append(account.model_dump())
    await restore_current_finances(today)
    return models.SavingsAccount(**account.model_dump())


async def delete_savings_account(account_id: str) -> None:
    data = await export_data()
    remaining = [a for a in data.today.savingsAccounts if a.id != account_id]
    if len(remaining) == len(data.today.savingsAccounts):
        raise ValueError(f"Savings account '{account_id}' not found.")
    today = data.today.model_dump(by_alias=True)
    today["savingsAccounts"] = [a.model_dump() for a in remaining]
    await restore_current_finances(today)


# --- Investment CRUD ---

async def list_investment_accounts() -> list[models.InvestmentAccount]:
    data = await export_data()
    return data.today.investmentAccounts


async def get_investment_account(account_id: str) -> models.InvestmentAccount:
    data = await export_data()
    for acct in data.today.investmentAccounts:
        if acct.id == account_id:
            return acct
    raise ValueError(f"Investment account '{account_id}' not found.")


async def create_investment_account(account: models.BaseInvestmentAccount) -> models.BaseInvestmentAccount:
    data = await export_data()
    today = data.today.model_dump(by_alias=True)
    today["investmentAccounts"].append(account.model_dump(exclude_none=True))
    await restore_current_finances(today)
    return account


async def delete_investment_account(account_id: str) -> None:
    data = await export_data()
    remaining = [a for a in data.today.investmentAccounts if a.id != account_id]
    if len(remaining) == len(data.today.investmentAccounts):
        raise ValueError(f"Investment account '{account_id}' not found.")
    today = data.today.model_dump(by_alias=True)
    today["investmentAccounts"] = [a.model_dump(exclude_none=True) for a in remaining]
    await restore_current_finances(today)


# --- Helpers ---

def _find_plan(plans: list, plan_id: str) -> dict:
    for plan in plans:
        if plan.get("id") == plan_id:
            return plan
    raise ValueError(f"Plan '{plan_id}' not found.")


# --- Milestone CRUD ---

async def list_milestones(plan_id: str) -> list[models.Milestone]:
    data = await export_data()
    plan = _find_plan(data.plans, plan_id)
    return [models.Milestone.model_validate(m) for m in plan.get("milestones", [])]


async def get_milestone(plan_id: str, milestone_id: str) -> models.Milestone:
    milestones = await list_milestones(plan_id)
    for m in milestones:
        if m.id == milestone_id:
            return m
    raise ValueError(f"Milestone '{milestone_id}' not found in plan '{plan_id}'.")


async def create_milestone(plan_id: str, milestone: models.NewMilestone) -> models.Milestone:
    data = await export_data()
    plans = data.plans  # list of raw dicts
    plan = _find_plan(plans, plan_id)
    plan.setdefault("milestones", [])
    plan["milestones"].append(milestone.model_dump(exclude_none=True))
    await restore_plans(plans)
    return models.Milestone.model_validate(milestone.model_dump(exclude_none=True))


async def update_milestone(plan_id: str, milestone_id: str, updates: dict) -> models.Milestone:
    data = await export_data()
    plans = data.plans
    plan = _find_plan(plans, plan_id)
    milestones = plan.get("milestones", [])
    for m in milestones:
        if m.get("id") == milestone_id:
            m.update(updates)
            await restore_plans(plans)
            return models.Milestone.model_validate(m)
    raise ValueError(f"Milestone '{milestone_id}' not found in plan '{plan_id}'.")


async def delete_milestone(plan_id: str, milestone_id: str) -> None:
    data = await export_data()
    plans = data.plans
    plan = _find_plan(plans, plan_id)
    milestones = plan.get("milestones", [])
    remaining = [m for m in milestones if m.get("id") != milestone_id]
    if len(remaining) == len(milestones):
        raise ValueError(f"Milestone '{milestone_id}' not found in plan '{plan_id}'.")
    plan["milestones"] = remaining
    await restore_plans(plans)


# --- Real Asset CRUD ---

async def list_real_assets() -> list:
    data = await export_data()
    return data.today.assets


async def get_real_asset(asset_id: str):
    data = await export_data()
    for a in data.today.assets:
        if a.id == asset_id:
            return a
    raise ValueError(f"Real asset '{asset_id}' not found.")


async def create_real_asset(asset: models.BaseAsset):
    data = await export_data()
    today = data.today.model_dump(by_alias=True)
    today["assets"].append(asset.model_dump(exclude_none=True))
    await restore_current_finances(today)
    return asset


async def delete_real_asset(asset_id: str) -> None:
    data = await export_data()
    remaining = [a for a in data.today.assets if a.id != asset_id]
    if len(remaining) == len(data.today.assets):
        raise ValueError(f"Real asset '{asset_id}' not found.")
    today = data.today.model_dump(by_alias=True)
    today["assets"] = [a.model_dump(exclude_none=True) for a in remaining]
    await restore_current_finances(today)


# --- Unsecured Debt CRUD ---

async def list_unsecured_debts() -> list:
    data = await export_data()
    return data.today.debts


async def get_unsecured_debt(debt_id: str):
    data = await export_data()
    for d in data.today.debts:
        if d.id == debt_id:
            return d
    raise ValueError(f"Unsecured debt '{debt_id}' not found.")


async def create_unsecured_debt(debt: models.BaseDebt):
    data = await export_data()
    today = data.today.model_dump(by_alias=True)
    today["debts"].append(debt.model_dump(exclude_none=True))
    await restore_current_finances(today)
    return debt


async def delete_unsecured_debt(debt_id: str) -> None:
    data = await export_data()
    remaining = [d for d in data.today.debts if d.id != debt_id]
    if len(remaining) == len(data.today.debts):
        raise ValueError(f"Unsecured debt '{debt_id}' not found.")
    today = data.today.model_dump(by_alias=True)
    today["debts"] = [d.model_dump(exclude_none=True) for d in remaining]
    await restore_current_finances(today)


# --- Income CRUD (plan-level) ---

async def list_income_events(plan_id: str) -> list[dict]:
    data = await export_data()
    plan = _find_plan(data.plans, plan_id)
    return plan.get("income", {}).get("events", [])


async def get_income_event(plan_id: str, income_id: str) -> dict:
    events = await list_income_events(plan_id)
    for e in events:
        if e.get("id") == income_id:
            return e
    raise ValueError(f"Income event '{income_id}' not found in plan '{plan_id}'.")


async def _create_income_event(plan_id: str, event: dict) -> dict:
    data = await export_data()
    plans = data.plans
    plan = _find_plan(plans, plan_id)
    plan.setdefault("income", {}).setdefault("events", []).append(event)
    await restore_plans(plans)
    return event


async def create_income(plan_id: str, params: models.NewIncome) -> models.BaseIncome:
    """Create an income event of any verified type using the UI's defaults for everything not given."""
    income = params.to_income()
    await _create_income_event(plan_id, income.model_dump(exclude_none=True))
    return income


async def create_salary(plan_id: str, params: models.NewSalary) -> models.Salary:
    salary = params.to_salary()
    await _create_income_event(plan_id, salary.model_dump(exclude_none=True))
    return salary


async def create_hourly_wage(plan_id: str, params: models.NewHourlyWage) -> models.HourlyWage:
    wage = params.to_hourly_wage()
    await _create_income_event(plan_id, wage.model_dump(exclude_none=True))
    return wage


async def create_rsu_grant(plan_id: str, params: models.NewRsuGrant) -> models.RsuGrant:
    grant = params.to_rsu_grant()
    await _create_income_event(plan_id, grant.model_dump(exclude_none=True))
    return grant


async def create_custom_income(plan_id: str, params: models.NewCustomIncome) -> models.CustomIncome:
    income = params.to_custom_income()
    await _create_income_event(plan_id, income.model_dump(exclude_none=True))
    return income


async def delete_income_event(plan_id: str, income_id: str) -> None:
    data = await export_data()
    plans = data.plans
    plan = _find_plan(plans, plan_id)
    events = plan.get("income", {}).get("events", [])
    remaining = [e for e in events if e.get("id") != income_id]
    if len(remaining) == len(events):
        raise ValueError(f"Income event '{income_id}' not found in plan '{plan_id}'.")
    plan["income"]["events"] = remaining
    await restore_plans(plans)


# --- Expense CRUD (plan-level) ---

async def list_expense_events(plan_id: str) -> list[dict]:
    data = await export_data()
    plan = _find_plan(data.plans, plan_id)
    return plan.get("expenses", {}).get("events", [])


async def get_expense_event(plan_id: str, expense_id: str) -> dict:
    for e in await list_expense_events(plan_id):
        if e.get("id") == expense_id:
            return e
    raise ValueError(f"Expense event '{expense_id}' not found in plan '{plan_id}'.")


async def _create_expense_event(plan_id: str, event: dict) -> dict:
    data = await export_data()
    plans = data.plans
    plan = _find_plan(plans, plan_id)
    plan.setdefault("expenses", {}).setdefault("events", []).append(event)
    await restore_plans(plans)
    return event


async def create_custom_expense(plan_id: str, params: models.NewCustomExpense) -> models.CustomExpense:
    expense = params.to_expense()
    await _create_expense_event(plan_id, expense.model_dump(exclude_none=True, by_alias=True))
    return expense


async def create_expense(plan_id: str, params: models.NewExpense) -> models.BaseExpense:
    """Create an expense of any verified type using the UI's defaults for everything not given."""
    expense = params.to_expense()
    await _create_expense_event(plan_id, expense.model_dump(exclude_none=True, by_alias=True))
    return expense


async def delete_expense_event(plan_id: str, expense_id: str) -> None:
    data = await export_data()
    plans = data.plans
    plan = _find_plan(plans, plan_id)
    events = plan.get("expenses", {}).get("events", [])
    if any(e.get("_meta", {}).get("deletion") == "locked" for e in events if e.get("id") == expense_id):
        raise ValueError(f"Expense event '{expense_id}' is generated by ProjectionLab and cannot be deleted.")
    remaining = [e for e in events if e.get("id") != expense_id]
    if len(remaining) == len(events):
        raise ValueError(f"Expense event '{expense_id}' not found in plan '{plan_id}'.")
    plan["expenses"]["events"] = remaining
    await restore_plans(plans)


async def list_plans() -> list[dict]:
    data = await export_data()
    return [{"id": p.get("id"), "name": p.get("name"), "active": p.get("active", False)} for p in data.plans]


# --- Priority CRUD ---
#
# NOTE: restorePlans() silently strips plan.priorities — ProjectionLab's plugin
# API does not expose a dedicated priorities endpoint.  We work around this by
# mutating plan.priorities.events directly in the Pinia store.  Vue's
# reactivity system picks up the change and the sync store saves it to Firebase
# automatically (no explicit save call required).

def _get_priority_events(plan: dict) -> list:
    return plan.setdefault("priorities", {}).setdefault("events", [])


async def _pinia_mutate_priorities(plan_id: str, js_body: str) -> None:
    """Run js_body against `events` (plan.priorities.events) in the Pinia store."""
    page = await get_page()
    script = f"""async () => {{
        const app = document.querySelector('#app').__vue_app__;
        const pinia = app.config.globalProperties.$pinia;
        const planStore = pinia._s.get('plan');
        const plan = planStore.plans.find(p => p.id === {json.dumps(plan_id)});
        if (!plan) throw new Error('Plan not found: ' + {json.dumps(plan_id)});
        plan.priorities = plan.priorities || {{}};
        plan.priorities.events = plan.priorities.events || [];
        const events = plan.priorities.events;
        {js_body}
    }}"""
    await page.evaluate(script)


async def list_priorities(plan_id: str) -> list[models.Priority]:
    data = await export_data()
    plan = _find_plan(data.plans, plan_id)
    return [models.Priority.model_validate(e) for e in _get_priority_events(plan)]


async def get_priority(plan_id: str, priority_id: str) -> models.Priority:
    priorities = await list_priorities(plan_id)
    for p in priorities:
        if p.id == priority_id:
            return p
    raise ValueError(f"Priority '{priority_id}' not found in plan '{plan_id}'.")


async def create_priority(plan_id: str, priority) -> models.Priority:
    event = priority.model_dump(exclude_none=True)
    await _pinia_mutate_priorities(plan_id, f"events.push({json.dumps(event)});")
    return models.Priority.model_validate(event)


async def delete_priority(plan_id: str, priority_id: str) -> None:
    js = f"""
        const idx = events.findIndex(e => e.id === {json.dumps(priority_id)});
        if (idx === -1) throw new Error('Priority not found: ' + {json.dumps(priority_id)});
        events.splice(idx, 1);
    """
    await _pinia_mutate_priorities(plan_id, js)


async def reorder_priorities(plan_id: str, priority_ids: list[str]) -> list[models.Priority]:
    """Reorder priorities to match the given list of IDs (must include all existing IDs)."""
    # Validate first via exportData
    data = await export_data()
    plan = _find_plan(data.plans, plan_id)
    events = _get_priority_events(plan)
    by_id = {e["id"]: e for e in events}
    if set(priority_ids) != set(by_id):
        raise ValueError("priority_ids must contain exactly the same IDs as the existing priorities.")
    ordered = [by_id[pid] for pid in priority_ids]
    js = f"events.splice(0, events.length, ...{json.dumps(ordered)});"
    await _pinia_mutate_priorities(plan_id, js)
    return [models.Priority.model_validate(by_id[pid]) for pid in priority_ids]
