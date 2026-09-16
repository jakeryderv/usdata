from datetime import UTC, datetime
from pathlib import Path

import pytest

from usdata.cache import sha256_file
from usdata.cite import (
    DATE_PLACEHOLDER,
    PLACEHOLDER_NOTE,
    Citation,
    cite_dataset,
    cite_lockfile,
    render_bibtex,
    render_text,
)
from usdata.manifest import LockedAsset, Lockfile, lockfile_path
from usdata.models import (
    Asset,
    Dataset,
    DomainInfo,
    Protocol,
    Provenance,
    ProviderInfo,
    Status,
    TimeRange,
)
from usdata.pull import ManifestChanged
from usdata.registry import Registry

MANIFEST = """name: synthetic
sources:
  - name: first
    dataset: test:widgets
"""
PLACEHOLDER_CITATION = "Widgets on AWS were accessed on [date] from https://example.test/widgets"


def make_dataset(**overrides) -> Dataset:
    fields = {
        "id": "test:widgets",
        "provider": "test",
        "title": "Test Widgets",
        "protocol": Protocol.HTTP,
        "homepage": "https://example.test/widgets",
        "license": "US Government Work (public domain)",
        "terms": "https://example.test/terms",
        "citation": "Test Agency, 2026: Widgets & gadgets, doi:10.0000/widgets_1",
        "summary": "Test widgets",
        "formats": ["CSV"],
        "domain": "test",
        "status": Status.AVAILABLE,
        "since": "0.1",
        "adapter": "test:Widgets",
    }
    return Dataset.model_validate(fields | overrides)


def make_registry(dataset: Dataset) -> Registry:
    return Registry(
        [dataset],
        [ProviderInfo(id="test", name="Test Agency", homepage="https://example.test/")],
        [DomainInfo(id="test", name="Test")],
    )


def locked(asset_id: str, retrieved: datetime, size: int, source: str) -> LockedAsset:
    href = f"https://example.test/{asset_id}.csv"
    checksum = f"sha256:{asset_id * 8}"
    return LockedAsset(
        asset=Asset(id=asset_id, dataset_id="test:widgets", href=href, protocol=Protocol.HTTP),
        provenance=Provenance(
            dataset_id="test:widgets",
            provider="test",
            source_url=href,
            retrieved_at=retrieved,
            checksum=checksum,
            size=size,
            license="US Government Work (public domain)",
            usdata_version="0.16.0",
        ),
        source=source,
    )


def pin(tmp_path: Path, *assets: LockedAsset) -> Path:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    Lockfile(
        manifest="synthetic",
        manifest_checksum=sha256_file(manifest),
        generated_at=datetime(2026, 5, 8, tzinfo=UTC),
        usdata_version="0.16.0",
        assets=list(assets),
    ).save(lockfile_path(manifest))
    return manifest


@pytest.fixture
def pinned(tmp_path: Path) -> Path:
    return pin(
        tmp_path,
        locked("a", datetime(2026, 5, 6, 12, tzinfo=UTC), 1200, "first"),
        locked("b", datetime(2026, 5, 7, 9, tzinfo=UTC), 34, "first"),
    )


def test_cite_dataset_uses_the_registry_citation() -> None:
    dataset = make_dataset()
    citation = cite_dataset(dataset, registry=make_registry(dataset))
    assert citation.dataset_id == "test:widgets" and citation.title == "Test Widgets"
    assert citation.text == dataset.citation
    assert citation.homepage == "https://example.test/widgets"
    assert citation.terms == "https://example.test/terms"
    assert citation.retrieved is None and citation.asset_count == 0 and citation.sources == []


def test_cite_dataset_falls_back_to_agency_title_and_provider_homepage() -> None:
    dataset = make_dataset(citation=None, homepage=None)
    citation = cite_dataset(dataset, registry=make_registry(dataset))
    assert citation.text == "Test Agency, Test Widgets, accessed via usdata"
    assert citation.homepage == "https://example.test/"


def test_cite_dataset_names_an_unknown_provider_by_its_id() -> None:
    dataset = make_dataset(citation=None)
    citation = cite_dataset(dataset, registry=Registry([]))
    assert citation.text == "TEST, Test Widgets, accessed via usdata"


def test_cite_lockfile_summarizes_what_each_dataset_pinned(pinned: Path) -> None:
    dataset = make_dataset()
    (citation,) = cite_lockfile(pinned, make_registry(dataset))
    assert citation.text == dataset.citation
    assert citation.retrieved is not None
    assert citation.retrieved.start == datetime(2026, 5, 6, 12, tzinfo=UTC)
    assert citation.retrieved.end == datetime(2026, 5, 7, 9, tzinfo=UTC)
    assert citation.asset_count == 2 and citation.total_bytes == 1234
    assert citation.usdata_version == "0.16.0" and citation.sources == ["first"]


def test_cite_lockfile_refuses_a_manifest_edited_after_the_lockfile(pinned: Path) -> None:
    pinned.write_text(MANIFEST + "    allow_empty: true\n")
    with pytest.raises(ManifestChanged):
        cite_lockfile(pinned, make_registry(make_dataset()))


