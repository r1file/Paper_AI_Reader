from bs4 import BeautifulSoup

from paper_ai_reader.fetcher import (
    clean_text,
    extract_ieee_metadata_parts,
    ieee_article_number,
    is_pdf_url,
)


def test_clean_text_collapses_spaces_and_blank_lines() -> None:
    assert clean_text(" A\t\tB \n\n\n\n C \x00 D ") == "A B \n\n C D"


def test_is_pdf_url_detects_common_pdf_forms() -> None:
    assert is_pdf_url("https://example.com/paper.pdf")
    assert is_pdf_url("https://arxiv.org/pdf/2401.00001")
    assert is_pdf_url("https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=123")
    assert not is_pdf_url("https://example.com/document")


def test_ieee_article_number_from_query_and_path() -> None:
    assert ieee_article_number("https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=12345") == "12345"
    assert ieee_article_number("https://ieeexplore.ieee.org/document/67890") == "67890"
    assert ieee_article_number("https://example.com") is None


def test_extract_ieee_metadata_parts_dedupes_meta_values() -> None:
    soup = BeautifulSoup(
        """
        <html>
          <head>
            <meta name="citation_title" content="Useful Paper">
            <meta property="og:description" content="Useful abstract">
            <meta name="citation_doi" content="10.1000/example">
          </head>
          <body><h1>Useful Paper</h1></body>
        </html>
        """,
        "html.parser",
    )

    parts = extract_ieee_metadata_parts(soup, "")

    assert "Title: Useful Paper" in parts
    assert "Abstract: Useful abstract" in parts
    assert "DOI: 10.1000/example" in parts
    assert parts.count("Title: Useful Paper") == 1
