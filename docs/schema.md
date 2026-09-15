# ProjectionLab export schema (reverse-engineered)

Everything here was verified against real `exportData()` output from ProjectionLab **4.6.0**
(`schema: 4.6`) on 2026-09-13, using the workflow in `tools/probe.py`
(snapshot → change something in the UI → snapshot → diff). Nothing in this file is
inferred from docs or guessed; if a field or value is not listed, it has not been observed.

Pydantic models in `projectionlab_mcp/models/` mirror this document and are validated
against a live export by `tests/schema/test_live_export.py`.

## Top level

```
{
  "meta":     { "version": "4.6.0", "lastUpdated": <epoch ms> },
  "today":    { ... Current Finances ... },
  "plans":    [ { ... plan ... }, ... ],
  "settings": { ... },
  "progress": { "data": [ {savings, loans, taxDeferred, taxable, crypto, taxFree, assets, debt, netWorth, date} ], "lastUpdated" }
}
```

The Plugin API (`window.projectionlabPluginAPI`) exposes exactly:
`exportData`, `updateAccount`, `restoreCurrentFinances`, `restorePlans`, `restoreProgress`,
`restoreSettings`, `validateApiKey`. Every call takes a trailing `{ key }` options object;
without a key it throws `Plugin Operation Failed: Missing Plugin API Key`.

## `today` (Current Finances)

```
location {country, state}, schema, tab, partnerStatus ("married" | ...),
age, birthYear, birthMonth, yourName, yourColor, yourIcon,
spouseAge, spouseAgeGap, spouseBirthYear, spouseBirthMonth, spouseName, spouseColor, spouseIcon,
savingsAccounts[], investmentAccounts[], debts[], assets[], lastUpdated
```

Colors are Vuetify color names (`teal-lighten-1`, `cyan`, `blue-darken-1`, `ink`), icons are
Material Design Icons names (`mdi-piggy-bank`).

### `today.savingsAccounts[]` — verified by creating one with the UI's **Add Savings** button

```json
{
  "id": "<uuid>", "name": "Savings", "title": "Savings", "type": "savings",
  "owner": "me", "balance": 0, "color": "teal-lighten-1", "icon": "mdi-piggy-bank",
  "liquid": true, "withdraw": true, "repurpose": true,
  "investmentGrowthType": "none", "investmentGrowthRate": 0,
  "dividendType": "plan", "dividendRate": 0,
  "withdrawAge": { "type": "keyword", "value": "now", "modifier": "include" }
}
```

The Current Finances page only exposes **Balance** and **Owner** (plus rename, icon/color
picker, notes, reorder, remove). Growth/dividend/withdrawal settings for an account are edited
from the plan editor's Accounts tab, so `today.savingsAccounts[]` records are the *defaults*
and the plan-level copy (below) is where they diverge.

### `today.investmentAccounts[]`

Observed types: `taxable`, `ira`, `401k`, `roth-ira`. Common fields as savings plus
`subtitle`, `yearlyFee`, `yearlyFeeType ("%")`, `investmentGrowthType: "plan"`.
Retirement types add `EWAge`, `EWPenaltyRate`, `hasEWPenalty`, `country`, `rmdType ("us")`;
`roth-ira` adds `withdrawContribsFree`; `taxable` may carry `costBasis`.

### `today.assets[]`

One `real-estate` / `subtype: "rental"` record observed; see the plan-level asset section
for the full field list (identical minus `assetId`/`persistent`/`key`).

## Plans

Plan envelope:

```
id, name, icon, active, initialized, hasNotes, schema (4.6), simKey, lastUpdated,
startingConditionsType ("default"), startingConditions {},
meta { dirty, hasAddedPriorities, index, runKey, wizardStep, yearlySummary },
accounts   { events: [] },
income     { events: [] },
expenses   { events: [] },
assets     { events: [] },
priorities { events: [] },      # the "Flows" tab
milestones [],
computedMilestones [],
variables { ~70 assumption fields },
montecarlo { ... },
withdrawalStrategy { ... }
```

The plan editor's sub-tabs map 1:1 onto these: **Accounts → Income → Expenses → Real Assets → Flows**.

Every event in `*.events` carries `id` (uuid), `name`, `owner ("me" | "spouse")`,
`planPath` (the section name), usually `title`/`icon`/`color`, and often `key` (a random
float used for ordering/reactivity — leave it alone).

### Linking to Current Finances

