# Kijiya (記事屋) — 設計書 / 実装指示書

> このドキュメントは Claude Code CLI にそのまま渡して実装させることを想定しています。
> 実行例: `claude "kijiya-design.md を読んで、記載どおりにプロジェクトを実装して。フェーズ1から順に進め、各フェーズの完了条件を満たしたら次へ進むこと。"`

---

## 0. プロジェクト概要

**プロジェクト名: Kijiya (記事屋)** / パッケージ名 `kijiya`

記事URLとプロンプトを入力すると、その記事の内容を素材として新しい記事を生成し、
ブラウザ上でプレビューして完成HTMLをダウンロードできるWebアプリケーション。

### やること (スコープ)

- URLから記事本文を抽出する
- ユーザーのプロンプトに従い LLM で新しい記事を生成する
- 生成結果を完成品のHTMLとしてプレビュー表示する
- そのHTMLを1ファイルでダウンロードする

### やらないこと (非スコープ / v1)

- ユーザー認証、DB永続化、生成履歴の保存
- 複数URLの同時入力、PDF/画像の取り込み
- 生成のストリーミング表示 (将来拡張として §16 に記載)
- 有料APIのコスト管理UI

---

## 1. 技術スタック

| 領域 | 採用 | 備考 |
|---|---|---|
| 言語 | Python 3.12+ | |
| パッケージ管理 | uv | `uv sync` / `uv run` |
| Webフレームワーク | FastAPI | |
| ASGIサーバー | uvicorn | |
| テンプレート | Jinja2 (`fastapi.templating.Jinja2Templates`) | |
| フロント | htmx 2.x + 素のCSS | CDN読み込み、ビルドツールなし |
| HTTPクライアント | httpx (async) | |
| 本文抽出 | trafilatura (主) / readability-lxml + BeautifulSoup (フォールバック) | 日本語記事に強い |
| LLM | Anthropic Python SDK (`anthropic`) | モデルは環境変数で差し替え可能 |
| 設定 | pydantic-settings | |
| テスト | pytest, pytest-asyncio, respx | |
| Lint/Format | ruff | |

**依存パッケージ (pyproject.toml)**

```
fastapi[standard]
jinja2
httpx
trafilatura
readability-lxml
beautifulsoup4
lxml
anthropic
pydantic-settings

[dev]
pytest
pytest-asyncio
respx
ruff
```

---

## 2. アーキテクチャ / 処理フロー

```
[ブラウザ]
   │ 1. POST /api/generate  (hx-post, form: url, prompt, tone, length)
   ▼
[FastAPI: routers/generate.py]
   │ 2. fetcher.fetch()      URL検証(SSRF対策) → HTML取得
   │ 3. extractor.extract()  本文/タイトル/著者/日付を抽出
   │ 4. generator.generate() LLMへ投げてJSON構造の記事を得る
   │ 5. renderer.render()    JSON → 完成HTML(単一ファイル, CSS埋め込み)
   │ 6. store.put()          doc_id を発行しメモリ上にTTL保存
   ▼
   7. HTMLフラグメント(partials/result.html)を返す
      → <iframe src="/preview/{doc_id}"> でプレビュー
      → <a href="/download/{doc_id}"> でダウンロード
```

**設計上の重要な決定**

- **LLMにはHTMLを書かせない。** 構造化JSONを返させ、サーバー側で信頼できるテンプレートに流し込む。
  これによりXSS・壊れたHTML・スタイル崩れを構造的に排除する。
- **生成物はメモリ上のTTLストアに置く。** DBもファイルI/Oも不要。デフォルトTTL 30分。
- **プレビューは iframe + sandbox。** 生成HTMLのCSSがアプリ本体のUIを侵食しないため。

---

## 3. ディレクトリ構成

