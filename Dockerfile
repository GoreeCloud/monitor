FROM python:3.12-slim
WORKDIR /app
COPY monitor ./monitor
COPY web ./web
RUN useradd --system --uid 10001 --home-dir /data monitor && mkdir -p /data && chown 10001:10001 /data
USER 10001:10001
ENV GC_DATA_DIR=/data GC_HOST=0.0.0.0 GC_PORT=3001 GC_COOKIE_SECURE=1 PYTHONUNBUFFERED=1
EXPOSE 3001
VOLUME ["/data"]
CMD ["python", "-m", "monitor.server"]
