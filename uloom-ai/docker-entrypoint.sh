#!/bin/sh
# Runs on every container start, not just first deploy - `alembic upgrade
# head` is a no-op when already at head, so this is safe to repeat and
# means the image never needs a separate manual migration step.
set -e

# NFR-004: HTTPS enforced end-to-end. Self-signed, generated here rather
# than baked into the image or repo, so it's regenerated per-container and
# never committed - see the Dockerfile HEALTHCHECK comment for why the
# healthcheck itself skips cert verification. A real deployment terminates
# TLS at a load balancer/ingress with a CA-issued certificate instead.
CERT_DIR=/srv/app/certs
if [ ! -f "$CERT_DIR/cert.pem" ] || [ ! -f "$CERT_DIR/key.pem" ]; then
    mkdir -p "$CERT_DIR"
    openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
        -keyout "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.pem" \
        -subj "/CN=localhost"
fi

alembic upgrade head
exec "$@"
