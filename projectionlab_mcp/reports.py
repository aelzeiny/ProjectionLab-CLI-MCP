"""
Report export — drives the Reports tab of a plan (``/plan/<id>/reports``) to download the
tables and plots ProjectionLab offers there as CSV, JSON or PDF.

The Plugin API has no report endpoint; the data only exists as the chart/table the UI
renders, and the UI's Export menu serialises it client-side into a ``blob:`` download.
So this module selects the report through the toolbar menus and captures that download
with Playwright.

Toolbar layout (ProjectionLab 4.6):

    [Explore] [Tables ▾] [Plots ▾] ... [⚙] [⛶] [⬇ Export ▾] [⋮]

The second button lists the three *tables*, the third the ~41 *plots*; picking one
resets the other. Every menu item carries a stable ``path`` attribute (e.g.
``netWorth``, ``granularSpending``) which is what :data:`REPORTS` is keyed by — the
visible names are not unique ("Spending" and "Income" each appear twice).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .browser import PROJECTIONLAB_URL, get_page

ReportKind = Literal["table", "plot"]
ReportFormat = Literal["csv", "json", "pdf"]

FORMATS: tuple[str, ...] = ("csv", "json", "pdf")

# key (the menu item's `path` attribute) -> (kind, label shown in the UI)
REPORTS: dict[str, tuple[ReportKind, str]] = {
    # Tables
    "summaryTable": ("table", "Summary"),
    "investmentReturnsTable": ("table", "Rates"),
    "incomeTable": ("table", "Income"),
    # Built-in plots
    "netWorth": ("plot", "Net Worth"),
    "stackedAssets": ("plot", "Stacked Net Worth"),
    "incomeByCategory": ("plot", "Income"),
    "expensesByCategory": ("plot", "Expenses"),
    "spendingByCategory": ("plot", "Spending"),
    "spendingBySection": ("plot", "Spending Overview"),
    "discretionarySpendingByCategory": ("plot", "Discretionary Spending"),
    "essentialSpendingByCategory": ("plot", "Essential Spending"),
    "flexSpendingByCategory": ("plot", "Spending Flex"),
    "taxesByCategory": ("plot", "Taxes"),
    "withdrawalsByCategory": ("plot", "Withdrawals"),
    "taxableIncomeByCategory": ("plot", "Taxable Income"),
    "stateTaxableIncomeByCategory": ("plot", "State Taxable Income"),
    "localTaxableIncomeByCategory": ("plot", "Local Taxable Income"),
    "savingsRate": ("plot", "Savings Rate"),
    "contributions": ("plot", "Contributions"),
    "contributionsAndWithdrawals": ("plot", "Contribs & Withdrawals"),
    "goalHeatmap": ("plot", "Goal Heatmap"),
    "incomeBySource": ("plot", "Income Breakdown"),
    "granularExpenses": ("plot", "Expenses Breakdown"),
    "granularSpending": ("plot", "Spending"),  # second "Spending" entry: per-expense breakdown
    "granularTaxes": ("plot", "Taxes Breakdown"),
    "withdrawalsBySource": ("plot", "Withdrawals Breakdown"),
    "taxableIncomeBySource": ("plot", "Taxable Income Breakdown"),
    "stateTaxableIncomeBySource": ("plot", "State Taxable Income Breakdown"),
    "localTaxableIncomeBySource": ("plot", "Local Taxable Income Breakdown"),
    "nonTaxableIncomeByCategory": ("plot", "Non-Taxable Income"),
    "passiveIncomeByCategory": ("plot", "Passive Income"),
    "granularContributions": ("plot", "Contributions Breakdown"),
    "granularContributionsAndWithdrawals": ("plot", "C/W Breakdown"),
    "granularDebtPayments": ("plot", "Debt Payments Breakdown"),
    "lnwByCategory": ("plot", "Liquidity"),
    "lnwByAccount": ("plot", "Liquidity Breakdown"),
    "stackedAccounts": ("plot", "All Accounts"),
    "changeInNetWorth": ("plot", "Change in Net Worth"),
    "granularChangeInNetWorth": ("plot", "Change in Net Worth Breakdown"),
    "investmentReturnsByCategory": ("plot", "Investment Growth"),
    "investmentReturnsByAccount": ("plot", "Investment Growth Breakdown"),
    "investmentAllocations": ("plot", "Allocations by Percent"),
    "investmentAllocationsBalance": ("plot", "Allocations by Amount"),
    "accountAllocations": ("plot", "Allocations by Account"),
}


@dataclass
class Report:
    plan_id: str
    key: str
    kind: ReportKind
    name: str
    format: str
    filename: str  # the name the browser would have saved it as
    content: bytes

    @property
    def text(self) -> str:
        return self.content.decode("utf-8-sig")

    def save(self, path: str) -> str:
        with open(path, "wb") as f:
            f.write(self.content)
        return path


def list_reports() -> list[dict]:
    return [{"key": k, "kind": kind, "name": name} for k, (kind, name) in REPORTS.items()]


def resolve_report(ref: str) -> str:
    """Accept a report key (``netWorth``) or a UI label (``"Net Worth"``, case-insensitive)."""
    if ref in REPORTS:
        return ref
    lowered = ref.strip().lower()
    by_key = [k for k in REPORTS if k.lower() == lowered]
    if len(by_key) == 1:
        return by_key[0]
    by_name = [k for k, (_, name) in REPORTS.items() if name.lower() == lowered]
    if len(by_name) == 1:
        return by_name[0]
    if by_name:
        opts = ", ".join(f"{k} ({REPORTS[k][0]})" for k in by_name)
        raise ValueError(f"Report name {ref!r} is ambiguous; use one of the keys: {opts}")
    raise ValueError(f"Unknown report {ref!r}. Known keys: {', '.join(REPORTS)}")


# ── browser driving ──────────────────────────────────────────────────────────

_EXPLORE = re.compile(r"^\s*Explore\s*$")


def _toolbar(page):
    # The row that holds the "Explore" button is the reports toolbar.
    return page.locator("div.v-row", has=page.locator("button", has_text=_EXPLORE)).first


async def _open_reports_page(page, plan_id: str) -> None:
    url = f"{PROJECTIONLAB_URL}/plan/{plan_id}/reports"
    if page.url != url:
        await page.goto(url)
    try:
        await page.locator("button", has_text=_EXPLORE).first.wait_for(state="visible", timeout=30000)
    except Exception as e:  # noqa: BLE001
        if f"/plan/{plan_id}" not in page.url:
            raise ValueError(f"Plan '{plan_id}' not found (browser ended up at {page.url}).") from e
        raise RuntimeError(f"Reports toolbar did not appear for plan '{plan_id}' ({page.url}).") from e


async def _menu_item(page, selector: str = "", text: str | None = None, timeout: int = 5000):
    items = page.locator(f".v-overlay--active .v-list-item{selector}")
    if text is not None:
        items = items.filter(has_text=re.compile(rf"^\s*{re.escape(text)}\s*$"))
    item = items.first
    await item.wait_for(state="visible", timeout=timeout)
    return item


async def _select_report(page, key: str) -> None:
    kind, name = REPORTS[key]
    toolbar = _toolbar(page)
    # buttons: 0 = Explore, 1 = tables menu, 2 = plots menu
    button = toolbar.locator("button").nth(1 if kind == "table" else 2)
    await button.click()
    try:
        item = await _menu_item(page, f'[path="{key}"]')
    except Exception as e:  # noqa: BLE001
        await page.keyboard.press("Escape")
        raise RuntimeError(f"Report '{key}' ({name}) is not in the {kind}s menu of this ProjectionLab version.") from e
    await item.click()
    # The chosen menu's button now shows the report's name; the other menu resets.
    await button.locator("div.text-truncate", has_text=re.compile(rf"^\s*{re.escape(name)}\s*$")).wait_for(timeout=10000)
    await page.wait_for_timeout(500)  # let the table/chart re-render before exporting


async def download_report(plan_id: str, report: str, fmt: str = "csv") -> Report:
    """Select ``report`` on the plan's Reports tab and capture its Export → CSV/JSON/PDF download."""
    fmt = fmt.lower()
    if fmt not in FORMATS:
        raise ValueError(f"format must be one of {', '.join(FORMATS)}, got {fmt!r}")
    key = resolve_report(report)
    kind, name = REPORTS[key]

    page = await get_page()
    await _open_reports_page(page, plan_id)
    await _select_report(page, key)

    export_button = _toolbar(page).locator("button:has(i.mdi-download)").first
    async with page.expect_download(timeout=60000) as dl_info:
        await export_button.click()
        item = await _menu_item(page, text=fmt.upper())
        await item.click()
    download = await dl_info.value
    path = await download.path()
    with open(path, "rb") as f:
        content = f.read()
    return Report(
        plan_id=plan_id, key=key, kind=kind, name=name, format=fmt,
        filename=download.suggested_filename, content=content,
    )
