#!/bin/sh
# NFR-004: HTTPS enforced end-to-end. Dropped into /docker-entrypoint.d/,
# the nginx:alpine base image's own hook directory - its default entrypoint
# runs every script there before starting nginx, so this only needs to
# generate the cert, not exec nginx itself.
#
# Generates a self-signed cert on first start if one isn't already present -
# never baked into the image or the repo, so it's regenerated per-container
# and never committed. This is a local/dev-appropriate cert (see
# nginx.conf); a real deployment terminates TLS at a load balancer/ingress
# with a CA-issued certificate instead.
set -e

CERT_DIR=/etc/nginx/certs
if [ ! -f "$CERT_DIR/cert.pem" ] || [ ! -f "$CERT_DIR/key.pem" ]; then
    mkdir -p "$CERT_DIR"
    openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
        -keyout "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.pem" \
        -subj "/CN=localhost"
fi
