"""
Offline check: the expense models' defaults reproduce the records ProjectionLab's own
"New Expense" dialog creates (captured in docs/fixtures/expenses/*.json).

For every fixture:
  1. the record parses with the model registered for its `type`;
  2. constructing that model from only id/name/amount (plus the Student Loans subtype
     overrides) dumps to exactly the captured record.

Re-capture the fixtures with the UI loop described in docs/schema.md after a ProjectionLab
release; if this test fails, the app's defaults changed.

Usage:
    .venv/bin/python tests/schema/test_expense_fixtures.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from projectionlab_mcp import models  # noqa: E402
from projectionlab_mcp.models.expenses import student_loans_defaults  # noqa: E402

FIXTURES = os.path.join(PROJECT_ROOT, "docs", "fixtures", "expenses", "*.json")


def main() -> None:
    failures = 0
    for path in sorted(glob.glob(FIXTURES)):
        rec = json.load(open(path))
        name = os.path.basename(path)
        model = models.EXPENSE_MODELS.get(rec["type"])
        if model is None:
            failures += 1
            print(f"  ✗ {name}: no model for type {rec['type']!r}")
            continue
        try:
            model.model_validate(rec)
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"  ✗ {name}: does not parse as {model.__name__}: {str(e).splitlines()[1:3]}")
            continue
        kwargs = {"id": rec["id"], "name": rec["name"], "amount": rec["amount"]}
        if rec.get("subtype") == "student-loans":
            kwargs.update(student_loans_defaults())
        built = model(**kwargs).model_dump(exclude_none=True, by_alias=True)
        diff = {k: (built.get(k), rec.get(k)) for k in set(built) | set(rec) if built.get(k) != rec.get(k)}
        if diff:
            failures += 1
            print(f"  ✗ {name}: defaults differ from UI record: {json.dumps(diff, sort_keys=True)}")
        else:
            print(f"  ✓ {name:32} {model.__name__}")
    print("\nRESULT:", "PASS" if not failures else f"FAIL ({failures} problems)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
