import importlib.util
import json
import os
import sys
import types
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

    def execute(source, output, kernel_dir, cache_dir):
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


def test_runner_gives_each_notebook_a_fresh_cache_unless_one_is_reused(runner, tmp_path, capsys):
    paths = [tmp_path / f"{index}.ipynb" for index in range(2)]
    for path in paths:
        path.write_text(json.dumps(notebook("original")))
    caches = []

    def execute(source, output, kernel_dir, cache_dir):
        assert cache_dir.is_dir()
        caches.append(cache_dir)
        output.write_text(json.dumps(notebook("executed")))

    runner.run_notebooks(paths, tmp_path / "fresh", execute=execute)
    assert len(set(caches)) == 2
    assert "warm cache" not in capsys.readouterr().out

    warm = tmp_path / "warm"
    caches.clear()
    runner.run_notebooks(paths, tmp_path / "reports", cache_dir=warm, execute=execute)
    assert caches == [warm, warm]
    printed = capsys.readouterr().out
    assert printed.count(f"Reusing warm cache {warm}") == 2


def test_runner_environment_points_the_notebook_at_the_resolved_cache(
    runner, tmp_path, monkeypatch
):
    captured = {}

    class FakeNotebook:
        def __init__(self):
            self.metadata = {}
            self.cells = []

    class FakeClient:
        def __init__(self, notebook, **kwargs):
            pass

        def execute(self, **kwargs):
            captured.update(kwargs["env"])

    def module(name, **members):
        made = types.ModuleType(name)
        for key, value in members.items():
            setattr(made, key, value)
        monkeypatch.setitem(sys.modules, name, made)
        return made

    module("nbformat", read=lambda *a, **k: FakeNotebook(), write=lambda *a, **k: None)
    module("nbclient", NotebookClient=FakeClient)
    module("jupyter_client", KernelManager=lambda **kwargs: None)
    module("jupyter_client.kernelspec", KernelSpecManager=lambda **kwargs: None)

    cache = tmp_path / "warm"
    runner.execute_notebook(
        tmp_path / "example.ipynb", tmp_path / "out.ipynb", tmp_path / "kernels/python3", cache
    )
    assert captured["USDATA_CACHE_DIR"] == str(cache)
    assert captured["PATH"] == os.environ["PATH"]


def test_cache_resolution_prefers_the_option_then_the_environment(runner, tmp_path):
    resolve = runner.resolve_cache_dir
    variable = runner.CACHE_ENVIRONMENT_VARIABLE

    assert resolve(None, {}) is None
    assert resolve("", {variable: ""}) is None
    assert resolve("   ", {}) is None
    warm = tmp_path / "warm"
    assert resolve(str(warm), {}) == warm.resolve()
    assert resolve(None, {variable: str(warm)}) == warm.resolve()
    other = tmp_path / "other"
    assert resolve(str(warm), {variable: str(other)}) == warm.resolve()
    # Nothing is created merely by resolving.
    assert not warm.exists()


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
    (live / "test_mrms_live.py").touch()
    example = tmp_path / "examples/studies/new/new.ipynb"
    example.parent.mkdir(parents=True)
    example.touch()
    checkpoint = example.parent / ".ipynb_checkpoints/new.ipynb"
    checkpoint.parent.mkdir()
    checkpoint.touch()
    data = ci_inventory.inventory(tmp_path)
    assert data["live"] == [
        {"id": "test_mrms_live", "path": "tests/live/test_mrms_live.py", "extra": "grib"},
        {"id": "test_new_live", "path": "tests/live/test_new_live.py", "extra": "core"},
    ]
    assert data["notebooks"] == [{"id": "example-0", "path": "examples/studies/new/new.ipynb"}]
    assert data["restores"] == []
    (tmp_path / "examples/catalog.json").write_text(
        json.dumps(
            {
                "studies": [{"slug": "new", "title": "Q?", "summary": "A."}],
                "pinned": ["studies/new"],
            }
        )
    )
    assert ci_inventory.inventory(tmp_path)["restores"] == [
        {"id": "new", "path": "examples/studies/new/dataset.yaml"}
    ]


