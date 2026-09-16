"""The ``doctor`` command: print the environment report and exit 1 on any failure."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from usdata.doctor import CheckStatus, diagnose

_COLORS = {CheckStatus.OK: "green", CheckStatus.WARN: "yellow", CheckStatus.FAIL: "red"}


def doctor(
    network: Annotated[
        bool, typer.Option("--network", help="Also probe one upstream host per endpoint family.")
    ] = False,
    as_json: Annotated[
        bool, typer.Option("--json", help="Emit the report as a JSON object and nothing else.")
    ] = False,
) -> None:
    """Report the environment, reader extras, cache, and endpoints. Fixes nothing."""
    report = diagnose(network=network)
    if as_json:
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))
    else:
        width = max(len(check.name) for check in report.checks)
        for check in report.checks:
            line = f"{check.name:<{width}}  {check.status.value:<4}  {check.detail}"
            typer.secho(line, fg=_COLORS[check.status])
    if report.failed:
        raise typer.Exit(code=1)
