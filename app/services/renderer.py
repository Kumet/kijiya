import re
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from app.models import GeneratedArticle, SourceArticle

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"\*(.+?)\*")
_CODE_RE = re.compile(r"`(.+?)`")


def inline_md(text: str) -> Markup:
    escaped = str(escape(text))
    escaped = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = _ITALIC_RE.sub(r"<em>\1</em>", escaped)
    escaped = _CODE_RE.sub(r"<code>\1</code>", escaped)
    return Markup(escaped)


_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "j2"]),
)
_env.filters["inline_md"] = inline_md


def render(article: GeneratedArticle, source: SourceArticle) -> str:
    template = _env.get_template("output/article.html.j2")
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return template.render(article=article, source=source, generated_at=generated_at)
