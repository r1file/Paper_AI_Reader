from __future__ import annotations

import re
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader


REQUEST_TIMEOUT = 45
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36 PaperAIReader/1.0"
    ),
    "Accept": "text/html,application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class FetchError(RuntimeError):
    pass


def fetch_paper_text(url: str, text_limit: int) -> str:
    fetch_errors = []
    if is_pdf_url(url):
        try:
            text = fetch_pdf_text(url)
        except FetchError as exc:
            fetch_errors.append(str(exc))
            try:
                text = fetch_webpage_text(url)
            except FetchError as webpage_exc:
                fetch_errors.append(str(webpage_exc))
                text = ""
    else:
        try:
            text = fetch_webpage_text(url)
        except FetchError as exc:
            fetch_errors.append(str(exc))
            text = ""

    text = clean_text(text)
    if not text and is_ieee_url(url):
        text = clean_text(fetch_ieee_metadata_text(url))

    if not text:
        detail = f" Details: {'; '.join(fetch_errors)}" if fetch_errors else ""
        raise FetchError(f"No readable text could be extracted.{detail}")
    return text[:text_limit]


def is_pdf_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    return (
        path.endswith(".pdf")
        or "/pdf/" in path
        or "arxiv.org/pdf" in url.lower()
        or is_ieee_stamp_url(url)
    )


def is_ieee_url(url: str) -> bool:
    return "ieeexplore.ieee.org" in urlparse(url).netloc.lower()


def is_ieee_stamp_url(url: str) -> bool:
    parsed = urlparse(url)
    return is_ieee_url(url) and "/stamp/" in parsed.path.lower()


def fetch_pdf_text(url: str) -> str:
    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers=REQUEST_HEADERS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"PDF download failed: {exc}") from exc

    content_type = response.headers.get("Content-Type", "").lower()
    if "pdf" not in content_type and not response.content.lstrip().startswith(b"%PDF"):
        raise FetchError(f"URL did not return a PDF. Content-Type: {content_type or 'unknown'}")

    return extract_pdf_text(response.content)


def extract_pdf_text(pdf_content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(pdf_content))
        page_text = []
        for page in reader.pages:
            page_text.append(page.extract_text() or "")
        return "\n".join(page_text)
    except Exception as exc:
        raise FetchError(f"PDF text extraction failed: {exc}") from exc


def fetch_webpage_text(url: str) -> str:
    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers=REQUEST_HEADERS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"Webpage fetch failed: {exc}") from exc

    content_type = response.headers.get("Content-Type", "").lower()
    if "pdf" in content_type:
        return extract_pdf_text(response.content)

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
        element.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup
    return main.get_text(separator="\n")


def fetch_ieee_metadata_text(url: str) -> str:
    arnumber = ieee_article_number(url)
    candidate_urls = [url]
    if arnumber:
        candidate_urls.append(f"https://ieeexplore.ieee.org/document/{arnumber}")

    for candidate_url in dict.fromkeys(candidate_urls):
        try:
            response = requests.get(
                candidate_url,
                timeout=REQUEST_TIMEOUT,
                headers=REQUEST_HEADERS,
            )
            response.raise_for_status()
        except requests.RequestException:
            continue

        if "pdf" in response.headers.get("Content-Type", "").lower() or response.content.lstrip().startswith(b"%PDF"):
            text = clean_text(extract_pdf_text(response.content))
            if text:
                return text

        soup = BeautifulSoup(response.text, "html.parser")
        text = clean_text("\n".join(extract_ieee_metadata_parts(soup, response.text)))
        if text:
            return text

    raise FetchError(
        "IEEE page did not expose readable PDF text or public metadata. "
        "If this paper is behind IEEE access control, use an accessible PDF URL or manually downloaded PDF."
    )


def ieee_article_number(url: str) -> str | None:
    parsed = urlparse(url)
    query_number = parse_qs(parsed.query).get("arnumber", [None])[0]
    if query_number:
        return query_number
    match = re.search(r"/document/(\d+)", parsed.path)
    if match:
        return match.group(1)
    match = re.search(r"arnumber=(\d+)", url)
    return match.group(1) if match else None


def extract_ieee_metadata_parts(soup: BeautifulSoup, html: str) -> list[str]:
    parts = []
    meta_fields = [
        ("Title", ["citation_title", "dc.Title", "og:title", "twitter:title"]),
        ("Abstract", ["description", "dc.Description", "og:description", "twitter:description"]),
        ("Publication", ["citation_publication_date", "citation_conference_title", "citation_journal_title"]),
        ("DOI", ["citation_doi", "dc.Identifier"]),
        ("Keywords", ["citation_keywords"]),
    ]
    seen_values = set()
    for label, names in meta_fields:
        values = []
        for name in names:
            for tag in soup.find_all("meta"):
                if tag.get("name") == name or tag.get("property") == name:
                    value = clean_text(tag.get("content", ""))
                    if value and value not in seen_values:
                        values.append(value)
                        seen_values.add(value)
        if values:
            parts.append(f"{label}: {'; '.join(values)}")

    title = soup.find(["h1", "h2"])
    if title:
        value = clean_text(title.get_text(separator=" "))
        if value and value not in seen_values:
            parts.insert(0, f"Title: {value}")
            seen_values.add(value)

    for selector in ("div.abstract-text", "section.abstract", "div.u-mb-1", "xpl-document-abstract"):
        element = soup.select_one(selector)
        if element:
            value = clean_text(element.get_text(separator=" "))
            if value and value not in seen_values:
                parts.append(f"Abstract: {value}")
                seen_values.add(value)

    embedded_patterns = [
        r'"title"\s*:\s*"([^"]{10,})"',
        r'"abstract"\s*:\s*"([^"]{20,})"',
        r'"doi"\s*:\s*"([^"]+)"',
    ]
    for pattern in embedded_patterns:
        for value in re.findall(pattern, html):
            value = clean_text(value.encode("utf-8").decode("unicode_escape", errors="ignore"))
            if value and value not in seen_values:
                parts.append(value)
                seen_values.add(value)

    return parts


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
