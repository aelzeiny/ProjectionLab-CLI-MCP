# ProjectionLab CLI & MCP

A command-line tool (`projectionlab` / `pl`) and an MCP server for [ProjectionLab](https://app.projectionlab.com), built on the [ProjectionLab Plugin API](https://docs.projectionlab.com/plugins). Both drive a headless browser via Playwright, log in to ProjectionLab, and expose your financial data as typed operations: read and write accounts, plans, income, expenses, milestones and flows, and export the Reports tab as CSV, JSON or PDF.

- **CLI** — script ProjectionLab from the shell; every command prints JSON, so it composes with `jq`. See [CLI](#cli).
- **MCP server** — the same operations as tools for Claude Code, Claude Desktop or any MCP client. See [Tools](#tools).

## Tools

### Raw API access

These tools map directly to Plugin API methods and give full control over the data. Use them for operations not covered by the typed tools below, or to read/write large sections of data at once.

| Tool                       | Description                                                   |
| -------------------------- | ------------------------------------------------------------- |
| `export_data`              | Export all data (finances, plans, progress, settings) as JSON |
| `update_account`           | Patch a single account field by ID                            |
| `restore_current_finances` | Replace the entire Current Finances state                     |
| `restore_plans`            | Replace all plans                                             |
| `restore_progress`         | Replace progress history                                      |
| `restore_settings`         | Replace settings                                              |
| `validate_api_key`         | Check that the configured API key works                       |

### Plans

| Tool         | Description                             |
| ------------ | --------------------------------------- |
| `list_plans` | List all plans with their IDs and names |

### Savings accounts (Current Finances)

| Tool                     | Description                    |
| ------------------------ | ------------------------------ |
| `list_savings_accounts`  | List all savings accounts      |
| `get_savings_account`    | Get a savings account by ID    |
| `create_savings_account` | Create a new savings account   |
| `delete_savings_account` | Delete a savings account by ID |

### Investment accounts (Current Finances)

| Tool                                           | Description                        |
| ---------------------------------------------- | ---------------------------------- |
| `list_investment_accounts`                     | List all investment accounts       |
| `get_investment_account`                       | Get an investment account by ID    |
| `create_taxable_investment_account`            | Create a taxable brokerage account |
| `create_crypto_investment_account`             | Create a cryptocurrency account    |
| `create_hsa_investment_account`                | Create an HSA                      |
| `create_529_investment_account`                | Create a 529 college savings plan  |
| `create_ira_investment_account`                | Create a traditional IRA           |
| `create_inherited_ira_investment_account`      | Create an Inherited IRA            |
| `create_roth_ira_investment_account`           | Create a Roth IRA                  |
| `create_inherited_roth_ira_investment_account` | Create an Inherited Roth IRA       |
| `delete_investment_account`                    | Delete an investment account by ID |

### Real assets (Current Finances)

| Tool                       | Description                                               |
| -------------------------- | --------------------------------------------------------- |
| `list_real_assets`         | List all real assets                                      |
| `get_real_asset`           | Get a real asset by ID                                    |
| `create_real_estate_asset` | Create a real estate asset (home, rental, building, etc.) |
| `create_car_asset`         | Create a vehicle asset (car, truck, etc.)                 |
| `create_custom_asset`      | Create a custom real asset                                |
| `delete_real_asset`        | Delete a real asset by ID                                 |

For asset types without a dedicated create tool (motorcycle, boat, land, jewelry, etc.), use `restore_current_finances` with the full modified state from `export_data`.

### Unsecured debts (Current Finances)

| Tool                        | Description                                                       |
| --------------------------- | ----------------------------------------------------------------- |
| `list_unsecured_debts`      | List all unsecured debts                                          |
| `get_unsecured_debt`        | Get an unsecured debt by ID                                       |
| `create_generic_debt`       | Create a generic debt (credit card, medical, personal loan, etc.) |
| `create_student_loans_debt` | Create a student loans debt                                       |
| `delete_unsecured_debt`     | Delete an unsecured debt by ID                                    |

### Income events (per plan)

Income events live inside a plan (`plan.income.events`) and are plan-specific. Pass the plan ID from `list_plans` to all income tools.

| Tool                   | Description                                        |
| ---------------------- | -------------------------------------------------- |
| `list_income_events`   | List all income events in a plan                   |
| `get_income_event`     | Get a single income event by ID                    |
| `create_income`        | Add an income event of any UI type (salary, hourly, rsu, side-hustle, inheritance, tax-credit, tax-deduction, pension, social-security, other) with the UI's defaults |
| `create_salary`        | Add a salary income event                          |
| `create_hourly_wage`   | Add an hourly wage income event                    |
| `create_rsu_grant`     | Add an RSU grant income event                      |
| `create_custom_income` | Add a custom income event (stored type: `"other"`) |
| `delete_income_event`  | Delete an income event by ID                       |

### Expense events (per plan)

Expense events live inside a plan (`plan.expenses.events`). Generated Medicare expenses are locked and cannot be deleted.

| Tool                    | Description                                          |
| ----------------------- | ---------------------------------------------------- |
| `list_expense_events`   | List all expense events in a plan                    |
| `get_expense_event`     | Get a single expense event by ID                     |
| `create_expense`        | Add an expense of any UI type (rent, education, wedding, debt, ...) with the UI's defaults |
| `create_custom_expense` | Add a custom expense event (stored type: `"other"`)  |
| `delete_expense_event`  | Delete an expense event by ID                        |

### Milestones (per plan)

| Tool               | Description                            |
| ------------------ | -------------------------------------- |
| `list_milestones`  | List all milestones in a plan          |
| `get_milestone`    | Get a milestone by ID                  |
| `create_milestone` | Create a new milestone                 |
| `update_milestone` | Update fields on an existing milestone |
| `delete_milestone` | Delete a milestone by ID               |

### Reports (per plan)

The Reports tab of a plan renders 3 tables and ~41 plots and can export the one on screen as
CSV, JSON or PDF. There is no Plugin API for this, so these tools drive the shared browser:
pick the report from the toolbar menus and capture the Export download.

| Tool              | Description                                                                 |
| ----------------- | --------------------------------------------------------------------------- |
| `list_reports`    | List report keys (`summaryTable`, `netWorth`, `expensesByCategory`, ...)    |
| `download_report` | Export one report as `csv`/`json` (returned inline) or `pdf` (saved to a path) |

Reports are addressed by the stable key the UI's menu items carry (`path` attribute), because
the visible names are not unique: "Spending" is both `spendingByCategory` and the per-expense
`granularSpending`, and "Income" is both the `incomeTable` table and the `incomeByCategory` plot.
Unique names ("Net Worth", "Summary") are accepted too. CSV exports start with a title line and a
blank line before the header row; JSON exports are a list of row objects keyed by column name.

## CLI

The same operations are available from the shell as `projectionlab` (alias `pl`). Output is JSON,
so it composes with `jq`. Plans can be referenced by id or by name.

```bash
pl plans                                   # list plans
pl export -o backup.json                   # full export
pl income list "My Plan" | jq '.[].name'
pl income create "My Plan" --type salary --name "New job" --amount 180000 \
     --set withholdingMode=fixed --set withholdingRate=25
pl expense create "My Plan" --type wedding --name Wedding --amount 20000 \
     --set 'start={"type":"date","value":"2027-06-01"}' --set switchToMarried=true
pl expense delete "My Plan" <id>
pl milestone update "My Plan" <id> --set name="FI"
pl priority reorder "My Plan" <id1> <id2> <id3> <id4>
pl investment create --type roth-ira --set name="Roth" --set title="Roth IRA" --set owner=me --set balance=0
pl account update <id> --set balance=52000
pl report list | jq -r '.[].key'          # report keys
pl report download "My Plan" summaryTable > summary.csv
pl report download "My Plan" netWorth -f json | jq '.[0]'
pl report download "My Plan" expensesByCategory -f pdf -o expenses.pdf
pl restore plans backup-plans.json         # destructive: replaces all plans
pl probe snap before && pl probe snap after && pl probe diff before after
```

Creation parameters come from `--type/--name/--amount/--owner/--frequency`, any number of
`--set key=value` (values parsed as JSON when possible), `--json '{...}'`, or `--file f.json`
(`-` for stdin), and are validated against the same Pydantic models the MCP tools use. Fields
you omit take the defaults the ProjectionLab UI itself would use for that type.

## Requirements

- Python 3.11+
- A ProjectionLab account with **Plugins enabled** (Account Settings → Plugins)

## Setup

```bash
git clone git@github.com:aelzeiny/ProjectionLab-CLI-MCP.git
cd ProjectionLab-CLI-MCP
uv venv .venv && uv pip install -p .venv/bin/python -e .   # or: pip install -e .
.venv/bin/playwright install chromium
```

This installs three commands into the venv: `projectionlab` and `pl` (the CLI) and `projectionlab-mcp` (the server).

Copy `.env.example` to `.env` and fill in your credentials:

```env
PROJECTIONLAB_EMAIL=your@email.com
PROJECTIONLAB_PASSWORD=yourpassword
PROJECTIONLAB_API_KEY=your-plugin-api-key
```

The API key is found in ProjectionLab under **Account Settings → Plugins**.

## Running

```bash
projectionlab-mcp
```

The server launches a headless browser, logs in automatically, and communicates over stdio (MCP standard). Set `HEADLESS=false` in `.env` to open a visible browser window.

### Dev mode

Dev mode connects to a shared visible browser via Chrome DevTools Protocol, useful for watching what the server does in real time alongside a browser automation tool (e.g. [browser-mcp](https://github.com/executeautomation/mcp-playwright)).

```bash
# Terminal 1 — start the shared browser (add HEADLESS=true on a box with no X display)
CDP_PORT=9222 python launch_browser.py

# Terminal 2 — start the MCP server pointing at it
CDP_PORT=9222 projectionlab-mcp
```

## How it works

The Plugin API (`window.projectionlabPluginAPI`) is a JavaScript object injected by ProjectionLab when plugins are enabled. This server calls it by injecting scripts into the browser page via Playwright.

The core flow for most operations is:

1. **`exportData()`** — fetch the full data snapshot as JSON
2. Modify the relevant section in Python (validated with Pydantic models)
3. **`restore*()`** — write the modified section back

```
AI assistant
    │  MCP tool call
    ▼
server.py  (FastMCP tool definitions)
    │
    ▼
plugin_api.py  (Python CRUD logic)
    │  page.evaluate(script)
    ▼
Playwright browser  →  window.projectionlabPluginAPI.*()  →  ProjectionLab
```

## Reverse-engineering the schema

ProjectionLab's export format is undocumented. `docs/schema.md` records everything that has
been verified against real data, and the loop for verifying more is:

```bash
CDP_PORT=9222 .venv/bin/python tools/probe.py snap before   # export -> backups/snap-before.json
#   ...change one thing in the ProjectionLab UI (via the shared browser)...
CDP_PORT=9222 .venv/bin/python tools/probe.py snap after
.venv/bin/python tools/probe.py diff before after            # every added/removed/changed path
.venv/bin/python tools/probe.py show after "plans.[id=<plan>].expenses.events.[id=<event>]"
```

`tests/schema/test_live_export.py` validates the newest backup (or `--live` data) against the
Pydantic models and is the first thing to run after a ProjectionLab release.
`backups/` is gitignored: it holds your real financial data.
