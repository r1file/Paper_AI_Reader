from __future__ import annotations

import re
from io import BytesIO
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader


REQUEST_TIMEOUT = 45
USER_AGENT = "PaperAIReader/1.0 (+https://notion.so)"


class FetchError(RuntimeError):
    pass


def fetch_paper_text(url: str, text_limit: int) -> str:
    if is_pdf_url(url):
        text = fetch_pdf_text(url)
    else:
        text = fetch_webpage_text(url)

    text = clean_text(text)
    if not text:
        raise FetchError("No readable text could be extracted.")
    return text[:text_limit]


def is_pdf_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    return path.endswith(".pdf") or "/pdf/" in path or "arxiv.org/pdf" in url.lower()


def fetch_pdf_text(url: str) -> str:
    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"PDF download failed: {exc}") from exc

    content_type = response.headers.get("Content-Type", "").lower()
    if "pdf" not in content_type and not url.lower().split("?")[0].endswith(".pdf"):
        raise FetchError(f"URL did not return a PDF. Content-Type: {content_type or 'unknown'}")

    try:
        reader = PdfReader(BytesIO(response.content))
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
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"Webpage fetch failed: {exc}") from exc

    content_type = response.headers.get("Content-Type", "").lower()
    if "pdf" in content_type:
        try:
            reader = PdfReader(BytesIO(response.content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise FetchError(f"PDF text extraction failed: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
        element.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup
    return main.get_text(separator="\n")


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
