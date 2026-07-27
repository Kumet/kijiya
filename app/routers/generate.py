import logging
from datetime import UTC, datetime
from secrets import token_hex
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.errors import (
    ExtractionError,
    FetchError,
    GenerationError,
    KijiyaError,
    RateLimitError,
    TooLargeError,
    UnsafeUrlError,
    UnsupportedContentError,
)
from app.models import GenerateRequest
from app.services import extractor, fetcher, generator, renderer
from app.services.ratelimit import rate_limiter
from app.services.store import store

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

ERROR_MESSAGES: dict[type[KijiyaError], str] = {
    UnsafeUrlError: "このURLは取得できません。公開されているhttp/httpsのページを指定してください。",
    FetchError: "ページを取得できませんでした。URLを確認するか、時間をおいて試してください。",
    TooLargeError: "ページが大きすぎます。別の記事URLで試してください。",
    UnsupportedContentError: "HTMLページではありません。記事ページのURLを指定してください。",
    ExtractionError: (
        "本文を取り出せませんでした。ログイン必須のページや動的生成のページは扱えません。"
    ),
    GenerationError: "記事を生成できませんでした。指示を短くするか、時間をおいて試してください。",
    RateLimitError: "生成回数の上限に達しました。1時間後に再度お試しください。",
}

INVALID_INPUT_MESSAGE = "入力内容を確認してください。URLや指示の形式を見直してください。"
UNEXPECTED_ERROR_MESSAGE = "予期しないエラーが発生しました。時間をおいて試してください。"


def _build_filename() -> str:
    date_str = datetime.now(UTC).strftime("%Y%m%d")
    return f"生成記事-{date_str}-{token_hex(3)}.html"


def _error_response(request: Request, message: str) -> HTMLResponse:
    return templates.TemplateResponse(request, "partials/error.html", {"message": message})


@router.post("/api/generate", response_class=HTMLResponse)
async def generate_article(
    request: Request,
    url: str = Form(...),
    prompt: str = Form(...),
    tone: str = Form("neutral"),
    length: str = Form("medium"),
):
    client_ip = request.client.host if request.client else "unknown"

    try:
        await rate_limiter.check(client_ip)
        req = GenerateRequest(url=url, prompt=prompt, tone=tone, length=length)

        final_url, html = await fetcher.fetch(str(req.url))
        source = extractor.extract(html, final_url)
        article = await generator.generate(source, req)
        rendered_html = renderer.render(article, source)

        filename = _build_filename()
        doc_id = await store.put(rendered_html, filename)

        return templates.TemplateResponse(
            request,
            "partials/result.html",
            {"article": article, "source": source, "doc_id": doc_id},
        )
    except ValidationError:
        logger.info("invalid generate request from %s", client_ip)
        return _error_response(request, INVALID_INPUT_MESSAGE)
    except KijiyaError as exc:
        logger.info("generate failed for %s: %s", client_ip, exc.user_message)
        message = ERROR_MESSAGES.get(type(exc), exc.user_message)
        return _error_response(request, message)
    except Exception:
        logger.exception("unexpected error during generate for %s", client_ip)
        return _error_response(request, UNEXPECTED_ERROR_MESSAGE)


@router.get("/preview/{doc_id}", response_class=HTMLResponse)
async def preview(doc_id: str):
    doc = await store.get(doc_id)
    if doc is None:
        return HTMLResponse(
            "<p>プレビューが見つかりません。生成から時間が経過したか、IDが誤っている可能性があります。</p>",
            status_code=404,
        )
    return HTMLResponse(doc.html)


@router.get("/download/{doc_id}")
async def download(doc_id: str):
    doc = await store.get(doc_id)
    if doc is None:
        return HTMLResponse(
            "<p>ダウンロード対象が見つかりません。生成から時間が経過したか、IDが誤っている可能性があります。</p>",
            status_code=404,
        )

    encoded_filename = quote(doc.filename)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
    return HTMLResponse(doc.html, headers=headers)
