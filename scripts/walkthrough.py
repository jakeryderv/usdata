"""Run the getting-started guide's own commands against the published package.

The guide at `docs/getting-started.md` is the first thing a new user follows, so
its blocks are extracted here rather than copied: the shell blocks become CLI
invocations, the Python block runs as written, and the manifest block is written
to the file the guide names. Nothing in this script restates a command, so the
guide cannot drift away from the check.

The check runs after publication, against a package installed from PyPI into a
fresh environment with a temporary cache. It reports a broken release; it never
changes one.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "getting-started.md"
BLOCK = re.compile(r"^```(\w+)\n(.*?)^```", re.MULTILINE | re.DOTALL)
SAVE_AS = re.compile(r"[Ss]ave this as `([^`]+)`")
REQUIRED = frozenset({"search", "info", "fetch", "pull", "verify"})


@dataclass(frozen=True)
class Install:
    """The guide's install line, pinned to the version under test by the runner."""

    prefix: tuple[str, ...]
    requirement: str


@dataclass(frozen=True)
class Command:
    """One `usdata` invocation from a shell block, without the program name."""

    arguments: tuple[str, ...]


@dataclass(frozen=True)
class Script:
    """A Python block, run as a file in the walkthrough directory."""

    source: str


@dataclass(frozen=True)
class Write:
    """A block the guide tells the reader to save under a given name."""

    name: str
    content: str


Step = Install | Command | Script | Write


def commands(body: str) -> Iterator[str]:
    """Yield each shell command in a block, joining backslash continuations."""
    pending = ""
    for line in body.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.endswith("\\"):
            pending += text[:-1]
            continue
        yield (pending + text).strip()
        pending = ""
    if pending:
        raise ValueError(f"unterminated continuation in {GUIDE.name}: {pending!r}")


def shell_steps(body: str) -> Iterator[Install | Command]:
    """Turn one shell block into install and CLI steps, rejecting anything else."""
    for command in commands(body):
        tokens = shlex.split(command)
        if tokens[1:4] == ["-m", "pip", "install"]:
            if len(tokens) != 5 or not tokens[4].startswith("usdata"):
                raise ValueError(f"unsupported install command in {GUIDE.name}: {command}")
            yield Install(prefix=tuple(tokens[1:4]), requirement=tokens[4])
        elif tokens[0] == "usdata" and len(tokens) > 1:
            yield Command(arguments=tuple(tokens[1:]))
        else:
            raise ValueError(f"unsupported command in {GUIDE.name}: {command}")


def plan(text: str) -> list[Step]:
    """Extract the guide's steps, in the order a reader performs them."""
    steps: list[Step] = []
    for block in BLOCK.finditer(text):
        language, body = block[1], block[2]
        if language == "sh":
            steps.extend(shell_steps(body))
        elif language == "python":
            steps.append(Script(source=body))
        elif language == "yaml":
            names = SAVE_AS.findall(text[: block.start()])
            if not names:
                raise ValueError(f"{GUIDE.name} has a manifest block with no file name")
            steps.append(Write(name=names[-1], content=body))
    return steps


def missing(steps: list[Step]) -> list[str]:
    """Report guide coverage the walkthrough depends on, so thinning it is visible."""
    subcommands = {step.arguments[0] for step in steps if isinstance(step, Command)}
    gaps = [f"no `usdata {name}` command" for name in sorted(REQUIRED - subcommands)]
    if not any(isinstance(step, Install) for step in steps):
        gaps.append("no install command")
    if not any(isinstance(step, Script) for step in steps):
        gaps.append("no Python block")
    if not any(isinstance(step, Write) for step in steps):
        gaps.append("no manifest block")
    if not cache_dirs(steps):
        gaps.append("no restoration into a second cache")
    return gaps


def cache_dirs(steps: list[Step]) -> set[str]:
    """Collect every explicit `--cache-dir` the guide uses."""
    return {
        step.arguments[index + 1]
        for step in steps
        if isinstance(step, Command)
        for index, argument in enumerate(step.arguments)
        if argument == "--cache-dir" and index + 1 < len(step.arguments)
    }


