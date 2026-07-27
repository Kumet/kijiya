import socket
from unittest.mock import patch

import httpx
import pytest
import respx

from app.config import settings
from app.errors import FetchError, TooLargeError, UnsupportedContentError
from app.services import fetcher


def _addrinfo(ip: str):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]


_real_getaddrinfo = socket.getaddrinfo


def _fake_getaddrinfo(host, *args, **kwargs):
    if host == "example.com":
        return _addrinfo("93.184.216.34")
    return _real_getaddrinfo(host, *args, **kwargs)


@pytest.fixture(autouse=True)
def _mock_public_dns():
    with patch("socket.getaddrinfo", side_effect=_fake_getaddrinfo):
        yield


async def test_fetch_returns_final_url_and_html():
    with respx.mock:
        respx.get("https://example.com/article").mock(
            return_value=httpx.Response(
                200, headers={"content-type": "text/html; charset=utf-8"}, text="<html>ok</html>"
            )
        )
        final_url, html = await fetcher.fetch("https://example.com/article")

    assert final_url == "https://example.com/article"
    assert "<html>ok</html>" in html


async def test_fetch_follows_redirect_and_revalidates_target():
    with respx.mock:
        respx.get("https://example.com/old").mock(
            return_value=httpx.Response(302, headers={"location": "https://example.com/new"})
        )
        respx.get("https://example.com/new").mock(
            return_value=httpx.Response(
                200, headers={"content-type": "text/html"}, text="<html>new</html>"
            )
        )
        final_url, html = await fetcher.fetch("https://example.com/old")

    assert final_url == "https://example.com/new"
    assert "new" in html


async def test_fetch_rejects_redirect_to_private_host():
    from app.errors import UnsafeUrlError

    with respx.mock:
        respx.get("https://example.com/old").mock(
            return_value=httpx.Response(302, headers={"location": "http://127.0.0.1/"})
        )
        with pytest.raises(UnsafeUrlError):
            await fetcher.fetch("https://example.com/old")


async def test_fetch_raises_for_unsupported_content_type():
    with respx.mock:
        respx.get("https://example.com/data.json").mock(
            return_value=httpx.Response(
                200, headers={"content-type": "application/json"}, text="{}"
            )
        )
        with pytest.raises(UnsupportedContentError):
            await fetcher.fetch("https://example.com/data.json")


async def test_fetch_raises_when_too_large(monkeypatch):
    monkeypatch.setattr(settings, "max_download_bytes", 10)
    with respx.mock:
        respx.get("https://example.com/big").mock(
            return_value=httpx.Response(
                200, headers={"content-type": "text/html"}, text="<html>" + "a" * 1000 + "</html>"
            )
        )
        with pytest.raises(TooLargeError):
            await fetcher.fetch("https://example.com/big")


async def test_fetch_raises_fetch_error_on_timeout():
    with respx.mock:
        respx.get("https://example.com/slow").mock(side_effect=httpx.ConnectTimeout("timeout"))
        with pytest.raises(FetchError):
            await fetcher.fetch("https://example.com/slow")
