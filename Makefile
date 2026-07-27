.DEFAULT_GOAL := help

.PHONY: help install run dev test lint format format-check fix check clean

help: ## このヘルプを表示
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## 依存パッケージをインストール
	uv sync --dev

run: ## 開発サーバーを起動 (http://localhost:8000)
	uv run uvicorn app.main:app --reload --port 8000

test: ## テストを実行
	uv run pytest

lint: ## ruffでlintチェック
	uv run ruff check .

format: ## ruffでフォーマット
	uv run ruff format .

format-check: ## ruffのフォーマット差分チェックのみ (変更しない)
	uv run ruff format --check .

fix: ## ruffでlintエラーを自動修正しフォーマットも適用
	uv run ruff check --fix .
	uv run ruff format .

check: lint format-check test ## CIと同じ一連のチェック (lint + format-check + test)

clean: ## キャッシュ類を削除
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} +