def test_inventory_focus_rejects_unknown_and_ambiguous_targets(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = importlib.import_module("ci_inventory")
    select_inventory = module.select_inventory
    data = module.inventory()
    focused = select_inventory(data, "live", "coops")
    assert [entry["id"] for entry in focused["live"]] == ["test_coops_live"]
    assert focused["notebooks"] == []
    assert select_inventory(data, "all") == data
    assert select_inventory(data, "minimum") == {"live": [], "notebooks": [], "restores": []}
    notebook = select_inventory(data, "notebooks", "noaa-coastwatch-sst")
    assert len(notebook["notebooks"]) == 1 and not notebook["live"] and not notebook["restores"]
    restore = select_inventory(data, "restores", "noaa-goes-glm")
    assert restore["restores"] == [
        {"id": "noaa-goes-glm", "path": "examples/datasets/noaa-goes-glm/dataset.yaml"}
    ]
    assert not restore["live"] and not restore["notebooks"]
    for scope, target in [("all", "coops"), ("minimum", "coops"), ("live", "$(echo x)")]:
        with pytest.raises(ValueError):
            select_inventory(data, scope, target)
    duplicates = {"live": data["live"] * 2, "notebooks": data["notebooks"]}
    with pytest.raises(ValueError, match="exactly one"):
        select_inventory(duplicates, "live", "coops")


def test_notebook_selection_accepts_slugs_and_paths_and_names_what_was_typed(runner, tmp_path):
    paths = [
        tmp_path / "examples/datasets/noaa-goes-glm/noaa-goes-glm.ipynb",
        tmp_path / "examples/studies/storm-surge/storm-surge.ipynb",
    ]
    for path in paths:
        path.parent.mkdir(parents=True)
        path.touch()
    resolve = runner.resolve_notebooks

    assert resolve(["noaa-goes-glm"], paths, root=tmp_path) == [paths[0]]
    assert resolve(["examples/studies/storm-surge/storm-surge.ipynb"], paths, root=tmp_path) == [
        paths[1]
    ]
    # Repeats collapse and results keep inventory order, not the order typed.
    assert resolve(["storm-surge", "noaa-goes-glm", "storm-surge"], paths, root=tmp_path) == paths

    with pytest.raises(ValueError) as raised:
        resolve(["goes_glm"], paths, root=tmp_path)
    message = str(raised.value)
    assert "goes_glm" in message
    assert "folder" in message and "examples/datasets/noaa-goes-glm/noaa-goes-glm.ipynb" in message


def test_runner_carries_a_committed_lockfile_only_for_pinned_examples(runner, tmp_path):
    seen: dict[str, list[str]] = {}
    for slug in ("pinned", "loose"):
        example = tmp_path / "examples" / slug
        example.mkdir(parents=True)
        (example / "example.ipynb").write_text(json.dumps(notebook("original")))
        (example / "dataset.yaml").write_text(f"name: {slug}\nsources: []\n")
        (example / "dataset.lock.json").write_text("{}")

    def execute(source, output, kernel_dir, cache_dir):
        seen[source.parent.name] = sorted(p.name for p in source.parent.iterdir() if p.is_file())
        output.write_text(json.dumps(notebook("executed")))

    paths = [tmp_path / "examples/pinned/example.ipynb", tmp_path / "examples/loose/example.ipynb"]
    pinned = [tmp_path / "examples/pinned/dataset.yaml"]
    assert not runner.run_notebooks(paths, tmp_path / "reports", pinned=pinned, execute=execute)
    assert seen["example-0"] == ["dataset.lock.json", "dataset.yaml", "example.ipynb"]
    assert seen["example-1"] == ["dataset.yaml", "example.ipynb"]
