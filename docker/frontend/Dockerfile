# ── Frontend (Nginx static file server + reverse proxy) ──────
FROM nginx:1.25-alpine

LABEL description="Frontend — Nginx + Static Assets"

# Copy nginx config (path relative to project root build context)
COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy static assets into Nginx serving directory
COPY app/frontend/static /usr/share/nginx/html/static

EXPOSE 80

HEALTHCHECK --interval=20s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost/nginx-health || exit 1
