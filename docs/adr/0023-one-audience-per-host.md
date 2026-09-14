# 0023: One audience per host

Status: accepted. Date: 2026-09-14. Updates the root README and setup-page
portion of [ADR 0016](0016-site-source-boundaries.md).

## Context

The documentation site carried two audiences in one navigation. Start here,
Guides, Datasets, and Reference served people using the package. Development
and Project served people changing it: architecture, testing, adding a dataset,
maintaining documentation, website operations, decision records, reviews,
versioning, and the roadmap. Because the contributor story was half on the site
and half on GitHub, user pages accumulated a dozen links out to the README,
changelog, contributing guide, and fragment rules, and the README and the
docs project page duplicated the same onboarding text for both audiences.
Visitors could not tell which host was for them.

## Decision

Each host has one audience and no content is duplicated between hosts.

- `usdata.dev` is for someone deciding whether to use the package: the pitch,
  the dataset browser, and the worked examples.
- `docs.usdata.dev` is for someone using the package: install, first dataset,
  task guides, dataset notes, and reference. Its navigation contains nothing
  about how the repository works.
- GitHub is for someone changing the project: the README is the single
  onboarding page, with contributing, architecture, testing, adding a dataset,
  decision records, reviews, roadmap, versioning, changelog, and site
  operations beside it.

Contributor and project-record pages remain under `docs/` so GitHub renders
them with working relative links between each other, but `mkdocs.yml` excludes
them from the built site. The docs project page is folded into the README, and
a new Install page holds installation, extras, platform notes, and the source
checkout, which is the one setup topic users need. A user page links to GitHub
only for a design decision that explains observed behaviour.

## Consequences

The user site has four tabs and every page in it is for a user. The README is
longer and is the only place contributor commands are listed. Links from
example pages and the dataset browser to the former docs project page move to
the Install page. Release notes stay on GitHub and PyPI; the site keeps the
generated upcoming-changes page because it tells a source-checkout user what is
not yet published, which is a usage question. This retires ADR 0016's statement
that detailed setup lives in the docs project page.
