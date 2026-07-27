import json
import re

import trafilatura
from bs4 import BeautifulSoup
from readability import Document

from app.config import settings
from app.errors import ExtractionError
from app.models import SourceArticle

MIN_TEXT_LENGTH = 200
_MULTI_BLANK_RE = re.compile(r"\n{3,}")


def extract(html: str, url: str) -> SourceArticle:
    text, meta = _extract_with_trafilatura(html, url)

    if len(text) < MIN_TEXT_LENGTH:
        text = _extract_with_readability(html)

    if len(text) < MIN_TEXT_LENGTH:
        raise ExtractionError("本文を取り出せませんでした")

    text = _normalize(text)

    truncated = False
    if len(text) > settings.max_source_chars:
        text = text[: settings.max_source_chars]
        truncated = True

    return SourceArticle(
        url=url,
        title=meta.get("title") or None,
        author=meta.get("author") or None,
        published_at=meta.get("date") or None,
        site_name=meta.get("sitename") or None,
        text=text,
        truncated=truncated,
    )


def _extract_with_trafilatura(html: str, url: str) -> tuple[str, dict]:
    result = trafilatura.extract(
        html,
        url=url,
        output_format="json",
        include_comments=False,
        favor_precision=True,
        with_metadata=True,
    )
    if not result:
        return "", {}

    data = json.loads(result)
    return data.get("text") or "", data


def _extract_with_readability(html: str) -> str:
    try:
        summary_html = Document(html).summary()
    except Exception:
        return ""

    soup = BeautifulSoup(summary_html, "lxml")
    return soup.get_text("\n")


def _normalize(text: str) -> str:
    return _MULTI_BLANK_RE.sub("\n\n", text).strip()
