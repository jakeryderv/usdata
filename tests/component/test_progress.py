from __future__ import annotations

import gzip
from collections.abc import Iterator
from importlib import import_module
from io import StringIO
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata import build_query, default_registry
from usdata._progress import AssetProgress, Batch, Event, TransferProgress, emit, observe
from usdata.cli import app
from usdata.cli.progress import _Display
from usdata.fetch import ChecksumMismatch, fetch
from usdata.protocols import http
from usdata.providers.noaa.ghcnd import DATA_URL
from usdata.pull import pull

cli_progress = import_module("usdata.cli.progress")
DATA = b"STATION,PRCP\nUSW00013967,1.2\n"
ARGS = [
    "fetch",
    "noaa:ghcn-daily",
    "-p",
    "stations=USW00013967",
    "--start",
    "2024-05-06",
    "--end",
    "2024-05-07",
]
MANIFEST = """name: progress
sources:
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    params: {stations: USW00013967}
"""


def test_observer_nesting_and_exception_restore() -> None:
    outer: list[Event] = []
    inner: list[Event] = []
    event = Batch(1, 0, 1)
    with observe(outer.append):
        emit(event)
        with pytest.raises(ValueError), observe(inner.append):
            emit(event)
            raise ValueError("failed")
        emit(event)
    emit(event)
    assert outer == [event, event]
    assert inner == [event]


class InterruptedStream(httpx.SyncByteStream):
    def __iter__(self) -> Iterator[bytes]:
        yield b"partial"
        raise httpx.ReadError("connection lost")


class UnknownLengthStream(httpx.SyncByteStream):
    def __iter__(self) -> Iterator[bytes]:
        yield DATA


def test_retry_resets_download_bytes_and_reports_current_attempt(tmp_path: Path) -> None:
    events: list[Event] = []
    with respx.mock() as mock, observe(events.append):
        mock.get(DATA_URL).side_effect = [
            httpx.Response(200, stream=InterruptedStream()),
            httpx.Response(200, content=DATA),
        ]
        http.download(DATA_URL, tmp_path / "data")
    assert TransferProgress(7, None, 1) in events
    assert TransferProgress(0, None, 2) in events
    assert events[-1] == TransferProgress(len(DATA), len(DATA), 2)
    assert (tmp_path / "data").read_bytes() == DATA


@pytest.mark.parametrize("encoded", [False, True])
def test_unknown_or_encoded_length_never_becomes_a_false_total(tmp_path: Path, encoded) -> None:
    events: list[Event] = []
    response = (
        httpx.Response(200, content=gzip.compress(DATA), headers={"Content-Encoding": "gzip"})
        if encoded
        else httpx.Response(200, stream=UnknownLengthStream())
    )
    with respx.mock() as mock, observe(events.append):
        mock.get(DATA_URL).return_value = response
        http.download(DATA_URL, tmp_path / "data")
    assert events[-1] == TransferProgress(len(DATA), None, 1)
    assert (tmp_path / "data").read_bytes() == DATA


def test_cache_hits_have_no_transfer_events_and_force_downloads(tmp_path: Path) -> None:
    dataset = default_registry().get("noaa:ghcn-daily")
    query = build_query(start="2024-05-06", end="2024-05-07", stations="USW00013967")
    events: list[Event] = []
    with respx.mock() as mock, observe(events.append):
        route = mock.get(DATA_URL).respond(200, content=DATA)
        first = fetch(dataset, query, root=tmp_path)
        assert events[0] == Batch(1, 0, 1)
        assert events[-1] == AssetProgress(first[0].asset.id, "fetched", len(DATA))
        events.clear()
        fetch(dataset, query, root=tmp_path)
        assert route.call_count == 1
        assert not any(isinstance(event, TransferProgress) for event in events)
        assert events[-1] == AssetProgress(first[0].asset.id, "cached", len(DATA))
        fetch(dataset, query, root=tmp_path, force=True)
        assert route.call_count == 2


def test_locked_restore_reports_sizes_cache_and_rejects_false_completion(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=DATA)
        first = pull(manifest, root=tmp_path)
    events: list[Event] = []
    with respx.mock(), observe(events.append):
        pull(manifest, root=tmp_path)
    assert events == [
        Batch(1, len(DATA), 0),
        AssetProgress(first.fetched[0].asset.id, "start", len(DATA)),
        AssetProgress(first.fetched[0].asset.id, "cached", len(DATA)),
    ]
    first.fetched[0].path.unlink()
    events.clear()
    with respx.mock() as mock, observe(events.append), pytest.raises(ChecksumMismatch):
        mock.get(DATA_URL).respond(200, content=b"changed upstream")
        pull(manifest, root=tmp_path)
    assert not any(
        isinstance(event, AssetProgress) and event.state == "fetched" for event in events
    )
    assert not first.fetched[0].path.exists()


