# stage 1: frontend build — replicates the repo layout because
# frontend/vite.config.ts emits to ../backend/dmarcayn/static
FROM node:22-alpine AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# stage 2: runtime
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY backend/ backend/
COPY --from=frontend /src/backend/dmarcayn/static backend/dmarcayn/static
RUN pip install --no-cache-dir . \
 && useradd --system --create-home --home-dir /data dmarcayn \
 && chown dmarcayn /data
USER dmarcayn
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/sync/status', timeout=4)"]
CMD ["dmarcayn", "--config", "/config/config.ini"]
