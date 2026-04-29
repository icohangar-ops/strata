# Strata production image — runs the Streamlit UI by default.
# Override CMD to run the CLI: docker run strata strata --help

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build deps for psycopg + cleanup in same layer
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
COPY samples ./samples
COPY src/strata/rubrics ./src/strata/rubrics

RUN pip install --upgrade pip \
 && pip install ".[ui,llm]"

# ---- runtime ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STRATA_LLM_BACKEND=openai \
    STRATA_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1 \
    STRATA_GRADER_MODEL=qwen3.6-flash \
    STRATA_AUTHOR_MODEL=qwen3.6-flash

WORKDIR /app

# Runtime libpq for psycopg
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/*

# Copy installed packages and source
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Streamlit config (theme + headless server)
COPY .streamlit /app/.streamlit
COPY streamlit_app.py /app/streamlit_app.py
COPY NOTICE /app/NOTICE

# Non-root user
RUN useradd --create-home --shell /bin/bash strata \
 && chown -R strata:strata /app
USER strata

# Railway provides $PORT; default to 8501 for local docker run.
EXPOSE 8501
ENV PORT=8501

# HEALTHCHECK relies on Streamlit's /_stcore/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,os; \
urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",\"8501\")}/_stcore/health', timeout=3)" \
  || exit 1

CMD streamlit run streamlit_app.py \
    --server.port=${PORT} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