`plan.accounts.events[]` and `plan.assets.events[]` are *copies* of the Current Finances
records with extra fields:

| field        | meaning                                                                 |
| ------------ | ----------------------------------------------------------------------- |
| `accountId`  | id of the matching `today.investmentAccounts[]`/`savingsAccounts[]` row |
| `assetId`    | id of the matching `today.assets[]` row                                 |
| `persistent` | `true` when linked to Current Finances                                  |
| `planPath`   | `"accounts"` / `"assets"`                                               |

Plan-native items (a 529 the user only plans to open, a house to buy in 2028, a future car)
have **no** `accountId`/`assetId`/`persistent`. Plan copies can diverge from the Current
Finances defaults, e.g. a taxable account with `dividendType: "fixed", dividendRate: 0.27,
monteCarloTreatment: "auto"` while `today` still says `dividendType: "plan"`.

`plan.accounts.events` may also include `excludeFromFinances` (529s) and
`displayAge { type: "keyword", value: "now", modifier: <beneficiary age int> }`.

### Time references (`start`, `end`, `repeatEnd`, `partTimeStart/End`, `pensionPayoutsStart/End`, `effectiveDate`)

All observed shapes:

| type        | value                                                     | modifier              |
| ----------- | --------------------------------------------------------- | --------------------- |
| `keyword`   | `beforeCurrentYear`, `now`, `never`, `endOfPlan`          | optional              |
| `age`       | numeric string, e.g. `"65"`                               | optional              |
| `milestone` | `retirement`, `spouseRetirement`, or a milestone uuid     | usually present       |
| `date`      | `YYYY-MM-01` (month precision)                            | optional              |
| `year`      | `"2059"`                                                  | absent                |

`modifier` is `"include"` or `"exclude"`. Milestone `criteria[]` use the same shape and also
`type: "year"` with a full `YYYY-01-01` value.

### `yearlyChange`

```
{ type: "match-inflation" | "increase" | "decrease" | "appreciate" | "depreciate" | ...,
  amount, amountType ("today$"), limit, limitEnabled, limitType ("today$") }
```

A minimal `{type, amount, amountType}` form (no limit fields) has also been observed on a
non-UI-created event.

### `plan.expenses.events[]`

Verified by adding one expense of **every** choice in the plan editor's "New Expense" dialog
(name + amount only, all other fields at their defaults) and reading the records back. The raw
captures are in `docs/fixtures/expenses/` and `tests/schema/test_expense_fixtures.py` checks
that the Pydantic defaults reproduce them exactly.

