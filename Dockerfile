FROM python:3.13-slim

WORKDIR /app

COPY . /app/

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV PATH="/root/.local/bin:${PATH}"
RUN uv sync --frozen
RUN ls -R /app

CMD ["uv", "run",  "/app/src/sensorthings_utils/main.py"]