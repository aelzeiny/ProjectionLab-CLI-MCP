from typing import Annotated, Any
from pydantic import Field
from mcp.server.fastmcp import FastMCP
from . import plugin_api
import models

mcp = FastMCP("projectionlab-mcp")


@mcp.tool()
async def export_data() -> str:
    """Export all ProjectionLab data (current finances, plans, progress, settings)."""
    result = await plugin_api.export_data()
    return result.model_dump_json(indent=2, by_alias=True)


@mcp.tool()
async def update_account(params: models.AccountUpdate) -> str:
    """Update an account in Current Finances by its ID."""
    await plugin_api.update_account(params.account_id, params.data, params.force)
    return f"Account '{params.account_id}' updated."


@mcp.tool()
async def restore_current_finances(
    new_state: Annotated[dict[str, Any], Field(description="The complete new Current Finances state object.")]
) -> str:
    """Replace the Current Finances state. Warning: overwrites the existing state entirely."""
    await plugin_api.restore_current_finances(new_state)
    return "Current finances restored."


@mcp.tool()
async def restore_plans(
    new_plans: Annotated[Any, Field(description="The new plans data (array or object).")]
) -> str:
    """Replace all Plans. Warning: overwrites all existing plans."""
    await plugin_api.restore_plans(new_plans)
    return "Plans restored."


@mcp.tool()
async def restore_progress(
    new_progress: Annotated[dict[str, Any], Field(description="The new progress state object.")]
) -> str:
    """Replace the Progress state. Warning: overwrites existing progress."""
    await plugin_api.restore_progress(new_progress)
    return "Progress restored."


@mcp.tool()
async def restore_settings(
    new_settings: Annotated[dict[str, Any], Field(description="The new settings object.")]
) -> str:
    """Replace Settings. Warning: overwrites existing settings."""
    await plugin_api.restore_settings(new_settings)
    return "Settings restored."


@mcp.tool()
async def validate_api_key() -> str:
    """Validate that the configured PROJECTIONLAB_API_KEY is correct."""
    await plugin_api.validate_api_key()
    return "API key is valid."


@mcp.tool()
async def list_savings_accounts() -> str:
    """List all savings accounts from Current Finances."""
    accounts = await plugin_api.list_savings_accounts()
    import json
    return json.dumps([a.model_dump() for a in accounts], indent=2)


@mcp.tool()
async def get_savings_account(
    account_id: Annotated[str, Field(description="The ID of the savings account to retrieve.")]
) -> str:
    """Get a single savings account by ID."""
    account = await plugin_api.get_savings_account(account_id)
    return account.model_dump_json(indent=2)


@mcp.tool()
async def create_savings_account(params: models.NewSavingsAccount) -> str:
    """Create a new savings account in Current Finances."""
    account = await plugin_api.create_savings_account(params)
    return f"Savings account '{account.id}' created.\n" + account.model_dump_json(indent=2)


@mcp.tool()
async def delete_savings_account(
    account_id: Annotated[str, Field(description="The ID of the savings account to delete.")]
) -> str:
    """Delete a savings account from Current Finances."""
    await plugin_api.delete_savings_account(account_id)
    return f"Savings account '{account_id}' deleted."


@mcp.tool()
async def list_investment_accounts() -> str:
    """List all investment accounts from Current Finances."""
    import json
    accounts = await plugin_api.list_investment_accounts()
    return json.dumps([a.model_dump(exclude_none=True) for a in accounts], indent=2)


@mcp.tool()
async def get_investment_account(
    account_id: Annotated[str, Field(description="The ID of the investment account to retrieve.")]
) -> str:
    """Get a single investment account by ID."""
    account = await plugin_api.get_investment_account(account_id)
    return account.model_dump_json(indent=2, exclude_none=True)


@mcp.tool()
async def create_taxable_investment_account(params: models.TaxableInvestmentAccount) -> str:
    """Create a new taxable brokerage investment account in Current Finances."""
    account = await plugin_api.create_investment_account(params)
    return f"Taxable investment account '{account.id}' created.\n" + account.model_dump_json(indent=2, exclude_none=True)


@mcp.tool()
async def create_crypto_investment_account(params: models.CryptoInvestmentAccount) -> str:
    """Create a new cryptocurrency investment account in Current Finances."""
    account = await plugin_api.create_investment_account(params)
    return f"Crypto investment account '{account.id}' created.\n" + account.model_dump_json(indent=2, exclude_none=True)


@mcp.tool()
async def create_hsa_investment_account(params: models.HSAInvestmentAccount) -> str:
    """Create a new HSA (Health Savings Account) in Current Finances."""
    account = await plugin_api.create_investment_account(params)
    return f"HSA '{account.id}' created.\n" + account.model_dump_json(indent=2, exclude_none=True)