```
kijiya/
├── pyproject.toml
├── README.md
├── .env.example
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPIアプリ生成、ルーター登録、例外ハンドラ
│   ├── config.py                # Settings (pydantic-settings)
│   ├── errors.py                # 独自例外とユーザー向けメッセージ
│   ├── models.py                # Pydanticモデル
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── pages.py             # GET /, GET /healthz
│   │   └── generate.py          # POST /api/generate, GET /preview/{id}, GET /download/{id}
│   ├── services/
│   │   ├── __init__.py
│   │   ├── urlguard.py          # SSRF対策のURL検証
│   │   ├── fetcher.py           # HTML取得
│   │   ├── extractor.py         # 本文抽出
│   │   ├── generator.py         # LLM呼び出し
│   │   ├── renderer.py          # 記事JSON → 完成HTML
│   │   └── store.py             # TTL付きインメモリストア
│   ├── prompts/
│   │   └── article.md           # LLMへのシステムプロンプト(テンプレート)
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── partials/
│   │   │   ├── result.html
│   │   │   └── error.html
│   │   └── output/
│   │       └── article.html.j2  # ダウンロードされる完成HTML
│   └── static/
│       └── css/app.css
└── tests/
    ├── conftest.py
    ├── test_urlguard.py
    ├── test_extractor.py
    ├── test_renderer.py
    ├── test_store.py
    └── test_api.py
```

---

## 4. 設定 (`app/config.py` / `.env`)

`pydantic_settings.BaseSettings` で実装。`.env` から読む。

| 変数名 | 型 | デフォルト | 説明 |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | str | (必須) | APIキー |
| `MODEL` | str | `claude-sonnet-5` | 生成に使うモデル |
| `MAX_TOKENS` | int | `8000` | LLM出力上限 |
| `FETCH_TIMEOUT` | float | `15.0` | 取得タイムアウト(秒) |
| `MAX_DOWNLOAD_BYTES` | int | `3_000_000` | 取得HTMLの上限サイズ |
| `MAX_SOURCE_CHARS` | int | `24000` | LLMへ渡す本文の最大文字数 |
| `DOC_TTL_SECONDS` | int | `1800` | 生成物の保持時間 |
| `MAX_DOCS` | int | `200` | ストアの最大件数 |
| `ALLOW_PRIVATE_HOSTS` | bool | `False` | Trueでプライベートアドレス許可(ローカル検証用) |
| `RATE_LIMIT_PER_HOUR` | int | `30` | 同一IPからの生成回数上限 |

`.env.example` には `ANTHROPIC_API_KEY=` を含む全項目をコメント付きで記載すること。

---

## 5. データモデル (`app/models.py`)

```python
class GenerateRequest(BaseModel):
    url: HttpUrl
    prompt: str = Field(min_length=1, max_length=2000)
    tone: Literal["neutral", "casual", "formal", "explainer"] = "neutral"
    length: Literal["short", "medium", "long"] = "medium"

class SourceArticle(BaseModel):
    url: str
    title: str | None
    author: str | None
    published_at: str | None
    site_name: str | None
    text: str            # プレーンテキスト本文
    truncated: bool      # MAX_SOURCE_CHARSで切り詰めたか

class Section(BaseModel):
    heading: str
    paragraphs: list[str]

class GeneratedArticle(BaseModel):
    title: str
    lede: str                      # リード文(1〜3文)
    sections: list[Section]
    tags: list[str] = []
    takeaways: list[str] = []      # 箇条書きのまとめ(0件可)

class StoredDoc(BaseModel):
    doc_id: str
    html: str
    filename: str                  # 例: "生成記事-20260727-a1b2c3.html"
    created_at: float
```

**length の目安 (プロンプトに埋め込む)**: short=600〜900字 / medium=1200〜1800字 / long=2500〜3500字。

---

## 6. API仕様

### `GET /`
トップページ。入力フォームを表示。

### `GET /healthz`
`{"status": "ok"}` を返す。

### `POST /api/generate`
- Content-Type: `application/x-www-form-urlencoded`
- フォーム項目: `url`, `prompt`, `tone`, `length`
- レスポンス: **HTMLフラグメント** (`partials/result.html`)。ステータスは常に200を返し、
  失敗時は `partials/error.html` をレンダリングする (htmxの既定では非2xxは差し替えられないため)。
- 成功時フラグメントに含めるもの:
  - 生成タイトル、タグ
  - `<iframe src="/preview/{doc_id}" sandbox loading="lazy">`
  - ダウンロードボタン (`<a href="/download/{doc_id}" download>`)
  - 元記事へのリンク、抽出文字数、切り詰めの有無

### `GET /preview/{doc_id}`
生成HTMLをそのまま `text/html` で返す。iframe用。存在しなければ 404 とシンプルな案内HTML。
レスポンスヘッダに `X-Frame-Options` は付けない (同一オリジンiframeのため)。

