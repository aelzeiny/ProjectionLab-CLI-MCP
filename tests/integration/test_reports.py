"""
Manual QA test for report downloads (tables + plots -> CSV/JSON/PDF).

Drives the shared browser (CDP) through projectionlab_mcp.reports.download_report and
checks the exports have the expected shape. Uses the first plan unless one is given.

Usage:
    CDP_PORT=9222 .venv/bin/python tests/integration/test_reports.py [PLAN_ID]
"""
import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

if not os.getenv("CDP_PORT"):
    print("ERROR: CDP_PORT is not set. Start the shared browser first and set CDP_PORT.")
    sys.exit(1)

from projectionlab_mcp import plugin_api as api  # noqa: E402


async def main():
    plan_id = sys.argv[1] if len(sys.argv) > 1 else (await api.list_plans())[0]["id"]
    print(f"plan: {plan_id}")

    for key in ("summaryTable", "netWorth"):
        csv = await api.download_report(plan_id, key, "csv")
        lines = csv.text.splitlines()
        assert csv.filename.endswith(".csv"), csv.filename
        assert lines[0].endswith(f"-projectionlab-report-{csv.name.lower().replace(' ', '-')}"), lines[0]
        assert lines[2].startswith("Year,"), lines[2]
        print(f"  {key:14} csv  {len(lines) - 3:3} rows  header={lines[2][:60]}")

        js = await api.download_report(plan_id, key, "json")
        rows = json.loads(js.text)
        assert isinstance(rows, list) and rows and "Year" in rows[0], rows[:1]
        assert len(rows) == len(lines) - 3, (len(rows), len(lines))
        print(f"  {key:14} json {len(rows):3} rows  cols={list(rows[0])[:4]}")

    pdf = await api.download_report(plan_id, "expensesByCategory", "pdf")
    assert pdf.content.startswith(b"%PDF"), pdf.content[:8]
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf.save(f.name)
    print(f"  expensesByCategory pdf {len(pdf.content)} bytes -> {f.name}")
    print("OK")


if __name__ == "__main__":
    asyncio.run(main())
