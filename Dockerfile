FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install . \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin gqmrmed \
    && mkdir -p /data/results /tmp/gqmrmed-media \
    && chown -R gqmrmed:gqmrmed /app /data /tmp/gqmrmed-media

USER gqmrmed

EXPOSE 8000

CMD ["python", "-m", "gqmrmed"]