### `GET /download/{doc_id}`
同じHTMLを `Content-Disposition: attachment` で返す。日本語ファイル名対応のため
`filename*=UTF-8''<percent-encoded>` 形式を使用すること。

---

## 7. 各サービスの仕様

### 7.1 `services/urlguard.py` — SSRF対策 (**必須**)

`validate_url(url: str) -> str` を実装。以下をすべて満たさない場合 `UnsafeUrlError` を送出。

1. スキームが `http` / `https` のいずれか
2. ホスト名が存在する
3. `socket.getaddrinfo` で解決した**すべてのIP**が、`ipaddress` モジュール判定で
   private / loopback / link-local / reserved / multicast の**いずれでもない**
   (`settings.ALLOW_PRIVATE_HOSTS=True` のときのみスキップ)
4. ポートが指定される場合は 80 / 443 のみ

リダイレクト追従時も**各ホップで同じ検証を行う**こと (fetcherで手動リダイレクト処理)。

### 7.2 `services/fetcher.py`

```python
async def fetch(url: str) -> tuple[str, str]:  # (final_url, html)
```

- `httpx.AsyncClient(follow_redirects=False)` を使い、最大5回まで手動でリダイレクトを辿る
- 各ホップで `urlguard.validate_url` を実行
- User-Agent: `Kijiya/1.0 (+https://example.local)`
- `Accept-Language: ja,en;q=0.8`
- ストリーミング受信し、`MAX_DOWNLOAD_BYTES` を超えたら `TooLargeError`
- Content-Type が `text/html` / `application/xhtml+xml` 以外なら `UnsupportedContentError`
- 文字コードは httpx の推定 → 失敗時 `charset_normalizer` フォールバック
- タイムアウト/接続失敗は `FetchError`

### 7.3 `services/extractor.py`

```python
def extract(html: str, url: str) -> SourceArticle
```

1. `trafilatura.extract(html, url=url, output_format="json", include_comments=False, favor_precision=True)`
   でテキストとメタデータ(title/author/date/sitename)を取得
2. 本文が200文字未満なら `readability.Document(html).summary()` → BeautifulSoup の `get_text("\n")` で再挑戦
3. それでも200文字未満なら `ExtractionError` ("本文を取り出せませんでした")
4. 連続空行を1つに正規化、前後の空白除去
5. `MAX_SOURCE_CHARS` を超えたら切り詰めて `truncated=True`

### 7.4 `services/generator.py`

```python
async def generate(source: SourceArticle, req: GenerateRequest) -> GeneratedArticle
```

- `anthropic.AsyncAnthropic` を使用
- `app/prompts/article.md` をJinja2で読み込みシステムプロンプトを構築
- ユーザーメッセージに、元記事のメタデータ・本文・ユーザープロンプトを明確なタグで区切って渡す
- **出力はJSONのみ**を強制。`assistant` の事前入力 (prefill) として `{` を渡し、
  返ってきたテキストの先頭に `{` を補ってパースする
- パース失敗時は1回だけリトライ (「JSONのみで再出力せよ」と指示)。2回失敗で `GenerationError`
- `GeneratedArticle` にバリデーションして返す
- API側のエラー (認証・レート制限・過負荷) は種類に応じたメッセージの `GenerationError` に変換

### 7.5 `services/renderer.py`

```python
def render(article: GeneratedArticle, source: SourceArticle) -> str
```

- `templates/output/article.html.j2` をレンダリング。CSSは `<style>` で**インライン埋め込み**
  (ダウンロード後に単体で開いても崩れないこと)
- すべての値はJinja2の自動エスケープを通す
- 段落テキストは最小限のインライン記法のみ許可する `inline_md()` を用意する:
  1. まずHTMLエスケープ
  2. その後 `**強調**` → `<strong>`、`*斜体*` → `<em>`、`` `コード` `` → `<code>` に置換
  3. `markupsafe.Markup` で返す
  ※ この順序を必ず守ること (エスケープが先)

### 7.6 `services/store.py`

- `dict[str, StoredDoc]` + `asyncio.Lock` で実装 (外部依存なし)
- `put(html, filename) -> doc_id` (doc_id は `secrets.token_urlsafe(12)`)
- `get(doc_id) -> StoredDoc | None` (TTL切れは None を返し削除)
- put時に期限切れを掃除し、`MAX_DOCS` 超過時は古い順に削除

