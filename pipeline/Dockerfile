# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
WORKDIR /app

FROM base AS tooling
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_PREFERENCE=only-system UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./

FROM tooling AS migration-build
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --only-group database

FROM base AS migrate
ENV PATH=/opt/venv/bin:$PATH
COPY --from=migration-build /opt/venv /opt/venv
COPY alembic.ini ./
COPY db/migrations/ ./db/migrations/
USER app
ENTRYPOINT ["alembic"]
CMD ["upgrade", "head"]

FROM tooling AS worker-build
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --only-group worker
COPY pipeline/src/ ./pipeline/src/
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --python /opt/venv/bin/python --no-deps .

FROM base AS worker
ENV PATH=/opt/venv/bin:$PATH SAFETRIP_PROJECT_ROOT=/app SAFETRIP_DB_BACKEND=postgres \
    SAFETRIP_MODEL_PATH=/models/checkpoint-189 SAFETRIP_MODEL_MANIFEST=/app/model-manifest.json \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
COPY --from=worker-build /opt/venv /opt/venv
COPY docs/baseline/artifacts.json ./model-manifest.json
COPY tests/fixtures/advisories.xml tests/fixtures/bert_predictions.json ./fixtures/
RUN mkdir /output && chown app:app /output
USER app
ENTRYPOINT ["safetrip"]
CMD ["--help"]
