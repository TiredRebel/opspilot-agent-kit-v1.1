FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev

COPY services/rag/app ./services/rag/app
COPY services/rag/prompts ./services/rag/prompts

ENV PATH="/app/.venv/bin:${PATH}"
ENV PYTHONPATH="/app/services/rag"

WORKDIR /app/services/rag
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
