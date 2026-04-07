FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir build && \
    python -m build --wheel --outdir dist/

FROM python:3.12-slim

RUN groupadd --gid 1000 olp && \
    useradd --uid 1000 --gid olp --create-home olp

WORKDIR /app

COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm -rf /tmp/*.whl

RUN mkdir -p /data && chown olp:olp /data

USER olp

ENV OLP_DB_PATH=/data/ollama-logs.db
ENV OLP_PORT=11433

EXPOSE 11433 8080 9090

ENTRYPOINT ["ollama-log-proxy"]
CMD ["--dashboard", "8080", "--metrics-port", "9090"]
