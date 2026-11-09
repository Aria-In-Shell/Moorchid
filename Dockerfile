FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY UI/package*.json ./
RUN npm ci
COPY UI/ ./
ENV VITE_API_BASE_URL=/api
RUN npm run build

FROM python:3.11-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 ENVIRONMENT=production DATABASE_URL=/data/journal.db CHROMA_PERSIST_DIR=/data/chroma PORT=8000
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home moorchid && install -d -o moorchid -g moorchid /data
COPY agents.py config.py embeddings.py main.py memory_schema.py models.py vector_store.py ./
COPY --from=web /web/dist ./UI/dist
USER moorchid
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port \"$PORT\""]
