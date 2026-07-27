import socket
from unittest.mock import AsyncMock, patch

import httpx
import respx

from app.models import GeneratedArticle, Section
from app.services.store import store


async def test_index_returns_200(client):
    response = await client.get("/")
    assert response.status_code == 200


async def test_healthz_returns_ok(client):
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_generate_returns_success_fragment(client):
    fake_article = GeneratedArticle(
        title="生成タイトル",
        lede="リード文",
        sections=[Section(heading="見出し", paragraphs=["段落"])],
        tags=["タグ"],
    )

    with patch(
        "socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    ):
        with respx.mock:
            respx.get("https://example.com/article").mock(
                return_value=httpx.Response(
                    200,
                    headers={"content-type": "text/html"},
                    text="<html><body><article><p>" + "本文" * 150 + "</p></article></body></html>",
                )
            )
            with patch(
                "app.routers.generate.generator.generate",
                AsyncMock(return_value=fake_article),
            ):
                response = await client.post(
                    "/api/generate",
                    data={
                        "url": "https://example.com/article",
                        "prompt": "要約して",
                        "tone": "neutral",
                        "length": "short",
                    },
                )

    assert response.status_code == 200
    assert "生成タイトル" in response.text
    assert "/preview/" in response.text
    assert "/download/" in response.text


async def test_generate_returns_error_fragment_for_unsafe_url(client):
    response = await client.post(
        "/api/generate",
        data={
            "url": "http://127.0.0.1/",
            "prompt": "要約して",
            "tone": "neutral",
            "length": "short",
        },
    )

    assert response.status_code == 200
    assert "このURLは取得できません" in response.text


async def test_preview_returns_404_for_unknown_id(client):
    response = await client.get("/preview/does-not-exist")
    assert response.status_code == 404


async def test_download_returns_content_disposition_header(client):
    doc_id = await store.put("<html>ok</html>", "テスト記事.html")

    response = await client.get(f"/download/{doc_id}")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]


async def test_download_returns_404_for_unknown_id(client):
    response = await client.get("/download/does-not-exist")
    assert response.status_code == 404
