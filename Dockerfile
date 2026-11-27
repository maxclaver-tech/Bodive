FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY bodive ./bodive
RUN pip install --no-cache-dir ".[cloud]" && useradd --create-home --uid 10001 bodive
USER bodive
CMD ["bodive", "serve"]
