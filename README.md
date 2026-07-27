# kijiya (記事屋)

記事URLとプロンプトを入力すると、その記事の内容を素材として新しい記事を生成し、
ブラウザ上でプレビューして完成HTMLをダウンロードできるWebアプリケーション。

設計の詳細は [`docs/design.md`](docs/design.md) を参照。

## セットアップ

```bash
uv sync
cp .env.example .env   # ANTHROPIC_API_KEY を記入
```

## 環境変数

`.env` に設定する。詳細は [`.env.example`](.env.example) を参照。

| 変数名 | デフォルト | 説明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | (必須、記事生成時のみ) | Anthropic APIキー |
| `MODEL` | `claude-sonnet-5` | 生成に使うモデル |
| `MAX_TOKENS` | `8000` | LLM出力トークン上限 |
| `FETCH_TIMEOUT` | `15.0` | 記事URL取得タイムアウト(秒) |
| `MAX_DOWNLOAD_BYTES` | `3000000` | 取得HTMLの上限サイズ(バイト) |
| `MAX_SOURCE_CHARS` | `24000` | LLMへ渡す本文の最大文字数 |
| `DOC_TTL_SECONDS` | `1800` | 生成物の保持時間(秒) |
| `MAX_DOCS` | `200` | インメモリストアの最大件数 |
| `ALLOW_PRIVATE_HOSTS` | `False` | `True`でプライベートアドレスへのアクセスを許可 (ローカル検証用) |
| `RATE_LIMIT_PER_HOUR` | `30` | 同一IPからの生成回数上限 (1時間あたり) |

`ANTHROPIC_API_KEY` はアプリ起動やテストには不要(未設定でも起動・pytestは通る)。
実際に記事を生成するリクエスト (`POST /api/generate`) を送るときのみ必要。

## 実行方法

```bash
uv run uvicorn app.main:app --reload --port 8000
```

`http://localhost:8000/` にアクセスし、記事URLと指示を入力する。

## テスト・Lint

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## 既知の制限

- ユーザー認証・DB永続化・生成履歴の保存は行わない (v1のスコープ外)。生成物はメモリ上に
  `DOC_TTL_SECONDS` の間だけ保持され、プロセス再起動で消える。
- 複数URLの同時入力、PDF/画像の取り込みには対応していない。
- 生成のストリーミング表示は未実装 (将来拡張)。
- ログイン必須のページや動的レンダリング (JavaScript依存) のページは本文抽出に失敗する。
- レート制限・TTLストアはすべてインメモリのため、複数プロセス/複数インスタンスでは
  IPごとの制限や生成物が共有されない。単一プロセスでの運用を前提とする。
