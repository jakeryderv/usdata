# Examples

Two kinds of notebook live here ([ADR 0041](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0041-dataset-walkthroughs-and-studies.md)):

- **Walkthroughs**, in `datasets/<provider>-<name>/`: one per dataset, teaching
  how to select it, what arrives, how to open it, and what was awkward. Each is
  shown on its dataset's page at [usdata.dev/datasets](https://usdata.dev/datasets/).
- **Studies**, in `studies/<slug>/`: a question answered end to end, usually by
  joining datasets, listed at [usdata.dev/studies](https://usdata.dev/studies/).
  Start with the [severe-weather case study](https://usdata.dev/studies/severe-weather-case-study/):
  one tornado, six datasets, one manifest, one lockfile, and a citation block.

Each folder holds a notebook named after the folder, its `dataset.yaml`, and,
when pinned, its committed `dataset.lock.json`. `catalog.json` lists the studies
in display order and the pinned folders. The website renders saved outputs; it
never runs a notebook.

## Run a notebook yourself

Download a notebook and its `dataset.yaml` from its page into one folder, then
install usdata with the extras the notebook imports, plus Jupyter and
matplotlib, in a Python 3.11+ environment:

```sh
python -m pip install "usdata[pandas]" jupyterlab matplotlib
jupyter lab
```

Radar walkthroughs need `usdata[radar]`, satellite and IBTrACS ones
`usdata[netcdf]`, and model-output ones `usdata[grib]`; the dataset page names
the extra. The first run downloads from the agency; later runs use the local
cache. A notebook that needs a key says which environment variables to set.
With a committed lockfile beside the manifest, `usdata pull` restores exactly
the pinned files instead of asking the agency again.

## Work on the examples

From the repository root, with [uv and just installed](https://github.com/jakeryderv/usdata#development):

```sh
just notebooks              # JupyterLab with every extra and the examples tools
just check-notebooks        # offline checks of committed outputs and lockfiles
just run-notebooks          # live execution, without changing committed outputs
just run-notebooks --write  # live execution, then save the results if all pass
```

`--notebook` names one notebook by folder (`noaa-goes-glm`) or by
repository-relative path, and repeats. Each run starts a fresh kernel with a
fresh cache in a temporary directory; `--cache DIR` (or
`USDATA_NOTEBOOK_CACHE`) reuses one across runs. A failure leaves the committed
notebooks untouched, and `just check` validates the saved outputs offline.

Saved outputs are snapshots, not promises about future upstream responses. Each
notebook records its execution time, package versions, source URLs, and input
checksums. Commit compact outputs: short tables, small static plots, and the
relevant provenance, and review the diff of a refresh, since upstream revisions
change both values and checksums.

## Pinned examples

The folders listed under `pinned` in `catalog.json` commit their lockfile
([ADR 0029](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0029-committed-example-lockfiles.md)).
Most read object archives on public buckets, written once and republished
rarely, so a pin can be expected to hold. `studies/wildfire-smoke` reads AQS
summaries, which agencies keep revising, so it is the pin most likely to drift;
the weekly job restores it with a key from repository secrets, and anyone
without a key restores it from the mirror. The notebook runner carries a
committed lockfile beside its manifest, so those notebooks restore the pinned
inputs instead of resolving their query again.

```sh
just restore-examples                          # every pinned example, each into a fresh cache
just restore-examples --manifest noaa-goes-glm
USDATA_MIRROR_URL=https://data.usdata.dev just restore-examples   # as the weekly job runs it
```

The project mirror at `https://data.usdata.dev` holds the exact bytes these
lockfiles pin
([ADR 0030](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0030-content-addressed-mirror.md)).
Re-pin deliberately, never from the runner: after editing a pinned manifest run
`usdata pull examples/<kind>/<folder>/dataset.yaml --force`, or `--update <id>`
to accept one archive's new bytes, and review the lockfile diff. Every other
folder's lockfile stays ignored.

## Writing a walkthrough or a study

A walkthrough follows one template, as markdown headings in this order: the
dataset's title and what it is, `Select`, `What arrives`, `Open`,
`A first look`, `Pin and cite`, and `What was awkward`. A study's title is the
question a student or analyst would ask, written down before touching the tool;
it opens with `Data`, organizes its analysis freely, and ends with
`Pin and cite` and `What was awkward`.

"What was awkward" lists the places where you had to work around the tool or
the data. Each entry is an issue candidate, and together they are how usage
friction reaches the project
([ADR 0025](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0025-examples-as-usage-review.md)).

The first code cell sets the shared figure style inline, so a downloaded
notebook needs nothing else from the repository. Tag exactly one code cell
`preview`; its single figure becomes the card and hero image on the website.