def run(command: list[str], work: Path, env: dict[str, str]) -> None:
    print(f"$ {shlex.join(command)}", flush=True)
    subprocess.run(command, check=True, cwd=work, env=env)


def install(step: Install, python: Path, version: str, work: Path, env: dict[str, str]) -> None:
    """Install the guide's requirement at the released version, tolerating index lag.

    A stale index page can come from two caches, both honouring PyPI's ten-minute
    ``max-age``. pip's own HTTP cache would hand every retry the page the first
    attempt saw, so it is turned off and each attempt asks the index again. PyPI's
    CDN can also serve an edge's cached page after an upload: the 0.28.0 index was
    stale at one edge for about 80 seconds with pip's cache off. The retry window
    in ``publish.yml`` is there to wait that out. Which cache kept the v0.27.0
    walkthrough failing for its whole ten-minute window was not established.
    """
    command = [str(python), *step.prefix, f"{step.requirement}=={version}"]
    attempts = int(env.get("USDATA_INSTALL_ATTEMPTS", "8"))
    delay = float(env.get("USDATA_INSTALL_DELAY", "20"))
    uncached = {**env, "PIP_NO_CACHE_DIR": "1"}
    for attempt in range(1, attempts + 1):
        try:
            run(command, work, uncached)
            return
        except subprocess.CalledProcessError:
            if attempt == attempts:
                raise
            print(f"install attempt {attempt} failed; retrying in {delay:.0f}s", flush=True)
            time.sleep(delay)


def perform(steps: list[Step], python: Path, cli: Path, version: str, work: Path) -> None:
    """Run every extracted step in order, in a throwaway directory and cache."""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("VIRTUAL_ENV", None)
    env["USDATA_CACHE_DIR"] = str(work / "cache")
    for index, step in enumerate(steps, 1):
        if isinstance(step, Install):
            install(step, python, version, work, env)
        elif isinstance(step, Command):
            run([str(cli), *step.arguments], work, env)
        elif isinstance(step, Script):
            source = work / f"step-{index}.py"
            source.write_text(step.source, encoding="utf-8")
            run([str(python), "-I", str(source)], work, env)
        else:
            (work / step.name).write_text(step.content, encoding="utf-8")
            print(f"wrote {step.name}", flush=True)


def confirm(steps: list[Step], work: Path) -> None:
    """Check that the walkthrough left the files the guide promises the reader."""
    caches = [work / "cache", *(work / name for name in sorted(cache_dirs(steps)))]
    for cache in caches:
        files = [path for path in cache.rglob("*") if path.is_file()]
        if not files:
            raise ValueError(f"{cache.name} holds no fetched files")
        print(f"{cache.name}: {len(files)} files", flush=True)
    for step in steps:
        if not isinstance(step, Write) or not step.name.endswith(".yaml"):
            continue
        lockfile = work / f"{step.name.removesuffix('.yaml')}.lock.json"
        if not lockfile.is_file():
            raise ValueError(f"{lockfile.name} was not written")
        pinned = json.loads(lockfile.read_text(encoding="utf-8"))
        print(f"{lockfile.name}: {len(json.dumps(pinned))} bytes of pinned inputs", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="the released version to install")
    parser.add_argument("--guide", type=Path, default=GUIDE, help="the walkthrough to extract")
    args = parser.parse_args()
    steps = plan(args.guide.read_text(encoding="utf-8"))
    gaps = missing(steps)
    if gaps:
        sys.exit(f"{args.guide.name} no longer covers the walkthrough: " + ", ".join(gaps))
    with TemporaryDirectory(prefix="usdata-walkthrough-") as directory:
        work = Path(directory)
        subprocess.run(
            ["uv", "venv", "--seed", "--python", sys.executable, str(work / "env")],
            check=True,
            cwd=work,
        )
        bindir = work / "env" / ("Scripts" if os.name == "nt" else "bin")
        python = bindir / ("python.exe" if os.name == "nt" else "python")
        cli = bindir / ("usdata.exe" if os.name == "nt" else "usdata")
        perform(steps, python, cli, args.version, work)
        confirm(steps, work)
    print(f"getting-started walkthrough passed against usdata {args.version}")


if __name__ == "__main__":
    main()
