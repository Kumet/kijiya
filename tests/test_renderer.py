from app.models import GeneratedArticle, Section, SourceArticle
from app.services.renderer import render

SOURCE = SourceArticle(
    url="https://example.com/original",
    title="元記事タイトル",
    author="著者",
    published_at="2026-01-01",
    site_name="サイト",
    text="元記事の本文",
    truncated=False,
)


def test_render_escapes_script_tags_in_paragraphs():
    article = GeneratedArticle(
        title="タイトル",
        lede="リード",
        sections=[Section(heading="見出し", paragraphs=["<script>alert(1)</script>"])],
    )

    html = render(article, SOURCE)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_render_converts_bold_markdown_to_strong_tag():
    article = GeneratedArticle(
        title="タイトル",
        lede="リード",
        sections=[Section(heading="見出し", paragraphs=["これは**強調**です"])],
    )

    html = render(article, SOURCE)

    assert "<strong>強調</strong>" in html


def test_render_includes_source_link_and_disclaimer():
    article = GeneratedArticle(
        title="タイトル",
        lede="リード",
        sections=[Section(heading="見出し", paragraphs=["本文"])],
    )

    html = render(article, SOURCE)

    assert 'href="https://example.com/original"' in html
    assert "この記事はAIが元記事をもとに再構成したものです。" in html
