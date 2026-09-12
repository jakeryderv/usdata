# 0016: Site source boundaries

Status: Superseded for docs layout and redirects by [ADR 0017](0017-direct-mkdocs-and-static-hosting.md).

## Context

Separate deployments still shared the homepage npm toolchain. Documentation
assembly scanned broad repository directories and copied root onboarding and
policy files, obscuring where to edit and how to build each site.

## Decision

Keep the current domains and separate Workers from ADR 0015. `web/` owns the
homepage content, build, tests, and deployment. `docs/` owns its content under
`content/`, MkDocs configuration, assembly script, theme, hosting code, tests,
and independent npm package and lockfile. The root justfile delegates to these
owners. The Python docs dependency group remains in the repository uv lockfile.

Docs read selected external files through `docs/inputs.yml`, an explicit list
without globs. The changelog and runnable examples retain their original owners.
Root README is concise; detailed setup lives in `docs/content/project.md`.
Contribution, security, license, and fragment instructions remain canonical on
GitHub and are linked rather than copied. Their former site paths redirect there.

Generated catalog, API/CLI references, and upcoming changes remain derived from
SDK sources and release fragments. This is a one-way dependency: SDK and examples
do not import website build code. Catalog Markdown remains committed for GitHub
readers, generated only under `docs/content/generated/catalog/`.

Preserve existing public documentation and example URLs through build mapping;
repository paths and public paths need not match. Continue using ignored
`.build/docs/`, `.build/docs-site/`, and `web/dist/` output directories.

## Consequences

Each site can be built, checked, and deployed from its own directory. Two small
npm lockfiles trade duplicate tooling declarations for independent ownership.
Publishing another external example requires adding it to `docs/inputs.yml`.
Reference and notebook generation still require assembly, but its inputs and
owner are explicit. This updates the layout portion of ADR 0015 without changing
hosting, dataset storage, package release policy, or remote-cache scope.
