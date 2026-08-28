FROM python:3.11-slim

WORKDIR /srv/app

# NFR-004: openssl generates the self-signed TLS cert at container start
# (docker-entrypoint.sh) - not present in python:3.11-slim by default.
RUN apt-get update && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000
# --insecure: this is our own self-signed cert (see docker-entrypoint.sh),
# not a real CA-issued one, so cert verification would always fail here -
# the healthcheck is confirming the process answers, not vetting its cert.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, ssl; urllib.request.urlopen('https://localhost:8000/health', context=ssl._create_unverified_context())" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--ssl-certfile", "/srv/app/certs/cert.pem", "--ssl-keyfile", "/srv/app/certs/key.pem"]
