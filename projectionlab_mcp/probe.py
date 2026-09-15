"""
Schema probe: snapshot the ProjectionLab export and diff two snapshots.

This is the core reverse-engineering loop for this repo:

    1. `probe.py snap before`           -> backups/snap-before.json
    2. change something in the UI (shared CDP browser)
    3. `probe.py snap after`            -> backups/snap-after.json
    4. `probe.py diff before after`     -> every added/removed/changed path

Lists whose items carry an `id` are diffed by id (so reordering or inserting
doesn't produce noise); everything else is diffed positionally.

Usage (snapshots land in ./backups, or $PROJECTIONLAB_ROOT/backups):
    CDP_PORT=9222 projectionlab probe snap <label>
    projectionlab probe diff <label-or-path> <label-or-path> [--ignore lastUpdated,...]
    projectionlab probe show <label-or-path> <dotted.path>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

PROJECT_ROOT = os.getenv("PROJECTIONLAB_ROOT", os.getcwd())
BACKUPS = os.path.join(PROJECT_ROOT, "backups")

DEFAULT_IGNORE = {"lastUpdated", "computedMilestones", "simKey"}


# ── snapshot ──────────────────────────────────────────────────────────────────

def _path_for(label: str) -> str:
    if os.path.exists(label):
        return label
    return os.path.join(BACKUPS, f"snap-{label}.json")


async def _export_raw() -> dict:
    from . import plugin_api as api
    return await api._call("exportData")


def snap(label: str) -> str:
    os.makedirs(BACKUPS, exist_ok=True)
    raw = asyncio.run(_export_raw())
    path = _path_for(label)
    with open(path, "w") as f:
        json.dump(raw, f, indent=2, sort_keys=True)
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] snapshot -> {os.path.relpath(path, PROJECT_ROOT)}")
    return path


# ── diff ──────────────────────────────────────────────────────────────────────

def _fmt(v) -> str:
    s = json.dumps(v, sort_keys=True)
    return s if len(s) <= 160 else s[:157] + "..."


def deep_diff(a, b, path: str = "", ignore: set[str] = DEFAULT_IGNORE, out: list | None = None) -> list[str]:
    if out is None:
        out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in ignore:
                continue
            p = f"{path}.{k}" if path else k
            if k not in a:
                out.append(f"+ {p} = {_fmt(b[k])}")
            elif k not in b:
                out.append(f"- {p} = {_fmt(a[k])}")
            else:
                deep_diff(a[k], b[k], p, ignore, out)
    elif isinstance(a, list) and isinstance(b, list):
        keyed = (all(isinstance(x, dict) and "id" in x for x in a)
                 and all(isinstance(x, dict) and "id" in x for x in b)
                 and (a or b))
        if keyed:
            am = {x["id"]: x for x in a}
            bm = {x["id"]: x for x in b}
            for k in am.keys() | bm.keys():
                p = f"{path}[id={k}]"
                if k not in am:
                    out.append(f"+ {p} = {_fmt(bm[k])}")
                elif k not in bm:
                    out.append(f"- {p} = {_fmt(am[k])}")
                else:
                    deep_diff(am[k], bm[k], p, ignore, out)
            if [x["id"] for x in a if x["id"] in bm] != [x["id"] for x in b if x["id"] in am]:
                out.append(f"~ {path} reordered")
        else:
            for i in range(max(len(a), len(b))):
                p = f"{path}[{i}]"
                if i >= len(a):
                    out.append(f"+ {p} = {_fmt(b[i])}")
                elif i >= len(b):
                    out.append(f"- {p} = {_fmt(a[i])}")
                else:
                    deep_diff(a[i], b[i], p, ignore, out)
    elif a != b:
        out.append(f"~ {path}: {_fmt(a)} -> {_fmt(b)}")
    return out


def diff(label_a: str, label_b: str, ignore: set[str]) -> list[str]:
    a = json.load(open(_path_for(label_a)))
    b = json.load(open(_path_for(label_b)))
    lines = deep_diff(a, b, ignore=ignore)
    if not lines:
        print("(no differences)")
    for line in lines:
        print(line)
    return lines


def show(label: str, dotted: str) -> None:
    obj = json.load(open(_path_for(label)))
    for part in dotted.split(".") if dotted else []:
        if part.startswith("[id="):
            wanted = part[4:-1]
            obj = next(x for x in obj if x.get("id") == wanted)
        elif isinstance(obj, list):
            obj = obj[int(part.strip("[]"))]
        else:
            obj = obj[part]
    print(json.dumps(obj, indent=2, sort_keys=True))


# ── cli ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snap"); s.add_argument("label")
    d = sub.add_parser("diff"); d.add_argument("a"); d.add_argument("b")
    d.add_argument("--ignore", default=",".join(sorted(DEFAULT_IGNORE)))
    sh = sub.add_parser("show"); sh.add_argument("label"); sh.add_argument("path", nargs="?", default="")
    args = ap.parse_args()

    if args.cmd == "snap":
        if not os.getenv("CDP_PORT"):
            sys.exit("CDP_PORT is not set (e.g. CDP_PORT=9222).")
        snap(args.label)
    elif args.cmd == "diff":
        diff(args.a, args.b, {x for x in args.ignore.split(",") if x})
    elif args.cmd == "show":
        show(args.label, args.path)


if __name__ == "__main__":
    main()