@mcp.tool()
async def create_529_investment_account(params: models.Plan529InvestmentAccount) -> str:
    """Create a new 529 college savings plan in Current Finances."""
    account = await plugin_api.create_investment_account(params)
    return f"529 plan '{account.id}' created.\n" + account.model_dump_json(indent=2, exclude_none=True)


@mcp.tool()
async def create_ira_investment_account(params: models.IRAInvestmentAccount) -> str:
    """Create a new traditional IRA in Current Finances."""
    account = await plugin_api.create_investment_account(params)
    return f"IRA '{account.id}' created.\n" + account.model_dump_json(indent=2, exclude_none=True)


@mcp.tool()
async def create_inherited_ira_investment_account(params: models.InheritedIRAInvestmentAccount) -> str:
    """Create a new Inherited IRA in Current Finances."""
    account = await plugin_api.create_investment_account(params)
    return f"Inherited IRA '{account.id}' created.\n" + account.model_dump_json(indent=2, exclude_none=True)


@mcp.tool()
async def create_roth_ira_investment_account(params: models.RothIRAInvestmentAccount) -> str:
    """Create a new Roth IRA in Current Finances."""
    account = await plugin_api.create_investment_account(params)
    return f"Roth IRA '{account.id}' created.\n" + account.model_dump_json(indent=2, exclude_none=True)


@mcp.tool()
async def create_inherited_roth_ira_investment_account(params: models.InheritedRothIRAInvestmentAccount) -> str:
    """Create a new Inherited Roth IRA in Current Finances."""
    account = await plugin_api.create_investment_account(params)
    return f"Inherited Roth IRA '{account.id}' created.\n" + account.model_dump_json(indent=2, exclude_none=True)


@mcp.tool()
async def delete_investment_account(
    account_id: Annotated[str, Field(description="The ID of the investment account to delete.")]
) -> str:
    """Delete an investment account from Current Finances."""
    await plugin_api.delete_investment_account(account_id)
    return f"Investment account '{account_id}' deleted."


@mcp.tool()
async def list_plans() -> str:
    """List all plans with their IDs and names."""
    import json
    plans = await plugin_api.list_plans()
    return json.dumps(plans, indent=2)


@mcp.tool()
async def list_milestones(
    plan_id: Annotated[str, Field(description="The ID of the plan whose milestones to list.")]
) -> str:
    """List all milestones for a plan."""
    import json
    milestones = await plugin_api.list_milestones(plan_id)
    return json.dumps([m.model_dump(exclude_none=True) for m in milestones], indent=2)


@mcp.tool()
async def get_milestone(
    plan_id: Annotated[str, Field(description="The ID of the plan.")],
    milestone_id: Annotated[str, Field(description="The ID of the milestone to retrieve.")],
) -> str:
    """Get a single milestone by ID."""
    m = await plugin_api.get_milestone(plan_id, milestone_id)
    return m.model_dump_json(indent=2, exclude_none=True)


@mcp.tool()
async def create_milestone(
    plan_id: Annotated[str, Field(description="The ID of the plan to add the milestone to.")],
    params: models.NewMilestone,
) -> str:
    """Create a new milestone in a plan."""
    m = await plugin_api.create_milestone(plan_id, params)
    return f"Milestone '{m.id}' created.\n" + m.model_dump_json(indent=2, exclude_none=True)


@mcp.tool()
async def update_milestone(
    plan_id: Annotated[str, Field(description="The ID of the plan.")],
    milestone_id: Annotated[str, Field(description="The ID of the milestone to update.")],
    updates: Annotated[dict[str, Any], Field(description='Key/value pairs to update on the milestone (e.g. {"name": "My Goal", "color": "green-lighten-1"}).')],
) -> str:
    """Update fields on an existing milestone."""
    m = await plugin_api.update_milestone(plan_id, milestone_id, updates)
    return f"Milestone '{milestone_id}' updated.\n" + m.model_dump_json(indent=2, exclude_none=True)


@mcp.tool()
async def delete_milestone(
    plan_id: Annotated[str, Field(description="The ID of the plan.")],
    milestone_id: Annotated[str, Field(description="The ID of the milestone to delete.")],
) -> str:
    """Delete a milestone from a plan."""
    await plugin_api.delete_milestone(plan_id, milestone_id)
    return f"Milestone '{milestone_id}' deleted."


def main():
    mcp.run()


if __name__ == "__main__":
    main()


# NOTE: Priority tools are intentionally not exposed here.
# restorePlans() silently strips plan.priorities (plugin API limitation).
# The working implementation using Pinia store mutation lives in plugin_api.py
# and models/priorities.py — see the docstring there for details.
