# Testing

`just check` is the complete offline pre-PR gate. It includes formatting,
linting, types, tests, generated documentation, and saved notebook validation.
Keep real network access out of this gate. Scientific decoder fixtures and
filesystem workflows belong here when they are deterministic and fast.

## Levels and responsibilities

Levels describe dependencies, not quality or importance. Run a regression at
the lowest level that reproduces the behavior; preserve real decoder tests
when mocks would miss format or alignment errors.

| Level | Scope here | Default home | Policy |
|---|---|---|---|
| L0 | Pure in-memory logic | `tests/unit/` | Every PR |
| L1 | Components with mocked transport | `tests/adapters/`, `tests/protocols/` | Every PR |
| L2 | Local files, SDK/CLI workflows, real scientific decoding | `tests/component/` | Every PR |
| L3 | Controlled service deployment | None: this SDK has no test deployment | Reserved |
| L4 | Production/upstream compatibility | `tests/live/` | Scheduled/manual |

L4 is a local adaptation for an SDK using public upstream services. A live NOAA
probe is not a controlled staging deployment. Installed-wheel smoke tests use
local fixtures (L2); resolving dependencies during environment setup is separate
from the offline behavior being tested. Saved notebook validation is offline;
executing the examples against public providers is live.

Collection assigns a level from the directory unless an explicit `l0`, `l1`,
`l2`, `l3`, or `l4` marker overrides it. Declare exactly one level. Mark tests
that use local files `@pytest.mark.l2` even inside adapter/transport modules;
a module using file fixtures throughout may declare `pytestmark = pytest.mark.l2`.
`component` modules conservatively use L2 for their combined local workflows.

Use `pandas`, `radar`, and `netcdf` markers for reader test groups. These select
coverage; they do not install dependencies. Tests still check optional imports,
and core-only CI must remain valid. Contract tests describe a purpose, not a
separate execution level.

## Selecting tests

- `just test`: all offline tests; live cases are skipped.
- `just test -m l0`: pure tests.
- `just test -m 'l1 or l2'`: offline component and local functional tests.
- `just test tests/adapters/test_goes.py`: one adapter's offline scenarios.
- `just test -m radar`: reader tests, with the radar extra installed.
- `just test-live`: explicitly enable and select upstream tests.
- `just test-live tests/live/test_goes_live.py`: one upstream dataset.

`just test-integration`, `--run-integration`, and the `integration` marker remain
compatibility aliases for live execution. A `live` marker is required to permit
network connections, and the CLI opt-in is required to run those cases. All
other tests are guarded against real socket connections and DNS resolution.
This guard applies to the pytest process, not arbitrary subprocesses.

## Adding and maintaining coverage

Keep source-specific query rules, pagination semantics, and response fixtures
with the adapter. Shared protocol behavior belongs under `tests/protocols/`.
Cache integrity, manifest restoration, and CLI error behavior belong with the
responsible component rather than a cross-cutting regression catch-all.

Prefer small fixtures, injected transports, meaningful failure assertions, and
parameter tables for equivalent cases. Test count is not a target. Measure
runtime and investigate failures; high line coverage does not establish correct
pagination, resource ownership, or scientific semantics. Keep `just check`
useful as providers grow instead of duplicating the entire core suite per adapter.

## CI reports and live isolation

CI runs repository-wide static/document checks once, then types and all offline
behavior tests in each supported Python/dependency profile. Core-only and each
optional extra remain separate environments. Built-wheel checks on Linux,
macOS, and Windows remain required; publishing still promotes the artifact
from successful CI for the exact commit.

`just check-static` and `just check-tests` expose those same parts locally.
`just check-tests --junitxml=reports/junit.xml --cov-report=json:reports/coverage.json`
retains machine-readable results. Coverage includes branches; it is diagnostic,
not a target for adding superficial tests. CI retains JUnit, coverage, and timing
reports for 14 days under uniquely named artifacts for each profile.

The scheduled/manual Integration workflow discovers jobs from live test modules
and example notebooks. Each dataset and example runs independently with fail-fast
disabled and a job timeout. GOES live decoding explicitly uses the NetCDF extra;
a core-only run reports that decoder test as skipped rather than silently omitting
its assertions. The workflow also tests minimum direct runtime dependencies on
Python 3.11 in a fresh environment, retaining the resolved versions. This probes
core lower bounds with current compatible transitive dependencies; it does not
claim minimum-version coverage for optional scientific stacks.

`just run-notebooks --notebook examples/goes-imagery/example.ipynb` selects one
example (repeat the flag for more). Executions retain partial notebooks, error
traces, timings, and `summary.json` in ignored `reports/notebooks/`; use
`--output-dir` to choose another report directory. A failed example does not
prevent later selected examples from running. `--write` refreshes the selected
committed notebooks only if every selected example succeeds.

Documentation is checked once in the static job: `just check-docs` checks generated
catalogs and saved notebooks, then builds the site with strict internal link and
anchor validation. See [maintaining documentation](guides/documentation.md).

## Focused hosted checks

Weekly Integration runs retain the full live, notebook, and minimum-dependency
suites. Manual runs can select a scope and one target; an empty target runs the
whole selected scope. Examples from a checkout with the GitHub CLI:

```sh
gh workflow run integration.yml -f scope=live -f target=coops
gh workflow run integration.yml -f scope=notebooks -f target=sst-analysis
gh workflow run integration.yml -f scope=minimum
gh workflow run integration.yml -f scope=all
```

A live target is the test module stem without `test_` and `_live`; a notebook
target is its example folder name. Full repository-relative paths also work.
Unknown or ambiguous targets fail before starting jobs. The `all` and `minimum`
scopes reject a target. Use `--ref BRANCH` to test a workflow change before merging.
Each test job writes counts, failures, skips, and execution time to the Actions
run summary; notebook jobs report status and duration. Reports missing after a
setup failure are identified explicitly, and full diagnostics remain in artifacts.
