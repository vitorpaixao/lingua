FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev
COPY lingua ./lingua
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "lingua.app:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--timeout-keep-alive", "600"]