@pytest.mark.parametrize("interactive,disabled", [(False, False), (True, True), (True, False)])
def test_cli_fetch_progress_is_separate_and_opt_out_works(
    tmp_path: Path, monkeypatch, interactive, disabled
) -> None:
    monkeypatch.setattr(cli_progress, "_interactive", lambda: interactive)
    args = ARGS + ["--cache-dir", str(tmp_path)] + (["--no-progress"] if disabled else [])
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=DATA)
        result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    path, tag, size = result.stdout.strip().split("\t")
    assert Path(path).is_file() and tag == "fetched" and size == f"{len(DATA)} bytes"
    assert "\r" not in result.stdout and "\x1b" not in result.stdout
    if interactive and not disabled:
        assert "1 size(s) unknown" in result.stderr and "attempt 1" in result.stderr
        assert "[1/1] fetched" in result.stderr
    else:
        assert result.stderr == ""


def test_cli_failure_clears_progress_without_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli_progress, "_interactive", lambda: True)
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(503)
        result = CliRunner().invoke(app, [*ARGS, "--cache-dir", str(tmp_path)])
    assert result.exit_code == 4 and result.stdout == ""
    assert "attempt 3" in result.stderr and "request failed" in result.stderr
    assert "[1/1]" not in result.stderr
    assert "\rrequest failed" in result.stderr


def test_cli_pull_progress_and_redirected_restore(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    monkeypatch.setattr(cli_progress, "_interactive", lambda: True)
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=DATA)
        result = CliRunner().invoke(app, ["pull", str(manifest), "--cache-dir", str(tmp_path)])
    assert result.exit_code == 0 and "[1/1] fetched" in result.stderr
    monkeypatch.setattr(cli_progress, "_interactive", lambda: False)
    with respx.mock():
        restored = CliRunner().invoke(app, ["pull", str(manifest), "--cache-dir", str(tmp_path)])
    assert restored.exit_code == 0 and "\tcached\t" in restored.stdout
    assert restored.stderr == f"1 asset(s); restored from {tmp_path / 'dataset.lock.json'}\n"


@pytest.mark.parametrize(
    "stdout_tty,stderr_tty", [(False, False), (True, False), (False, True), (True, True)]
)
def test_interactivity_requires_both_streams(monkeypatch, stdout_tty, stderr_tty) -> None:
    monkeypatch.setattr(cli_progress.sys.stdout, "isatty", lambda: stdout_tty)
    monkeypatch.setattr(cli_progress.sys.stderr, "isatty", lambda: stderr_tty)
    assert cli_progress._interactive() == (stdout_tty and stderr_tty)


def test_display_mixed_sizes_throttles_updates_and_sanitizes_ids(monkeypatch) -> None:
    monkeypatch.setattr(cli_progress, "monotonic", lambda: 1.0)
    stream = StringIO()
    display = _Display(stream)
    display(Batch(2, 1024, 1))
    assert "1,024 known bytes; 1 size(s) unknown" in stream.getvalue()
    display(AssetProgress("id\x1b\n", "start", 1024))
    assert "id??" in stream.getvalue() and "\x1b" not in stream.getvalue()
    display(TransferProgress(0, 1024, 1))
    previous = stream.getvalue()
    display(TransferProgress(100, 1024, 1))
    assert stream.getvalue() == previous
    display(TransferProgress(0, None, 2))
    assert "0/unknown bytes (attempt 2)" in stream.getvalue()
    display(AssetProgress("id", "cached", 1024))
    display(AssetProgress("other", "fetched", 5))
    assert "[2/2] fetched (5 bytes; 1 cached)" in stream.getvalue()
    assert stream.getvalue().endswith("\n")


def test_dry_run_retains_records_and_reports_unknown_sizes_only_on_terminal(monkeypatch) -> None:
    runner = CliRunner()
    redirected = runner.invoke(app, [*ARGS, "--dry-run"])
    monkeypatch.setattr(cli_progress, "_interactive", lambda: True)
    terminal = runner.invoke(app, [*ARGS, "--dry-run"])
    assert terminal.exit_code == redirected.exit_code == 0
    assert terminal.stdout == redirected.stdout
    assert redirected.stderr == "1 asset(s) matched\n"
    assert "1 size(s) unknown" in terminal.stderr