---

## 8. LLMプロンプト設計 (`app/prompts/article.md`)

以下の内容で作成すること。

**システムプロンプト**

```
あなたは日本語のWebメディアで働く編集者兼ライターです。
与えられた「元記事」を素材として、ユーザーの指示に沿った新しい記事を書きます。

守ること:
- 元記事の事実関係を変えない。書かれていない数値・固有名詞・出来事を追加しない。
- 元記事の文章を丸写ししない。構成・語彙・切り口を自分の言葉で組み立て直す。
  引用が必要な場合のみ、1箇所30字以内に留める。
- 元記事に答えがない点をユーザーが求めている場合は、推測で埋めず、
  その旨を本文中で明示する。
- 見出しは内容を要約したものにする。「はじめに」「まとめ」のような
  中身のない見出しは使わない。
- 文体は指定されたトーンに合わせる。一文は短く、主語と述語を対応させる。

出力形式:
必ず次のJSONだけを出力する。前置き、説明、コードフェンスは一切書かない。

{
  "title": "記事タイトル(40字以内)",
  "lede": "リード文。1〜3文で記事全体の要点を伝える",
  "sections": [
    {"heading": "見出し", "paragraphs": ["段落1", "段落2"]}
  ],
  "tags": ["タグ", "タグ"],
  "takeaways": ["要点1", "要点2"]
}

段落の中では **強調**、*斜体*、`コード` の3種類だけ使える。
HTMLタグは書かない。
```

**ユーザーメッセージの構造**

```
<source_metadata>
title: {{ title }}
site: {{ site_name }}
author: {{ author }}
published: {{ published_at }}
url: {{ url }}
truncated: {{ truncated }}
</source_metadata>

<source_text>
{{ text }}
</source_text>

<instruction>
{{ prompt }}
</instruction>

<style>
トーン: {{ tone_label }}
分量の目安: {{ length_label }}
</style>
```

---

## 9. 出力HTML仕様 (`templates/output/article.html.j2`)

ダウンロードされる**単一HTMLファイル**。以下を満たすこと。

- `<!doctype html>` / `<html lang="ja">` / `<meta charset="utf-8">` / viewport
- `<title>` は記事タイトル
- OGP相当の `<meta name="description">` にリード文
- CSSは `<style>` に内包。外部リクエストは**一切行わない** (フォントもWebフォント読み込みなし、
  システムフォントスタックを使用)
- 構造: `header`(タイトル/リード/タグ) → `article`(section > h2 > p) →
  `aside`(takeaways) → `footer`(出典: 元記事タイトルとURLへのリンク、生成日時、
  「この記事はAIが元記事をもとに再構成したものです」の注記)
- 本文の最大幅 68ch、行間 1.9、フォントサイズ 17px、ダークモード対応
  (`@media (prefers-color-scheme: dark)`)
- 印刷用スタイル (`@media print`) でリンクURLを脚注表示

---

## 10. フロントエンド仕様

### 10.1 `index.html` の構造

- ヘッダー: プロダクト名 `記事屋` と一行説明「記事のURLと指示から、新しい記事を組み直す。」
- 入力フォーム (`<form>`, htmx属性):
  ```html
  <form hx-post="/api/generate"
        hx-target="#result"
        hx-swap="innerHTML"
        hx-indicator="#indicator"
        hx-disabled-elt="find button, find input, find select">
  ```
  - `url` (type=url, required, placeholder="https://...")
  - `prompt` (textarea, required, rows=4,
     placeholder="例: 高校生にもわかるように、専門用語を噛み砕いて解説記事にして")
  - `tone` (select: そのまま / くだけた / かたい / 解説調)
  - `length` (radio: 短め / ふつう / 長め)
  - 送信ボタン: ラベルは **「記事を組む」**
- `#indicator`: 生成中の表示。`.htmx-indicator` クラスで制御。
  文言は「記事を組んでいます… (30秒ほどかかります)」
- `#result`: 結果差し込み先。初期状態は空ではなく、使い方を1行で示す空状態を置く。

### 10.2 `partials/result.html`