| UI choice        | stored `type`       | `subtype`       | icon                        | color                    | default frequency | default start                | default end                          | yearlyChange | spendingType    | extra fields                                                                 |
| ---------------- | ------------------- | --------------- | --------------------------- | ------------------------ | ----------------- | ---------------------------- | ------------------------------------ | ------------ | --------------- | ---------------------------------------------------------------------------- |
| Living Expenses  | `living-expenses`   |                 | `mdi-home-city`             | `blue-lighten-1`         | yearly            | beforeCurrentYear            | endOfPlan (include)                  | match-inflation | essential    |                                                                              |
| Rent             | `rent`              |                 | `mdi-home-currency-usd`     | `teal-lighten-1`         | monthly           | beforeCurrentYear            | endOfPlan (include)                  | match-inflation | essential    |                                                                              |
| Dependent        | `dependent-support` |                 | `mdi-human-child`           | `purple-lighten-1`       | yearly            | beforeCurrentYear            | milestone `retirement` (include)     | match-inflation | essential    |                                                                              |
| Education        | `education`         |                 | `mdi-school`                | `light-green-lighten-1`  | yearly            | beforeCurrentYear            | endOfPlan (include)                  | match-inflation | essential    | `itemized: false`, `taxDeductible: false`                                    |
| Health Care      | `health-care`       |                 | `mdi-heart-plus`            | `pink-lighten-1`         | yearly            | beforeCurrentYear            | endOfPlan (include)                  | inflation+ 2 | essential       | `amountType: "grow$"`, `healthcareType: "standard"`, `deductFromIncomeId: ""` |
| Medical Expenses | `medical`           |                 | `mdi-medical-bag`           | `red-lighten-1`          | yearly            | now (include)                | endOfPlan (include)                  | inflation+ 2 | essential       | `amountType: "grow$"`, `deductFromIncomeId: ""`, `repeat: false`             |
| Vacation         | `vacation`          |                 | `mdi-beach`                 | `cyan-lighten-1`         | yearly            | beforeCurrentYear            | endOfPlan (include)                  | match-inflation | discretionary | `repeat: false`                                                              |
| Travel           | `travel`            |                 | `mdi-airplane`              | `cyan-lighten-1`         | yearly            | now (include)                | endOfPlan (include)                  | match-inflation | discretionary | `repeat: false`                                                              |
| Wedding          | `wedding`           |                 | `mdi-diamond-stone`         | `pink-lighten-1`         | once              | now (include)                | endOfPlan (include)                  | none         | discretionary   | `switchToMarried: false`, `repeat: false`                                    |
| Charity          | `charity`           |                 | `mdi-charity`               | `blue-lighten-1`         | once              | now (include)                | endOfPlan (include)                  | none         | discretionary   | `donationType: "standard"`, `itemized: true`, `taxDeductible: ["federal","state"]`, `repeat: false` |
| Emergency        | `emergency`         |                 | `mdi-weather-lightning`     | `red-lighten-1`          | once              | now (include)                | endOfPlan (include)                  | none         | essential       | `repeat: false`                                                              |
| Custom Expense   | `other`             |                 | `mdi-currency-usd-circle`   | `brown-lighten-1`        | yearly            | beforeCurrentYear            | endOfPlan (include)                  | match-inflation | essential    | `itemized: false`, `taxDeductible: false`, `deductFromIncomeId: ""`, `repeat: false` |
| Debt             | `debt`              |                 | `mdi-weight-pound`          | `orange-lighten-1`       | monthly           | now (include)                | never                                | none         | *(none)*        | see below                                                                    |
| Student Loans    | `debt`              | `student-loans` | `mdi-school`                | `lime-lighten-1`         | monthly           | now (include)                | never                                | none         | *(none)*        | see below                                                                    |
| *(generated)*    | `medicare`          |                 | `mdi-hospital-box`          |                          | yearly            | date                         | endOfPlan (include)                  | match-inflation | essential    | `generated: true`, `_meta: {deletion: "locked"}`, `frequencyChoices: false`, `partA/B/DPremium`, `supplementalPremium`, `supplementalType: "none"`, `healthcareInflationModifier: 2` |

Common fields on every UI-created expense: `id` (uuid), `name`, `title`, `icon`, `color`,
`owner`, `planPath: "expenses"`, `amount`, `amountType`, `frequency`, `frequencyChoices: true`,
`start`, `end`, `yearlyChange`. Pre-existing records also carry `key` (random float).

`debt`-type expenses are loan payoffs modelled as expenses and have their own field set:
`amount` (balance), `monthlyPayment`, `monthlyPaymentType: "today$"`, `interestRate: 0`,
`interestType: "compound"`, `compounding: "daily"`, `effectiveDate` (now, include),
`hasForgiveness: false`, `forgiveAt` (now, include). They have **no** `spendingType`.

Observed enumerations: `frequency` ∈ {`yearly`, `monthly`, `once`}; `spendingType` ∈
{`essential`, `discretionary`} (UI label "Flexibility"); `amountType` ∈ {`today$`, `grow$`};
`yearlyChange.type` ∈ {`match-inflation`, `none`, `inflation+`} (UI label "Change Over Time").
`taxDeductible` is either a bool or a list of jurisdictions (`["federal", "state"]`).

Form fields not yet mapped to JSON (left at defaults during capture): "Pay From" (Automatic),
"Recurrence / Repeat", "Advanced Options", and the Wedding "Update Status to Married" box.

Write path verified on 4.6.0: appending a `type: "other"` event built by
`models.NewCustomExpense(...).to_expense()` to `plan.expenses.events` and calling
`restorePlans()` stores every field byte-for-byte (re-exported record == sent record) and
touches nothing else in the plan except `meta.dirty`. Removing 14 UI-created events the same
way left the plan identical to the pre-experiment snapshot.

**Warning.** Three events with `type: "healthcare"` (no hyphen), ids like
`expense-1773474094865`, and no `title`/`icon`/`color` exist in this account. The UI creates
`health-care` with uuid ids, so these were injected by an earlier automation run. Do not
treat `healthcare` as a valid type.

### `plan.income.events[]`

Verified by adding one income of **every** choice in the "New Income" dialog (name + amount
only) and one Custom Income per dropdown option. Raw captures: `docs/fixtures/income/`;
`tests/schema/test_income_fixtures.py` pins the model defaults to them.

