"""
projectionlab — command-line interface to the unofficial ProjectionLab Plugin API client.

Every command talks to ProjectionLab through the same browser session the MCP server uses
(shared CDP browser when CDP_PORT is set, otherwise a private headless one) and prints JSON.

    projectionlab export [-o FILE]
    projectionlab plans
    projectionlab income   list PLAN | get PLAN ID | create PLAN --type salary --name N --amount A ... | delete PLAN ID
    projectionlab expense  list PLAN | get PLAN ID | create PLAN --type rent   --name N --amount A ... | delete PLAN ID
    projectionlab milestone list PLAN | get PLAN ID | create PLAN --json ... | update PLAN ID --set k=v | delete PLAN ID
    projectionlab priority list PLAN | get PLAN ID | create PLAN --type cash|investment|asset-loan|debt|transfer ... | delete PLAN ID | reorder PLAN ID...
    projectionlab savings    list | get ID | create --set name=... | delete ID
    projectionlab investment list | get ID | create --type taxable|crypto|hsa|529|ira|inherited-ira|roth-ira|inherited-roth-ira ... | delete ID
    projectionlab asset      list | get ID | create --type real-estate|car|... | delete ID
    projectionlab debt       list | get ID | create --type generic|student-loans ... | delete ID
    projectionlab account update ID --set balance=5000 [--force]
    projectionlab restore plans|current-finances|progress|settings FILE
    projectionlab validate-key
    projectionlab report list | download PLAN REPORT [--format csv|json|pdf] [-o FILE]
    projectionlab probe snap LABEL | diff A B | show LABEL [PATH]

PLAN may be a plan id or its (unique) name. Creation parameters come from any mix of
`--set key=value` (value parsed as JSON when possible), `--json '{...}'` and `--file f.json`
(`-` for stdin); they are validated against the same Pydantic models the MCP tools use.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Callable

from . import plugin_api as api
from . import models

# ── helpers ───────────────────────────────────────────────────────────────────


def _out(obj: Any) -> None:
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump(exclude_none=True, by_alias=True)
    elif isinstance(obj, list):
        obj = [o.model_dump(exclude_none=True, by_alias=True) if hasattr(o, "model_dump") else o for o in obj]
    json.dump(obj, sys.stdout, indent=2, sort_keys=False)
    sys.stdout.write("\n")


def _parse_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _params(args: argparse.Namespace) -> dict[str, Any]:
    """Merge --file / --json / --set / well-known flags into one dict."""
    data: dict[str, Any] = {}
    if getattr(args, "file", None):
        src = sys.stdin if args.file == "-" else open(args.file)
        data.update(json.load(src))
    if getattr(args, "json", None):
        data.update(json.loads(args.json))
    for kv in getattr(args, "set", None) or []:
        if "=" not in kv:
            sys.exit(f"--set expects key=value, got {kv!r}")
        k, v = kv.split("=", 1)
        data[k] = _parse_value(v)
    for flag in ("type", "name", "amount", "owner", "frequency"):
        v = getattr(args, flag, None)
        if v is not None:
            data[flag] = v
    return data


def _build(model: type, args: argparse.Namespace):
    data = _params(args)
    fields = getattr(model, "model_fields", {})
    if "extra" in fields:
        # NewIncome / NewExpense keep type-specific fields in `extra`; route unknown keys there.
        unknown = [k for k in data if k not in fields]
        if unknown:
            data.setdefault("extra", {}).update({k: data.pop(k) for k in unknown})
    try:
        return model.model_validate(data)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"invalid parameters for {model.__name__}:\n{e}")


def _add_param_flags(p: argparse.ArgumentParser, *, with_type: bool = True, type_choices: list[str] | None = None) -> None:
    if with_type:
        p.add_argument("--type", choices=type_choices, help="Kind of record to create.")
    p.add_argument("--name")
    p.add_argument("--amount", type=float)
    p.add_argument("--owner", choices=["me", "spouse"])
    p.add_argument("--frequency")
    p.add_argument("--set", action="append", metavar="KEY=VALUE", help="Set any field; value is parsed as JSON when possible. Repeatable.")
    p.add_argument("--json", metavar="JSON", help="Parameters as a JSON object.")
    p.add_argument("--file", metavar="FILE", help="Parameters from a JSON file ('-' for stdin).")


async def _resolve_plan(ref: str) -> str:
    plans = await api.list_plans()
    for p in plans:
        if p["id"] == ref:
            return ref
    matches = [p for p in plans if p["name"] == ref]
    if len(matches) == 1:
        return matches[0]["id"]
    names = ", ".join(f"{p['name']} ({p['id']})" for p in plans)
    sys.exit(f"plan {ref!r} not found or ambiguous. Plans: {names}")


def _run(coro):
    try:
        return asyncio.run(coro)
    except (ValueError, RuntimeError) as e:
        sys.exit(f"error: {e}")


# ── type maps ─────────────────────────────────────────────────────────────────

INVESTMENT_MODELS = {
    "taxable": models.TaxableInvestmentAccount,
    "crypto": models.CryptoInvestmentAccount,
    "hsa": models.HSAInvestmentAccount,
    "529": models.Plan529InvestmentAccount,
    "ira": models.IRAInvestmentAccount,
    "inherited-ira": models.InheritedIRAInvestmentAccount,
    "roth-ira": models.RothIRAInvestmentAccount,
    "inherited-roth-ira": models.InheritedRothIRAInvestmentAccount,
}
ASSET_MODELS = {
    "real-estate": models.RealEstateAsset,
    "rental": models.RentalPropertyAsset,
    "building": models.BuildingAsset,
    "commercial": models.CommercialPropertyAsset,
    "car": models.CarAsset,
    "motorcycle": models.MotorcycleAsset,
    "boat": models.BoatAsset,
    "land": models.LandAsset,
    "jewelry": models.JewelryAsset,
    "precious-metals": models.PreciousMetalsAsset,
    "furniture": models.FurnitureAsset,
    "instrument": models.InstrumentAsset,
    "machinery": models.MachineryAsset,
    "custom": models.CustomAsset,
}
DEBT_MODELS = {"generic": models.GenericDebt, "student-loans": models.StudentLoansDebt}
PRIORITY_MODELS = {
    "cash": models.NewCashPriority,
    "investment": models.NewInvestmentPriority,
    "asset-loan": models.NewAssetLoanPriority,
    "debt": models.NewDebtPriority,
    "transfer": models.NewTransferPriority,
}
INCOME_TYPES = list(models.INCOME_MODELS)
EXPENSE_TYPES = list(models.EXPENSE_MODELS) + ["student-loans"]
EXPENSE_TYPES.remove("medicare")


# ── command implementations ──────────────────────────────────────────────────

async def cmd_export(args):
    raw = await api._call("exportData")
    if args.output:
        with open(args.output, "w") as f:
            json.dump(raw, f, indent=2)
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        _out(raw)


async def cmd_validate_key(args):
    await api.validate_api_key()
    print("API key is valid.")


async def cmd_restore(args):
    data = json.load(sys.stdin if args.file == "-" else open(args.file))
    fn = {
        "plans": api.restore_plans,
        "current-finances": api.restore_current_finances,
        "progress": api.restore_progress,
        "settings": api.restore_settings,
    }[args.section]
    await fn(data)
    print(f"{args.section} restored.")


async def cmd_plans(args):
    _out(await api.list_plans())


async def cmd_account_update(args):
    data = {}
    for kv in args.set or []:
        k, v = kv.split("=", 1)
        data[k] = _parse_value(v)
    await api.update_account(args.id, data, args.force)
    print(f"Account '{args.id}' updated.")


def _plan_section(list_fn, get_fn, create_fn, delete_fn, model_for: Callable[[argparse.Namespace], type]):
    """Build list/get/create/delete handlers for a per-plan section."""
    async def _list(args):
        _out(await list_fn(await _resolve_plan(args.plan)))

    async def _get(args):
        _out(await get_fn(await _resolve_plan(args.plan), args.id))

    async def _create(args):
        params = _build(model_for(args), args)
        _out(await create_fn(await _resolve_plan(args.plan), params))

    async def _delete(args):
        await delete_fn(await _resolve_plan(args.plan), args.id)
        print(f"deleted {args.id}")

    return _list, _get, _create, _delete


def _today_section(list_fn, get_fn, create_fn, delete_fn, model_for: Callable[[argparse.Namespace], type]):
    async def _list(args):
        _out(await list_fn())

    async def _get(args):
        _out(await get_fn(args.id))

    async def _create(args):
        params = _build(model_for(args), args)
        _out(await create_fn(params))

    async def _delete(args):
        await delete_fn(args.id)
        print(f"deleted {args.id}")

    return _list, _get, _create, _delete


async def cmd_milestone_update(args):
    plan_id = await _resolve_plan(args.plan)
    updates = _params(args)
    _out(await api.update_milestone(plan_id, args.id, updates))


async def cmd_priority_reorder(args):
    plan_id = await _resolve_plan(args.plan)
    _out(await api.reorder_priorities(plan_id, args.ids))


def cmd_report_list(args):
    _out(api.list_reports())


async def cmd_report_download(args):
    plan_id = await _resolve_plan(args.plan)
    rep = await api.download_report(plan_id, args.report, args.format)
    out = args.output
    if out is None and args.format == "pdf":
        out = rep.filename
    if out:
        rep.save(out)
        print(f"{rep.name} ({rep.kind}, key={rep.key}) -> {out} ({len(rep.content)} bytes)", file=sys.stderr)
    else:
        sys.stdout.write(rep.text)
        if not rep.text.endswith("\n"):
            sys.stdout.write("\n")


def cmd_probe(args):
    from . import probe
    if args.probe_cmd == "snap":
        if not os.getenv("CDP_PORT"):
            print("warning: CDP_PORT is not set; using a private headless browser.", file=sys.stderr)
        probe.snap(args.label)
    elif args.probe_cmd == "diff":
        probe.diff(args.a, args.b, {x for x in args.ignore.split(",") if x})
    elif args.probe_cmd == "show":
        probe.show(args.label, args.path)


# ── parser ────────────────────────────────────────────────────────────────────

def _crud(sub, name: str, help_: str, handlers, *, per_plan: bool, type_choices: list[str] | None, with_type: bool = True):
    p = sub.add_parser(name, help=help_)
    s = p.add_subparsers(dest=f"{name}_cmd", required=True)
    _list, _get, _create, _delete = handlers

    lp = s.add_parser("list", help=f"List {help_.lower()}.")
    if per_plan:
        lp.add_argument("plan")
    lp.set_defaults(func=_list)

    gp = s.add_parser("get", help="Get one by id.")
    if per_plan:
        gp.add_argument("plan")
    gp.add_argument("id")
    gp.set_defaults(func=_get)

    cp = s.add_parser("create", help="Create one; fields via --type/--name/--amount/--set/--json/--file.")
    if per_plan:
        cp.add_argument("plan")
    _add_param_flags(cp, with_type=with_type, type_choices=type_choices)
    cp.set_defaults(func=_create)

    dp = s.add_parser("delete", help="Delete one by id.")
    if per_plan:
        dp.add_argument("plan")
    dp.add_argument("id")
    dp.set_defaults(func=_delete)
    return s


def _require_type(table: dict, default: str | None = None):
    def pick(args):
        t = getattr(args, "type_choice", None) or getattr(args, "type", None) or default
        if not t:
            sys.exit(f"--type is required (one of: {', '.join(table)})")
        # `type` is a field on the create model for income/expense, not for the
        # today-section record models, whose `type` is a fixed Literal.
        return table[t]
    return pick


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="projectionlab", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("export", help="Export all data as JSON.")
    p.add_argument("-o", "--output", help="Write to a file instead of stdout.")
    p.set_defaults(func=cmd_export)

    sub.add_parser("validate-key", help="Check the configured API key.").set_defaults(func=cmd_validate_key)

    p = sub.add_parser("restore", help="Replace a whole section from a JSON file (destructive).")
    p.add_argument("section", choices=["plans", "current-finances", "progress", "settings"])
    p.add_argument("file", help="JSON file ('-' for stdin).")
    p.set_defaults(func=cmd_restore)

    sub.add_parser("plans", help="List plans (id, name, active).").set_defaults(func=cmd_plans)

    p = sub.add_parser("account", help="Current Finances account operations.")
    s = p.add_subparsers(dest="account_cmd", required=True)
    up = s.add_parser("update", help="Patch fields on an account by id (updateAccount).")
    up.add_argument("id")
    up.add_argument("--set", action="append", metavar="KEY=VALUE", required=True)
    up.add_argument("--force", action="store_true", help="Allow adding properties that don't exist yet.")
    up.set_defaults(func=cmd_account_update)

    # per-plan sections
    _crud(sub, "income", "Income events", _plan_section(
        api.list_income_events, api.get_income_event, api.create_income, api.delete_income_event,
        lambda a: models.NewIncome), per_plan=True, type_choices=INCOME_TYPES)
    _crud(sub, "expense", "Expense events", _plan_section(
        api.list_expense_events, api.get_expense_event, api.create_expense, api.delete_expense_event,
        lambda a: models.NewExpense), per_plan=True, type_choices=EXPENSE_TYPES)
    ms = _crud(sub, "milestone", "Milestones", _plan_section(
        api.list_milestones, api.get_milestone, api.create_milestone, api.delete_milestone,
        lambda a: models.NewMilestone), per_plan=True, type_choices=None, with_type=False)
    mu = ms.add_parser("update", help="Update fields on a milestone.")
    mu.add_argument("plan"); mu.add_argument("id")
    _add_param_flags(mu, with_type=False)
    mu.set_defaults(func=cmd_milestone_update)
    pr = _crud(sub, "priority", "Cash-flow priorities (Flows)", _plan_section(
        api.list_priorities, api.get_priority, api.create_priority, api.delete_priority,
        _require_type(PRIORITY_MODELS)), per_plan=True, type_choices=list(PRIORITY_MODELS))
    ro = pr.add_parser("reorder", help="Reorder priorities; pass every id in the new order.")
    ro.add_argument("plan"); ro.add_argument("ids", nargs="+")
    ro.set_defaults(func=cmd_priority_reorder)

    # Current Finances sections
    _crud(sub, "savings", "Savings accounts", _today_section(
        api.list_savings_accounts, api.get_savings_account, api.create_savings_account, api.delete_savings_account,
        lambda a: models.NewSavingsAccount), per_plan=False, type_choices=None, with_type=False)
    _crud(sub, "investment", "Investment accounts", _today_section(
        api.list_investment_accounts, api.get_investment_account, api.create_investment_account, api.delete_investment_account,
        _require_type(INVESTMENT_MODELS)), per_plan=False, type_choices=list(INVESTMENT_MODELS))
    _crud(sub, "asset", "Real assets", _today_section(
        api.list_real_assets, api.get_real_asset, api.create_real_asset, api.delete_real_asset,
        _require_type(ASSET_MODELS)), per_plan=False, type_choices=list(ASSET_MODELS))
    _crud(sub, "debt", "Unsecured debts", _today_section(
        api.list_unsecured_debts, api.get_unsecured_debt, api.create_unsecured_debt, api.delete_unsecured_debt,
        _require_type(DEBT_MODELS)), per_plan=False, type_choices=list(DEBT_MODELS))

    # reports
    p = sub.add_parser("report", help="Export a plan's Reports-tab tables/plots as CSV, JSON or PDF.")
    s = p.add_subparsers(dest="report_cmd", required=True)
    s.add_parser("list", help="List report keys (tables and plots).").set_defaults(func=cmd_report_list, sync=True)
    rd = s.add_parser("download", help="Download one report (key from `report list`, or its UI name when unique).")
    rd.add_argument("plan"); rd.add_argument("report")
    rd.add_argument("-f", "--format", choices=["csv", "json", "pdf"], default="csv")
    rd.add_argument("-o", "--output", help="Write to a file instead of stdout (pdf defaults to the browser's filename).")
    rd.set_defaults(func=cmd_report_download)

    # schema probe
    p = sub.add_parser("probe", help="Snapshot/diff exports for schema reverse-engineering.")
    s = p.add_subparsers(dest="probe_cmd", required=True)
    sp = s.add_parser("snap"); sp.add_argument("label")
    dp = s.add_parser("diff"); dp.add_argument("a"); dp.add_argument("b")
    dp.add_argument("--ignore", default="lastUpdated,computedMilestones,simKey")
    shp = s.add_parser("show"); shp.add_argument("label"); shp.add_argument("path", nargs="?", default="")
    p.set_defaults(func=cmd_probe, sync=True)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    # The today-section record models carry a fixed `type`; drop the CLI's --type so it
    # doesn't collide (the model already knows its type).
    if args.cmd in ("investment", "asset", "debt", "priority") and getattr(args, "type", None):
        args.type_choice = args.type
        args.type = None
    if getattr(args, "sync", False):
        args.func(args)
    else:
        _run(args.func(args))


if __name__ == "__main__":
    main()