- 見出し行: 生成タイトル + タグ
- メタ行: 元記事へのリンク、抽出文字数、`truncated` なら「元記事が長いため前半のみ使用」
- プレビュー: `<iframe src="/preview/{{ doc_id }}" sandbox title="生成記事のプレビュー" height="720">`
- ボタン: 「HTMLをダウンロード」(primary) / 「別の指示でやり直す」(フォームにフォーカスを戻す)

### 10.3 `partials/error.html`

`errors.py` の例外種別に応じたメッセージを表示。**何が起きて、次に何をすればよいか**を書く。
謝罪文は書かない。例:

| 例外 | 表示メッセージ |
|---|---|
| `UnsafeUrlError` | このURLは取得できません。公開されているhttp/httpsのページを指定してください。 |
| `FetchError` | ページを取得できませんでした。URLを確認するか、時間をおいて試してください。 |
| `TooLargeError` | ページが大きすぎます。別の記事URLで試してください。 |
| `UnsupportedContentError` | HTMLページではありません。記事ページのURLを指定してください。 |
| `ExtractionError` | 本文を取り出せませんでした。ログイン必須のページや動的生成のページは扱えません。 |
| `GenerationError` | 記事を生成できませんでした。指示を短くするか、時間をおいて試してください。 |
| `RateLimitError` | 生成回数の上限に達しました。1時間後に再度お試しください。 |

### 10.4 デザイン方針 (`static/css/app.css`)

**コンセプト: 赤入れ (校正)。** 編集者が原稿に朱を入れる行為が、このアプリのやっていることそのもの。
朱色はアクセントとしてのみ使い、面で塗らない。

デザイントークン (CSS変数として定義):

| 役割 | 値 |
|---|---|
| `--paper` | `#F7F6F3` (本体背景) |
| `--paper-raised` | `#FFFFFF` (カード/フォーム) |
| `--ink` | `#1A1E29` (本文) |
| `--ink-mute` | `#5C6273` (補助テキスト) |
| `--rule` | `#DCD9D2` (罫線) |
| `--vermilion` | `#C8341F` (朱: アクセント、フォーカス、主要ボタン) |
| `--vermilion-soft` | `#F3E2DE` (朱の淡色: タグ背景) |

- タイポグラフィ: 見出しは明朝 (`"Hiragino Mincho ProN", "Yu Mincho", serif`)、
  本文はゴシック (`system-ui, "Hiragino Sans", "Yu Gothic", sans-serif`)、
  URL・数値などのメタ情報のみ等幅。この3役割を混ぜない。
- **署名的要素**: フォームと結果カードの左端に幅3pxの朱色の縦罫を引く (原稿の朱線)。
  これがこのアプリ唯一の装飾。他に飾りを足さない。
- 角丸は `4px` まで。影は使わず、1pxの `--rule` で境界を作る。
- レイアウト: 最大幅 900px 中央寄せ。768px以下で1カラムに素直に落とす。
- フォーカスリングは `outline: 2px solid var(--vermilion); outline-offset: 2px;` を必ず可視化。
- `@media (prefers-reduced-motion: reduce)` でアニメーションを無効化。
- ローディングは回転スピナーではなく、朱色の細い横バーが左右に往復する表現にする。

---

## 11. セキュリティ要件

1. **SSRF**: §7.1 の検証を、初回およびすべてのリダイレクト先に適用する。
2. **XSS**: LLM出力をHTMLとして解釈しない (§7.5)。Jinja2の自動エスケープを無効化しない。
   `|safe` を使ってよいのは `inline_md()` の戻り値のみ。
3. **iframe**: `sandbox` 属性を値なしで指定 (スクリプト・フォーム・同一オリジンすべて禁止)。
4. **レート制限**: 同一IPあたり `RATE_LIMIT_PER_HOUR` 回。インメモリのスライディングウィンドウで実装し、
   超過時は `RateLimitError`。
5. **入力長**: prompt は2000字、URLは2048字で打ち切る。
6. **APIキー**: ログにも例外メッセージにも絶対に含めない。
7. 生成HTMLに元記事の本文をそのまま埋め込まない (出典リンクのみ)。

---

## 12. エラーハンドリング (`app/errors.py`)

```python
class KijiyaError(Exception):
    user_message: str

class UnsafeUrlError(KijiyaError): ...
class FetchError(KijiyaError): ...
class TooLargeError(KijiyaError): ...
class UnsupportedContentError(KijiyaError): ...
class ExtractionError(KijiyaError): ...
class GenerationError(KijiyaError): ...
class RateLimitError(KijiyaError): ...
```

