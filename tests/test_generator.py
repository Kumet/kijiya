from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import openai
import pytest

from app.errors import GenerationError
from app.models import GenerateRequest, SourceArticle
from app.services import generator

SOURCE = SourceArticle(
    url="https://example.com/a",
    title="元タイトル",
    author="著者",
    published_at="2026-01-01",
    site_name="サイト",
    text="本文" * 100,
    truncated=False,
)
REQUEST = GenerateRequest(
    url="https://example.com/a", prompt="要約して", tone="neutral", length="short"
)

VALID_JSON_BODY = (
    '{"title": "新タイトル", "lede": "リード文",'
    ' "sections": [{"heading": "見出し", "paragraphs": ["本文段落"]}],'
    ' "tags": ["タグ1"], "takeaways": []}'
)


def _fake_response(text: str):
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def _client_with_responses(texts: list[str]):
    client = SimpleNamespace()
    mock_create = AsyncMock(side_effect=[_fake_response(t) for t in texts])
    client.chat = SimpleNamespace(completions=SimpleNamespace(create=mock_create))
    return client, mock_create


def _client_raising(exc: Exception):
    client = SimpleNamespace()
    client.chat = SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(side_effect=exc)))
    return client


async def test_generate_parses_valid_json_response():
    client, mock_create = _client_with_responses([VALID_JSON_BODY])
    with patch("app.services.generator.openai.AsyncOpenAI", return_value=client):
        article = await generator.generate(SOURCE, REQUEST)

    assert article.title == "新タイトル"
    assert article.sections[0].heading == "見出し"
    assert mock_create.call_count == 1


async def test_generate_retries_once_on_invalid_json_then_succeeds():
    client, mock_create = _client_with_responses(["not json at all", VALID_JSON_BODY])
    with patch("app.services.generator.openai.AsyncOpenAI", return_value=client):
        article = await generator.generate(SOURCE, REQUEST)

    assert article.title == "新タイトル"
    assert mock_create.call_count == 2


async def test_generate_raises_generation_error_after_two_failures():
    client, mock_create = _client_with_responses(["broken", "still broken"])
    with patch("app.services.generator.openai.AsyncOpenAI", return_value=client):
        with pytest.raises(GenerationError):
            await generator.generate(SOURCE, REQUEST)

    assert mock_create.call_count == 2


async def test_generate_translates_authentication_error():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(401, request=request)
    exc = openai.AuthenticationError("invalid api key", response=response, body=None)
    client = _client_raising(exc)

    with patch("app.services.generator.openai.AsyncOpenAI", return_value=client):
        with pytest.raises(GenerationError):
            await generator.generate(SOURCE, REQUEST)


async def test_generate_translates_rate_limit_error():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(429, request=request)
    exc = openai.RateLimitError("rate limited", response=response, body=None)
    client = _client_raising(exc)

    with patch("app.services.generator.openai.AsyncOpenAI", return_value=client):
        with pytest.raises(GenerationError):
            await generator.generate(SOURCE, REQUEST)