def test_render_text_labels_the_fields_that_are_set(pinned: Path) -> None:
    dataset = make_dataset()
    rendered = render_text(cite_lockfile(pinned, make_registry(dataset)))
    assert rendered.splitlines() == [
        "test:widgets",
        f"  {dataset.citation}",
        "  homepage: https://example.test/widgets",
        "  license: US Government Work (public domain)",
        "  terms: https://example.test/terms",
        "  retrieved: 2026-05-06 through 2026-05-07; 2 checksummed assets "
        "(1,234 bytes) pinned by usdata 0.16.0",
        "  sources: first",
    ]


def test_render_text_of_a_registry_entry_has_no_retrieval_lines() -> None:
    dataset = make_dataset()
    rendered = render_text([cite_dataset(dataset, registry=make_registry(dataset))])
    assert "retrieved:" not in rendered and "sources:" not in rendered
    assert rendered.startswith("test:widgets\n  Test Agency, 2026:")


def test_render_text_separates_datasets_with_a_blank_line() -> None:
    dataset = make_dataset()
    other = make_dataset(id="test:gadgets", title="Test Gadgets", citation=None)
    registry = Registry(
        [dataset, other],
        [ProviderInfo(id="test", name="Test Agency")],
        [DomainInfo(id="test", name="Test")],
    )
    rendered = render_text([cite_dataset(d, registry=registry) for d in (dataset, other)])
    assert "\n\ntest:gadgets\n" in rendered


def test_render_bibtex_escapes_specials_and_keeps_urls_verbatim() -> None:
    dataset = make_dataset()
    entry = render_bibtex([cite_dataset(dataset, registry=make_registry(dataset))])
    assert entry.startswith("@misc{test-widgets,\n")
    assert (
        "howpublished = {Test Agency, 2026: Widgets \\& gadgets, doi:10.0000/widgets\\_1}," in entry
    )
    assert "url          = {https://example.test/widgets}," in entry
    assert entry.endswith("}") and "note" not in entry


def test_render_bibtex_notes_the_retrieval_dates_and_checksummed_assets(pinned: Path) -> None:
    entry = render_bibtex(cite_lockfile(pinned, make_registry(make_dataset())))
    assert (
        "note         = {Retrieved 2026-05-06 through 2026-05-07; "
        "2 checksummed assets (1,234 bytes) pinned by usdata 0.16.0}," in entry
    )


def test_render_bibtex_falls_back_to_the_terms_url_and_counts_one_asset() -> None:
    moment = datetime(2026, 5, 6, 3, tzinfo=UTC)
    citation = Citation(
        dataset_id="test:widgets",
        title="Test Widgets",
        text="Test Agency, Test Widgets, accessed via usdata",
        terms="https://example.test/terms",
        retrieved=TimeRange(start=moment, end=moment),
        asset_count=1,
        total_bytes=58,
    )
    entry = render_bibtex([citation])
    assert "url          = {https://example.test/terms}," in entry
    assert "note         = {Retrieved 2026-05-06; 1 checksummed asset (58 bytes) pinned}," in entry


def test_cite_lockfile_fills_the_date_placeholder_with_the_retrieval_range(pinned: Path) -> None:
    dataset = make_dataset(citation=PLACEHOLDER_CITATION)
    (citation,) = cite_lockfile(pinned, make_registry(dataset))
    assert citation.text == (
        "Widgets on AWS were accessed between 2026-05-06 and 2026-05-07 "
        "from https://example.test/widgets"
    )


def test_cite_lockfile_fills_the_placeholder_with_one_date_within_a_day(tmp_path: Path) -> None:
    manifest = pin(
        tmp_path,
        locked("a", datetime(2026, 5, 6, 1, tzinfo=UTC), 12, "first"),
        locked("b", datetime(2026, 5, 6, 23, tzinfo=UTC), 34, "first"),
    )
    dataset = make_dataset(citation=PLACEHOLDER_CITATION)
    (citation,) = cite_lockfile(manifest, make_registry(dataset))
    assert citation.text == PLACEHOLDER_CITATION.replace(DATE_PLACEHOLDER, "2026-05-06")


def test_render_bibtex_of_a_lockfile_citation_has_no_date_placeholder(pinned: Path) -> None:
    dataset = make_dataset(citation=PLACEHOLDER_CITATION)
    entry = render_bibtex(cite_lockfile(pinned, make_registry(dataset)))
    assert DATE_PLACEHOLDER not in entry
    assert "howpublished = {Widgets on AWS were accessed between 2026-05-06" in entry


def test_cite_dataset_keeps_the_placeholder_and_render_text_says_where_it_comes_from() -> None:
    dataset = make_dataset(citation=PLACEHOLDER_CITATION)
    citation = cite_dataset(dataset, registry=make_registry(dataset))
    assert citation.text == PLACEHOLDER_CITATION
    assert f"  note: {PLACEHOLDER_NOTE}" in render_text([citation]).splitlines()


def test_as_text_and_as_bibtex_render_the_single_citation(pinned: Path) -> None:
    (citation,) = cite_lockfile(pinned, make_registry(make_dataset()))
    assert citation.as_text() == render_text([citation])
    assert citation.as_bibtex() == render_bibtex([citation])


def test_renderers_say_so_when_a_retrieval_range_has_no_bounds() -> None:
    citation = Citation(
        dataset_id="test:widgets",
        title="Test Widgets",
        text="Test Agency, Test Widgets, accessed via usdata",
        retrieved=TimeRange(),
    )
    assert "retrieved: an unrecorded date;" in render_text([citation])