| UI choice        | `type`            | icon                                    | frequency | start                        | end                          | yearlyChange    | tax controls                                   | extra fields                                                                                           |
| ---------------- | ----------------- | --------------------------------------- | --------- | ---------------------------- | ---------------------------- | --------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Salary           | `salary`          | `mdi-office-building`                   | yearly    | beforeCurrentYear            | milestone retirement (incl.) | match-inflation | taxCharacter, taxExempt, withholdingMode       | part-time + pension block (below), `contribsReduceTaxableIncome: true`                                 |
| Hourly Wage      | `hourly`          | `mdi-briefcase-clock`                   | yearly, `frequencyChoices: false` | beforeCurrentYear | milestone retirement (incl.) | match-inflation | same                              | `hoursPerWeek: 40`, `amount` = hourly rate, part-time + pension block                                   |
| RSU Grant        | `rsu`             | `mdi-finance`                           | once      | now (incl.)                  | milestone retirement (incl.) | none            | same                                           | `repeat: false`                                                                                        |
| Side Hustle      | `side-hustle`     | `mdi-piggy-bank`                        | yearly    | beforeCurrentYear            | milestone retirement (incl.) | none            | same, `taxCharacter: "selfEmployment"`         | `repeat: false`                                                                                        |
| Custom Income    | `other`           | `mdi-currency-usd-circle`               | yearly    | beforeCurrentYear            | milestone retirement (incl.) | match-inflation | same                                           | `preventOverflow: false`, `repeat: false`                                                              |
| Inheritance      | `inheritance`     | `mdi-gift`                              | once      | now (incl.)                  | milestone retirement (incl.) | none            | taxCharacter, taxExempt (no withholding)       | `repeat: false`                                                                                        |
| Tax Credit       | `tax-credit`      | `mdi-file-document-outline`             | once      | now (incl.)                  | milestone retirement (incl.) | none            | none                                           | `jurisdictions: ["federal"]`, `taxType: "income"`, `refundable: false`, `repeat: false`                |
| Tax Deduction    | `tax-deduction`   | `mdi-file-document-outline`             | once      | now (incl.)                  | milestone retirement (incl.) | none            | none                                           | `jurisdictions: ["federal"]`, `taxType: "income"`, `itemized: false`, `repeat: false`                  |
| Pension Income   | `pension`         | `mdi-account-clock`                     | yearly    | milestone retirement (incl.) | endOfPlan (incl.)            | match-inflation | taxExempt, withholdingMode (no taxCharacter)   |                                                                                                        |
| Social Security  | `social-security` | `mdi-account-supervisor-circle-outline` | yearly    | date (birth date + 67y)      | endOfPlan (incl.)            | match-inflation | taxExempt                                      | `amount: 0`, `country: "US"`, `estimateIncome: true`, `expectedPercent: 100`, `primaryInsuranceAmount` |

Common fields: `id`, `name`, `title`, `icon`, `owner`, `planPath: "income"`, `amount`,
`amountType: "today$"`, `frequency`, `frequencyChoices`, `start`, `end`, `yearlyChange`.
Income events have **no** `color`. Pre-existing records may also carry `key` and `hidden`.

Part-time + pension block (Salary, Hourly Wage): `goPartTime: false`, `partTimeStart` (now,
include), `partTimeEnd` (retirement, include), `partTimeRate: 50`, `hasPension: false`,
`pensionContribution: 0`, `pensionContributionType: "%"`, `pensionPayoutAmount: 0`,
`pensionPayoutRate: 25`, `pensionPayoutType: "fap"`, `pensionPayoutsAreTaxFree: false`,
`pensionPayoutsStart` (retirement, include), `pensionPayoutsEnd` (endOfPlan, include).

Dropdown label → stored value (captured on Custom Income):

