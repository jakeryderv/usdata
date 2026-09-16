"""Render retained test reports as a compact GitHub Actions job summary."""

from __future__ import annotations

import argparse
import html
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def cell(value: str) -> str:
    return html.escape(value).replace("|", "&#124;").replace("\n", " ").replace("\r", " ")


def junit_summary(path: Path) -> str:
    cases = list(ET.parse(path).getroot().iter("testcase"))
    failed = [c for c in cases if c.find("failure") is not None or c.find("error") is not None]
    skipped = [c for c in cases if c.find("skipped") is not None]
    seconds = sum(float(c.get("time", "0")) for c in cases)
    lines = [
        "| Tests | Passed | Failed/errors | Skipped | Test seconds |",
        "|---:|---:|---:|---:|---:|",
        f"| {len(cases)} | {len(cases) - len(failed) - len(skipped)} | "
        f"{len(failed)} | {len(skipped)} | {seconds:.2f} |",
    ]
    if failed or skipped:
        lines += ["", "| Test | Result | Detail |", "|---|---|---|"]
        for case in failed + skipped:
            detail = next(node for node in case if node.tag in {"failure", "error", "skipped"})
            name = f"{case.get('classname', '')}.{case.get('name', '')}"
            message = detail.get("message") or detail.text or "See retained report"
            lines.append(f"| {cell(name)} | {detail.tag} | {cell(message[:300])} |")
    return "\n".join(lines)


def notebook_summary(path: Path) -> str:
    results = json.loads(path.read_text())
    lines = ["| Notebook | Result | Seconds |", "|---|---|---:|"]
    for result in results:
        # Keep the example name, omitting the hosted checkout prefix.
        name = "/".join(Path(result["path"]).parts[-2:])
        lines.append(f"| {cell(name)} | {cell(result['status'])} | {result['seconds']:.2f} |")
    return "\n".join(lines)


def restore_summary(path: Path) -> str:
    results = json.loads(path.read_text())
    lines = ["| Example | Result | Assets | Bytes | Seconds |", "|---|---|---:|---:|---:|"]
    for result in results:
        name = Path(result["path"]).parent.name
        lines.append(
            f"| {cell(name)} | {cell(result['status'])} | {result['assets']} | "
            f"{result['bytes']:,} | {result['seconds']:.2f} |"
        )
    drifted = [(r, d) for r in results for d in r.get("drift", [])]
    if drifted:
        lines += ["", "| Example | Asset | Problem |", "|---|---|---|"]
        for result, drift in drifted:
            name = Path(result["path"]).parent.name
            lines.append(f"| {cell(name)} | {cell(drift['asset_id'])} | {cell(drift['problem'])} |")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--junit", type=Path)
    source.add_argument("--notebooks", type=Path)
    source.add_argument("--restore", type=Path)
    args = parser.parse_args()
    print(f"### {cell(args.label)}\n")
    path = args.junit or args.notebooks or args.restore
    if not path.exists():
        print("No test report was produced. Check job logs for setup or execution failures.")
    elif args.junit:
        print(junit_summary(path))
    elif args.notebooks:
        print(notebook_summary(path))
    else:
        print(restore_summary(path))
