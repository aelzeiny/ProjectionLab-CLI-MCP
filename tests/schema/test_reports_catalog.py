"""
Offline check of the report catalog and name resolution in projectionlab_mcp.reports.

Usage:
    .venv/bin/python tests/schema/test_reports_catalog.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from projectionlab_mcp.reports import REPORTS, resolve_report  # noqa: E402


def main() -> None:
    kinds = {k: v[0] for k, v in REPORTS.items()}
    assert sum(1 for k in kinds.values() if k == "table") == 3
    assert sum(1 for k in kinds.values() if k == "plot") == 41

    assert resolve_report("netWorth") == "netWorth"
    assert resolve_report("networth") == "netWorth"          # key, case-insensitive
    assert resolve_report("Net Worth") == "netWorth"         # unique UI name
    assert resolve_report("summary") == "summaryTable"       # unique UI name

    for ambiguous in ("Spending", "Income"):
        try:
            resolve_report(ambiguous)
        except ValueError as e:
            assert "ambiguous" in str(e), e
        else:
            raise AssertionError(f"{ambiguous!r} should be ambiguous")

    try:
        resolve_report("bogus")
    except ValueError as e:
        assert "Unknown report" in str(e)
    else:
        raise AssertionError("unknown report should raise")
    print("OK")


if __name__ == "__main__":
    main()
