FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000 WORKBENCH_ONLINE=1 WORKBENCH_DATA_DIR=/data
WORKDIR /app
RUN groupadd --gid 10001 workbench && useradd --uid 10001 --gid workbench --no-create-home workbench && mkdir /data && chown workbench:workbench /data
COPY --chown=workbench:workbench app.py access.py ./
COPY --chown=workbench:workbench static/ ./static/
USER workbench
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
CMD ["python", "app.py"]
