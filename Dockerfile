FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DAHUER_MEDIA_DIR=/app/media DAHUER_MEDIA_AUTO_SYNC=true
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -r -u 10001 api
COPY app.py media_store.py ./
COPY data ./data
COPY site ./site
RUN mkdir -p /app/media && chown -R api:api /app/media
VOLUME ["/app/media"]
USER api
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
