import json
from pathlib import Path

import anthropic
from jinja2 import Template
from pydantic import ValidationError

from app.config import settings
from app.errors import GenerationError
from app.models import GeneratedArticle, GenerateRequest, SourceArticle

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "article.md"

TONE_LABELS = {
    "neutral": "そのまま",
    "casual": "くだけた",
    "formal": "かたい",
    "explainer": "解説調",
}

LENGTH_LABELS = {
    "short": "短め (600〜900字)",
    "medium": "ふつう (1200〜1800字)",
    "long": "長め (2500〜3500字)",
}

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
    "</instruction>\n\n"
    "<style>\n"
    "トーン: {{ tone_label }}\n"
    "分量の目安: {{ length_label }}\n"
    "</style>\n"
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
        tone_label=TONE_LABELS[req.tone],
        length_label=LENGTH_LABELS[req.length],
    )


def _parse_article(raw_text: str) -> GeneratedArticle:
    text = raw_text if raw_text.lstrip().startswith("{") else "{" + raw_text
    data = json.loads(text)
    return GeneratedArticle.model_validate(data)


async def _call(client: anthropic.AsyncAnthropic, system_prompt: str, user_content: str) -> str:
    response = await client.messages.create(
        model=settings.model,
        max_tokens=settings.max_tokens,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": "{"},
        ],
    )
    return "{" + response.content[0].text


def _translate_api_error(exc: anthropic.APIError) -> GenerationError:
    if isinstance(exc, anthropic.AuthenticationError):
        return GenerationError("APIキーの認証に失敗しました。設定を確認してください。")
    if isinstance(exc, anthropic.RateLimitError):
        return GenerationError("APIのレート制限に達しました。時間をおいて試してください。")
    if isinstance(exc, anthropic.APIStatusError) and exc.status_code == 529:
        return GenerationError("生成サービスが混雑しています。時間をおいて試してください。")
    return GenerationError(
        "記事を生成できませんでした。指示を短くするか、時間をおいて試してください。"
    )


async def generate(source: SourceArticle, req: GenerateRequest) -> GeneratedArticle:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    system_prompt = _load_system_prompt()
    user_message = _build_user_message(source, req)

    try:
        raw = await _call(client, system_prompt, user_message)
    except anthropic.APIError as exc:
        raise _translate_api_error(exc) from exc

    try:
        return _parse_article(raw)
    except (json.JSONDecodeError, ValidationError):
        pass

    try:
        raw = await _call(client, system_prompt, user_message + _RETRY_INSTRUCTION)
    except anthropic.APIError as exc:
        raise _translate_api_error(exc) from exc

    try:
        return _parse_article(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise GenerationError(
            "記事を生成できませんでした。指示を短くするか、時間をおいて試してください。"
        ) from exc
