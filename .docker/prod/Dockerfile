# ベースイメージ
FROM python:3.12-slim

# 作業ディレクトリ
WORKDIR /app

# 依存関係をコピー＆インストール
COPY ./app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションをコピー
COPY ./app/ .

# 本番用コマンド：Uvicorn単体で起動
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