| control            | field                        | label → value                                                                                                                                             |
| ------------------ | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Earner             | `owner`                      | You → `me`, spouse name → `spouse`, Joint → *(not captured)*                                                                                              |
| Frequency          | `frequency`                  | Yearly → `yearly`, Once Per Year → `yearly-lump-sum`, Quarterly → `quarterly`, Monthly → `monthly`, Bi-Weekly → `bi-weekly`, Weekly → `weekly`, Daily → `daily`, Once → `once` (also sets `start` to now/include) |
| Change Over Time   | `yearlyChange.type`          | None → `none`, Increase → `increase`, Decrease → `decrease`, Match Inflation → `match-inflation`, Match Inflation +X% → `inflation+`, Match Inflation -X% → `inflation-`, Advanced → *(not captured)*; X goes in `yearlyChange.amount` |
| Tax Handling Type  | `taxCharacter`               | Auto → `auto`, Wage → `wage`, Self-Employment → `selfEmployment`, Ordinary → `ordinary`, Dividend → `dividend`, Capital Gains → `capGains`                 |
| Withholding        | `withholdingMode`            | Auto → `auto`, Fixed Rate → `fixed` (+ `withholdingRate` percent), None → `none`                                                                          |
| Passive Income     | `isPassiveIncome`            | Auto → field absent, Yes → `true`, No → `false`                                                                                                           |
| Send To            | `routeToAccounts`            | Automatic → field absent, Specific Account → `[<plan.accounts event id>]` (the plan-level id, not the Current Finances id)                                 |
| Recurrence: Repeat | `repeat` + friends           | `repeat: true`, `repeatEnd` (endOfPlan, include), `repeatInterval: 0`, `repeatIntervalType: "between"`, `repeatScaler: 0`                                 |
| Tax-Exempt         | `taxExempt`                  | checkbox → `true`/`false` (per-jurisdiction detail not captured)                                                                                          |

Not yet captured: the "Advanced" change-over-time mode, Joint earner, the Part-Time and
Defined Benefit Pension sub-forms with non-default values, and "Advanced Options" on types
other than Custom Income.

**Schema history.** The earlier income models (March 2026) wrote `taxWithholding`, `withhold`,
`selfEmployment`, `wage`, `isDividendIncome`, `isPassiveIncome` and left `title` = name. On
4.6.0 the UI writes none of those; tax handling is `taxCharacter` + `withholdingMode` +
`withholdingRate`. The integration scripts in `tests/integration/test_*_income.py` still
assert the old fields and need re-recording.

Write path verified on 4.6.0 for `side-hustle`, `tax-credit`, `social-security` and `other`:
stored record == sent record, and the events survive a reload.

### `plan.priorities.events[]` (Flows)

Types observed: `asset`, `529`, `taxable`. Fields: `accountId`/`assetId`, `amount`,
`amountType`, `contributionsAreFixed`, `country`, `desiredContribution`, `extra`,
`extraType`, `frequency`, `goalIntent`, `maxMsg`, `persistent`, `taxDeductible`, plus the
common set. An earlier session found `restorePlans()` **dropped** `plan.priorities`, so the
repo writes priorities by mutating the Pinia store directly (`plugin_api._pinia_mutate_priorities`).
On 4.6.0 a `restorePlans()` round trip (add one expense, delete it) left all 4 priorities intact,
so re-test before relying on either behaviour.

### `plan.milestones[]`

`{ id, name, icon, color, removable, criteria: [ {type, value, modifier?} | metric criteria ] }`.
See `projectionlab_mcp/models/milestones.py`.

## Persistence of Plugin API writes

`restorePlans()` / `restoreCurrentFinances()` update the in-memory Pinia store immediately
(`exportData()` reflects the change at once) but the save to ProjectionLab's backend is
asynchronous. Reloading the page ~1 s after a `restorePlans()` lost the write; waiting 10 s
before reloading kept it. Give the app a few seconds after any write before navigating or
reloading, and never treat "it shows in exportData" as proof it was saved.

The app logs `PlanEventFormUtils: No data model found for healthcare event` on load, which
confirms the three `type: "healthcare"` records above are unknown to ProjectionLab itself.

## Still unverified

- Full option lists for `frequency`, `spendingType`, `investmentGrowthType`, `dividendType`,
  `yearlyChange.type` (only the values above have been seen; the dropdowns have not been opened).
- The add-account / add-asset / add-income forms in the plan editor, and the expense form's
  "Pay From", "Recurrence" and "Advanced Options" fields.
- `settings`, `variables`, `montecarlo`, `withdrawalStrategy` internals.

## Verified 2026-09-15 (plan build session)

- **Creating a plan**: no API; deep-copy an existing plan with a fresh `id`, `simKey`, `meta.index`, append it to the
  exported `plans` list and `restorePlans()` the whole list. On 4.6.0 the new plan's `priorities.events` survived the
  round trip and a later reload.
