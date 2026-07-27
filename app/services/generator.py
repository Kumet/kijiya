import json
from pathlib import Path

import openai
from jinja2 import Template
from pydantic import ValidationError

from app.config import settings
from app.errors import GenerationError
from app.models import GeneratedArticle, GenerateRequest, SourceArticle

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "article.md"

_RETRY_INSTRUCTION = (
    "\n\n<instruction>\nJSONのみで再出力せよ。前置きや説明は一切書かない。\n</instruction>"
)

_USER_MESSAGE_TEMPLATE = Template(
    "<source_metadata>\n"
    "title: {{ title }}\n"
    "site: {{ site_name }}\n"
    "author: {{ author }}\n"
    "published: {{ published_at }}\n"
    "url: {{ url }}\n"
    "truncated: {{ truncated }}\n"
    "</source_metadata>\n\n"
    "<source_text>\n"
    "{{ text }}\n"
    "</source_text>\n\n"
    "<instruction>\n"
    "{{ prompt }}\n"
    "</instruction>\n"
)


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_user_message(source: SourceArticle, req: GenerateRequest) -> str:
    return _USER_MESSAGE_TEMPLATE.render(
        title=source.title or "(不明)",
        site_name=source.site_name or "(不明)",
        author=source.author or "(不明)",
        published_at=source.published_at or "(不明)",
        url=source.url,
        truncated=source.truncated,
        text=source.text,
        prompt=req.prompt,
    )


def _parse_article(raw_text: str) -> GeneratedArticle:
    data = json.loads(raw_text)
    return GeneratedArticle.model_validate(data)


async def _call(client: openai.AsyncOpenAI, system_prompt: str, user_content: str) -> str:
    response = await client.chat.completions.create(
        model=settings.model,
        max_completion_tokens=settings.max_tokens,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return response.choices[0].message.content or ""


def _translate_api_error(exc: openai.APIError) -> GenerationError:
    if isinstance(exc, openai.AuthenticationError):
        return GenerationError("APIキーの認証に失敗しました。設定を確認してください。")
    if isinstance(exc, openai.RateLimitError):
        return GenerationError("APIのレート制限に達しました。時間をおいて試してください。")
    if isinstance(exc, openai.APIStatusError) and exc.status_code == 503:
        return GenerationError("生成サービスが混雑しています。時間をおいて試してください。")
    return GenerationError(
        "記事を生成できませんでした。指示を短くするか、時間をおいて試してください。"
    )


async def generate(source: SourceArticle, req: GenerateRequest) -> GeneratedArticle:
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    system_prompt = _load_system_prompt()
    user_message = _build_user_message(source, req)

    try:
        raw = await _call(client, system_prompt, user_message)
    except openai.APIError as exc:
        raise _translate_api_error(exc) from exc

    try:
        return _parse_article(raw)
    except (json.JSONDecodeError, ValidationError):
        pass

    try:
        raw = await _call(client, system_prompt, user_message + _RETRY_INSTRUCTION)
    except openai.APIError as exc:
        raise _translate_api_error(exc) from exc

    try:
        return _parse_article(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise GenerationError(
            "記事を生成できませんでした。指示を短くするか、時間をおいて試してください。"
        ) from exc
