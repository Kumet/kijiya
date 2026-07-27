from pathlib import Path

import pytest

from app.errors import ExtractionError
from app.services.extractor import extract

FIXTURES = Path(__file__).parent / "fixtures"


def test_extracts_text_and_title_from_article_html():
    html = (FIXTURES / "article.html").read_text(encoding="utf-8")

    source = extract(html, "https://example.com/article")

    assert source.title == "猫と暮らす、小さな部屋の工夫"
    assert "キャットタワー" in source.text
    assert len(source.text) >= 200
    assert source.truncated is False


def test_raises_extraction_error_for_short_html():
    html = (FIXTURES / "short.html").read_text(encoding="utf-8")

    with pytest.raises(ExtractionError):
        extract(html, "https://example.com/short")


def test_truncates_text_exceeding_max_source_chars(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_source_chars", 50)
    html = (FIXTURES / "article.html").read_text(encoding="utf-8")

    source = extract(html, "https://example.com/article")

    assert source.truncated is True
    assert len(source.text) == 50
