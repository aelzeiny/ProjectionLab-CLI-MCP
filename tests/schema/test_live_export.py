"""
Schema drift check: validate a real exportData() dump against the Pydantic models.

Reads the newest `backups/export-*.json` (or a path given as argv[1]); pass `--live`
to export from the shared CDP browser first. Exits non-zero on any validation error,
and prints every section's pass/fail so drift is obvious after a ProjectionLab release.

Usage:
    .venv/bin/python tests/schema/test_live_export.py                # newest backup
    .venv/bin/python tests/schema/test_live_export.py backups/x.json
    CDP_PORT=9222 .venv/bin/python tests/schema/test_live_export.py --live
"""
from __future__ import annotations

import asyncio
import glob
import json
import os
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from projectionlab_mcp import models  # noqa: E402

# Records the UI never creates (see docs/schema.md); reported as warnings, not failures.
KNOWN_NON_UI_TYPES = {"healthcare"}

INCOME_MODELS = models.INCOME_MODELS


def _load(arg: str | None) -> dict:
    if arg == "--live":
        from projectionlab_mcp import plugin_api as api
        raw = asyncio.run(api._call("exportData"))
        os.makedirs(os.path.join(PROJECT_ROOT, "backups"), exist_ok=True)
        path = os.path.join(PROJECT_ROOT, "backups", f"export-{time.strftime('%Y%m%d-%H%M%S')}.json")
        json.dump(raw, open(path, "w"), indent=2)
        print(f"exported live data -> {os.path.relpath(path, PROJECT_ROOT)}")
        return raw
    path = arg or sorted(glob.glob(os.path.join(PROJECT_ROOT, "backups", "export-*.json")))[-1]
    print(f"validating {os.path.relpath(path, PROJECT_ROOT)}")
    return json.load(open(path))


def _check(label: str, items: list[dict], model_for) -> int:
    failures = 0
    for it in items:
        model = model_for(it)
        if model is None and it.get("type") in KNOWN_NON_UI_TYPES:
            print(f"  ! [{label}] non-UI record type={it.get('type')!r} name={it.get('name')!r} (ignored)")
            continue
        if model is None:
            failures += 1
            print(f"  ✗ [{label}] no model for type={it.get('type')!r} name={it.get('name')!r}")
            continue
        try:
            model.model_validate(it)
        except Exception as e:  # noqa: BLE001
            failures += 1
            detail = " | ".join(line.strip() for line in str(e).splitlines()[1:5])
            print(f"  ✗ [{label}] {model.__name__} name={it.get('name')!r}: {detail}")
    print(f"  {'✓' if not failures else '✗'} [{label}] {len(items) - failures}/{len(items)} OK")
    return failures


def main() -> None:
    raw = _load(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"app version {raw['meta']['version']}, today.schema {raw['today'].get('schema')}")
    failures = 0

    try:
        models.PLExport.model_validate(raw)
        print("  ✓ [PLExport] top level + today OK")
    except Exception as e:  # noqa: BLE001
        failures += 1
        print("  ✗ [PLExport]", " | ".join(line.strip() for line in str(e).splitlines()[:8]))

    for plan in raw["plans"]:
        p = plan["name"]
        failures += _check(f"{p}/income", plan["income"]["events"], lambda it: INCOME_MODELS.get(it.get("type")))
        failures += _check(f"{p}/expenses", plan["expenses"]["events"], lambda it: models.EXPENSE_MODELS.get(it.get("type")))
        failures += _check(f"{p}/milestones", plan["milestones"], lambda it: models.Milestone)
        failures += _check(f"{p}/priorities", plan["priorities"]["events"], lambda it: models.Priority)

    print("\nRESULT:", "PASS" if not failures else f"FAIL ({failures} problems)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
