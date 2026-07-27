import charset_normalizer
import httpx

from app.config import settings
from app.errors import FetchError, TooLargeError, UnsupportedContentError
from app.services.urlguard import validate_url

USER_AGENT = "Kijiya/1.0 (+https://example.local)"
ACCEPT_LANGUAGE = "ja,en;q=0.8"
MAX_REDIRECTS = 5
ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


async def fetch(url: str) -> tuple[str, str]:
    current_url = validate_url(url)
    headers = {"User-Agent": USER_AGENT, "Accept-Language": ACCEPT_LANGUAGE}

    async with httpx.AsyncClient(follow_redirects=False, timeout=settings.fetch_timeout) as client:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                async with client.stream("GET", current_url, headers=headers) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise FetchError("リダイレクト先が不明です")
                        current_url = validate_url(str(httpx.URL(current_url).join(location)))
                        continue

                    return current_url, await _read_html(response)
            except httpx.TimeoutException as exc:
                raise FetchError("ページの取得がタイムアウトしました") from exc
            except httpx.HTTPError as exc:
                raise FetchError("ページを取得できませんでした") from exc

    raise FetchError("リダイレクトの回数が上限を超えました")


async def _read_html(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedContentError(
            f"サポートしていないContent-Typeです: {content_type or '不明'}"
        )

    body = bytearray()
    async for chunk in response.aiter_bytes():
        body.extend(chunk)
        if len(body) > settings.max_download_bytes:
            raise TooLargeError("ページのサイズが上限を超えています")

    return _decode(bytes(body), response.charset_encoding)


def _decode(body: bytes, charset: str | None) -> str:
    if charset:
        try:
            return body.decode(charset)
        except (UnicodeDecodeError, LookupError):
            pass

    detected = charset_normalizer.from_bytes(body).best()
    if detected is not None:
        return str(detected)

    return body.decode("utf-8", errors="replace")