- **Current Finances → plan copies**: a new `today` savings/investment account, asset or debt is mirrored into every
  plan on load (`accountId` / `assetId` / `debtId` + `persistent: true`; debts land in `plan.expenses.events` as
  `type: "debt"`). On every reload `name`, `balance` and `monthlyPayment` of linked items are re-synced from `today`;
  ratios (`taxRate`, `monthlyHOA`, …) and `start`/`end` on the plan copy are left alone.
- **401k priority** as the UI writes it: `type: "401k"`, `accountId` (plan-level), `incomeStreamId` (plan-level
  salary event id), `contribution` + `contributionType: "%"`, `contributionLimit: 0`, `employerMatch` +
  `employerMatchType: "%"`, `employerMatchLimit: 0`, `employerMatchIsRoth`, `catchUpContributionsAreRoth`,
  `reduceEmployerMatch: true`, `contributionsAreFixed`, `yearlyLimitType: "us"`, `yearlyLimit: 0`,
  `yearlyLimit$Type: "today$"`, `country: "US"`, `goalIntent: "invest"`, `title: "401k"`. The
  `NewInvestmentPriority(type="401k", desiredContribution="max")` shape contributes nothing in the simulation.
- **Debt payoff priority** ("Extra Debt Payments"): `type: "debt"`, `goalIntent: "pay-extra"`, `debtId` = the
  plan-level debt expense event id, `desiredContribution: "amount"`, `extra`, `extraType: "today$"`,
  `frequency: "monthly"`, `contributionsAreFixed`, `start`/`end`. A one-month start/end window is a lump payment.
- **Funding**: `contributionsAreFixed: true` is the UI's "Always Fund" (fund even without surplus income, drawing
  from accounts); `false` is "Fund with Income". `pay-extra` flows on assets only spend surplus, so a payment the
  user always makes is better modelled as the asset's `monthlyPayment`.
- `variables.startDate` is the date the simulation starts from (a copied plan keeps the source plan's old date).
  `{type: "year"}` refs on expenses did not behave (an end of `"2059"` ended the event in the first year); use
  `date` refs. `withdrawalStrategy.enabled` overrides the expense events after retirement.
- **Reading simulation results** (Pinia): after `$router.push('/plan/<id>')`,
  `pinia._s.get('plan').$state.plan._runtime.results` holds `outcome.status`, `_meta` (`netWorthAtRetirement`,
  `finalNetWorth`), `data[]` per year with `summary.<metric>.actualTotal` and `.events`/`.sections`,
  `notableEvents[]`; `_runtime.warnings[]` are the plan's warning chips. Stringify inside the page.
- `amountType: "grow$"` on an income event is ignored by the simulation (an RSU event stored as grow$ was still
  inflated). To book a fixed nominal amount N in year Y, store today$ `N / inflation^(Y - startYearFraction)`
  (with a 2026-09-15 start the observed factors were 1.0098 for 2027 and 1.0431 for 2028 at 3.3%).
- `NewCashPriority(type="emergency-fund", goalIntent="maintain", amount=…)` on a savings account works as the
  UI's cash-reserve goal: the account is kept at the target while `drawdownOrder` starts with `excess-cash`.

## Reports tab export (verified 2026-09-15, app 4.6.0)

`/plan/<id>/reports` has no Plugin API; `projectionlab_mcp/reports.py` drives the UI.

- Toolbar (the `div.v-row` containing the **Explore** button): `[Explore] [Tables ▾] [Plots ▾] … [tune] [fullscreen] [download ▾] [dots ▾]`.
  Button 1 lists the 3 tables, button 2 the 41 plots (first row "Built-in Plots" is a disabled header).
  Selecting one relabels its button with the report name and resets the other button to "Tables"/"Plots".
- Every `.v-list-item` in those menus has `path="<key>"` and `name="<label>"` attributes; `path` is the stable id
  (labels collide: "Spending" = `spendingByCategory` | `granularSpending`, "Income" = `incomeTable` | `incomeByCategory`).
- The download button's menu offers **CSV / JSON / PDF**. All three are generated client-side and served as a
  `blob:` download named `YYYY-MM-DD-projectionlab-report-<slug>.<ext>`; Playwright's `expect_download` captures it
  over the CDP connection.
- CSV = title line, blank line, then a `Year,...` header and one row per projection year (the summary table has an
  extra "current" row for the start year with blank cells). JSON = list of row objects keyed by column label.
- Playwright gotcha: `.v-list-item:text-is("CSV")` does not match (the text pseudo-class resolves to the innermost
  span); filter the item locator with `has_text=re.compile(r"^\s*CSV\s*$")` instead.