- `routers/generate.py` で `KijiyaError` を捕捉し、`partials/error.html` を **HTTP 200** で返す。
- 想定外の例外は `logging.exception` に記録し、汎用メッセージで `error.html` を返す。
- ログは `logging.basicConfig` レベルで十分。URLはログに出してよいが、プロンプト全文は出さない。

---

## 13. テスト (`tests/`)

`pytest` + `httpx.ASGITransport` で実装。**LLM APIとネットワークは必ずモックする。**

| ファイル | 内容 |
|---|---|
| `test_urlguard.py` | `http://localhost`, `http://127.0.0.1`, `http://192.168.0.1`, `file://`, `ftp://`, ポート8080 を拒否。通常のhttpsを許可。 |
| `test_extractor.py` | 固定HTMLフィクスチャから本文・タイトルを抽出できる。本文が短いHTMLで `ExtractionError`。 |
| `test_renderer.py` | `<script>alert(1)</script>` を含む段落がエスケープされる。`**強調**` が `<strong>` になる。 |
| `test_store.py` | put/get が往復する。TTL経過後にNoneを返す。`MAX_DOCS` 超過で古いものが消える。 |
| `test_api.py` | `GET /` が200。`POST /api/generate` が respx + generatorモックで成功フラグメントを返す。不正URLでエラーフラグメントを返す (ステータスは200)。`GET /download/{id}` が `Content-Disposition` 付きで返る。存在しないidで404。 |

目標: 上記シナリオをすべてカバーすること (カバレッジ率の数値目標は設けない)。

---

## 14. 実装フェーズ (この順で進めること)

### フェーズ1: 骨組み
`pyproject.toml`, `.env.example`, `.gitignore`, `app/main.py`, `config.py`, `errors.py`, `models.py`,
`routers/pages.py`、最小の `base.html` / `index.html` / `app.css`。

**完了条件**: `uv run uvicorn app.main:app --reload` が起動し、`GET /` でフォームが表示され、
`GET /healthz` が200を返す。

### フェーズ2: 取得と抽出
`urlguard.py`, `fetcher.py`, `extractor.py` と対応するテスト。

**完了条件**: `uv run pytest tests/test_urlguard.py tests/test_extractor.py` が通る。

### フェーズ3: 生成とレンダリング
`prompts/article.md`, `generator.py`, `renderer.py`, `output/article.html.j2`, `store.py` とテスト。

**完了条件**: `uv run pytest` が全通過。レンダリング結果をファイルに書き出してブラウザで開き、
単体で正しく表示されること。

### フェーズ4: 結線とUI仕上げ
`routers/generate.py`, `partials/result.html`, `partials/error.html`、htmx組み込み、
§10.4のデザイン適用、レート制限。

**完了条件**: 実URL (例: Wikipediaの記事ページ) を入力してプレビューが表示され、
ダウンロードしたHTMLが単体で正しく開く。全エラーケースで適切なメッセージが出る。

### フェーズ5: 仕上げ
`README.md` (セットアップ手順・環境変数・実行方法・既知の制限)、`ruff check --fix`、
`ruff format`、全テスト再実行。

---

## 15. 動作確認コマンド

```bash
uv sync
cp .env.example .env   # ANTHROPIC_API_KEY を記入
uv run pytest
uv run ruff check .
uv run uvicorn app.main:app --reload --port 8000
```

---

## 16. 将来拡張 (v1では実装しない)

- SSE (`htmx-ext-sse`) による生成のストリーミング表示
- Markdown / DOCX 形式でのダウンロード
- 複数URLをまとめて1本の記事にする
- 出力HTMLテーマの切り替え (雑誌風 / ドキュメント風)
- 生成履歴の保存 (SQLite + 共有リンク)

---

## 17. Claude Code への指示メモ

- 既存の慣習がない新規プロジェクトのため、この設計書を唯一の基準とすること。
- 設計書と矛盾する実装が必要になった場合は、実装を進める前に矛盾点を報告すること。
- 各フェーズの完了条件を満たしたことを確認してから次のフェーズへ進むこと。
- 秘密情報 (APIキー) をコードにハードコードしないこと。
- ファイルを大量に作る前に、まずフェーズ1の骨組みが起動することを確認すること。
