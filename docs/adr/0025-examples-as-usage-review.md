# 0025: Worked examples are the usage review

Status: accepted. Date: 2026-09-15. Retires the per-release first-use review
that [versioning](../versioning.md) asked for after each publication, and whose
results are kept in [docs/reviews/](../reviews/).

## Context

Every minor release since v0.10.0 ended with a manual first-use review: install
the published package into a fresh environment, follow the getting-started
walkthrough, exercise whatever the release added, and write the result up in
`docs/reviews/first-use-vX.Y.Z.md`. The Observation sections are the part that
paid: they produced real fixes, including pathlib and published-installation
corrections to the manifest examples, fresh-cache restoration in the
walkthrough, and the note that a date-only `--end` means midnight at the start
of that day, which is surprising for the model datasets.

The rest of the practice did less than it looked like it did. The author was
reviewing the author's own tool, so the questions asked were the ones the tool
already answers well. It happened once per release, on a schedule chosen by the
release rather than by anyone's actual work, and each review started from
nothing: the previous review's surprises were recorded as prose and not carried
into anything executable. Its install check is also no longer the only one.
CI builds the distributions once and smoke-tests the installed wheel outside
the checkout on Linux, macOS, and Windows, across core, pandas, radar, and
NetCDF profiles, before publishing promotes those same files.

## Decision

Retire the per-release first-use review document. Its two jobs move.

Proving the published package installs and the guide works is automated.
After the publish workflow tags a release, a job installs that exact version
from PyPI with the extra the guide names and runs the guide's own commands
against it: search, info, the station fetch, the Python reading example, the
manifest pull and verify, and restoration into a second cache. The commands are
extracted from `docs/getting-started.md` rather than copied, so the guide and
the check cannot disagree. The job fails visibly and changes nothing: the tag,
the release, and the uploaded files stay as they are.

Surfacing friction moves into the worked examples. An example is written
question-first: the README title is the question a student or analyst would
ask, written before touching the tool, and the notebook answers it. Each
example README carries a short section titled "What was awkward" listing the
places the author had to work around the tool or the data. Each entry is an
issue candidate. Each release should have exercised its new behavior in at
least one example, since the live example run then guards it.

## Consequences

Release preparation ends at publication and the automated walkthrough. Nothing
about a release waits on a person writing a review document, and a broken
published package is reported by a failing job rather than by whoever gets to
the review first.

Friction is now recorded next to the work that hit it, by someone answering a
question rather than inspecting a tool, and it accumulates across examples
instead of resetting every release. The cost is that friction surfaces only
where an example goes; a release whose new behavior no example uses has no
usage record, which is why the rule is that each release exercises its new
behavior in one.

The existing review files stay where they are as historical records. They keep
their original evidence and are cited as dated snapshots, not as a current
check.
