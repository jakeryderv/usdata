import re

from usdata.protocols.listing import directory_entries

NAME = re.compile(r"data-(\d{4})\.csv\.gz")
TABLE = (
    "<table>"
    '<tr><td><img src="/icons/text.gif"></td><td><a href="data-2023.csv.gz">x</a></td>'
    '<td align="right">2026-03-05 16:03</td><td align="right">6.8M</td></tr>'
    '<tr><td><a href="data-2024.csv.gz">data-2024.csv.gz</a></td><td>2026-03-23 13:10</td>'
    '<td align="right">10508</td><td></td></tr>'
    '<tr><td><a href="/pub/other/">parent</a></td><td></td><td>7</td></tr>'
    '<tr><td><a href="https://evil.example/data-2025.csv.gz">x</a></td><td>8</td></tr>'
    "</table>"
)


def test_keeps_only_literal_matching_names_with_integer_sizes() -> None:
    expected = [("data-2023.csv.gz", None), ("data-2024.csv.gz", 10508)]
    assert directory_entries(TABLE, NAME) == expected


def test_anchors_outside_table_rows_have_no_size() -> None:
    page = '<pre><a href="data-2022.csv.gz">data-2022.csv.gz</a> 2026-01-01 12:00 4096</pre>'
    assert directory_entries(page, NAME) == [("data-2022.csv.gz", None)]


def test_size_is_not_taken_from_cells_before_the_name() -> None:
    page = '<table><tr><td>42</td><td><a href="data-2021.csv.gz">x</a></td><td>-</td></tr></table>'
    assert directory_entries(page, NAME) == [("data-2021.csv.gz", None)]
