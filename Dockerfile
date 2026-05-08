FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INVENTORY_HOST=0.0.0.0 \
    INVENTORY_PORT=5000 \
    INVENTORY_DATABASE_PATH=/data/inventory.db \
    INVENTORY_UPLOADS_DIR=/data/uploads \
    INVENTORY_INSTANCE_PATH=/data/instance

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY app.py ./app.py
COPY docker_wsgi.py ./docker_wsgi.py
COPY pondsec_ai ./pondsec_ai
COPY static ./static
COPY templates ./templates
COPY LICENSE ./LICENSE

VOLUME ["/data"]

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/login', timeout=3).read()" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "docker_wsgi:application"]
