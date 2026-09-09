import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "run_notebooks", ROOT / "scripts/run_notebooks.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def notebook(text: str) -> dict:
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {
                "cell_type": "code",
                "metadata": {},
                "source": ["print('ok')"],
                "execution_count": 1,
                "outputs": [{"output_type": "stream", "name": "stdout", "text": [text]}],
            }
        ],
    }


@pytest.mark.parametrize("fail", [False, True])
def test_runner_retains_diagnostics_continues_and_refreshes_only_on_success(runner, tmp_path, fail):
    paths = [tmp_path / f"{index}.ipynb" for index in range(3)]
    for path in paths:
        path.write_text(json.dumps(notebook("original")))
    called = []

    def execute(source, output, kernel_dir):
        called.append(source.name)
        output.write_text(json.dumps(notebook("executed")))
        if fail and source.name == "1.ipynb":
            raise RuntimeError("simulated upstream failure")

    reports = tmp_path / "reports"
    errors = runner.run_notebooks(paths, reports, write=True, execute=execute)
    assert called == [path.name for path in paths]
    assert len(errors) == int(fail)
    expected = "original" if fail else "executed"
    assert all(
        json.loads(path.read_text())["cells"][0]["outputs"][0]["text"] == [expected]
        for path in paths
    )
    summary = json.loads((reports / "summary.json").read_text())
    assert [r["status"] for r in summary] == ["passed", "failed" if fail else "passed", "passed"]
    assert all((reports / r["output"]).exists() for r in summary)
    if fail:
        assert "simulated upstream failure" in (reports / summary[1]["error"]).read_text()


def test_runner_does_not_report_stale_outputs_after_early_failure(runner, tmp_path):
    source = tmp_path / "example.ipynb"
    source.write_text(json.dumps(notebook("original")))
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "0-example.ipynb").write_text("stale success")

    def fail_before_reading(*args):
        raise ValueError("malformed input")

    assert runner.run_notebooks([source], reports, execute=fail_before_reading)
    summary = json.loads((reports / "summary.json").read_text())
    assert summary[0]["output"] is None
    assert not (reports / "0-example.ipynb").exists()


def test_live_inventory_discovers_new_examples_and_excludes_checkpoints(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    ci_inventory = importlib.import_module("ci_inventory")

    live = tmp_path / "tests/live"
    live.mkdir(parents=True)
    (live / "test_new_live.py").touch()
    example = tmp_path / "examples/new/example.ipynb"
    example.parent.mkdir(parents=True)
    example.touch()
    checkpoint = example.parent / ".ipynb_checkpoints/example.ipynb"
    checkpoint.parent.mkdir()
    checkpoint.touch()
    data = ci_inventory.inventory(tmp_path)
    assert data["live"] == [
        {"id": "test_new_live", "path": "tests/live/test_new_live.py", "extra": "core"}
    ]
    assert data["notebooks"] == [{"id": "example-0", "path": "examples/new/example.ipynb"}]


def test_inventory_focus_rejects_unknown_and_ambiguous_targets(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = importlib.import_module("ci_inventory")
    select_inventory = module.select_inventory
    data = module.inventory()
    focused = select_inventory(data, "live", "coops")
    assert [entry["id"] for entry in focused["live"]] == ["test_coops_live"]
    assert focused["notebooks"] == []
    assert select_inventory(data, "all") == data
    assert select_inventory(data, "minimum") == {"live": [], "notebooks": []}
    notebook = select_inventory(data, "notebooks", "sst-analysis")
    assert len(notebook["notebooks"]) == 1 and not notebook["live"]
    for scope, target in [("all", "coops"), ("minimum", "coops"), ("live", "$(echo x)")]:
        with pytest.raises(ValueError):
            select_inventory(data, scope, target)
    duplicates = {"live": data["live"] * 2, "notebooks": data["notebooks"]}
    with pytest.raises(ValueError, match="exactly one"):
        select_inventory(duplicates, "live", "coops")
