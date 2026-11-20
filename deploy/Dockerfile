FROM python:3.13-slim
WORKDIR /app
RUN groupadd -g 65532 monitor && useradd -u 65532 -g 65532 -s /usr/sbin/nologin monitor \
    && mkdir -p /data && chown 65532:65532 /data
COPY service/monitor.py /app/monitor.py
USER 65532:65532
ENV PYTHONUNBUFFERED=1 MONITOR_DB=/data/monitor.db MONITOR_HOST=0.0.0.0
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/healthz',timeout=3)"
CMD ["python", "/app/monitor.py"]
