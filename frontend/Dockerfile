# Multi-stage: Node builds the bundle, nginx serves it. The runtime image
# carries no Node, no node_modules, and no source — just static files and a web
# server, which is both far smaller and a much smaller attack surface.

FROM node:26-alpine AS builder

WORKDIR /build

# package files alone first: this layer stays cached until dependencies
# actually change, rather than invalidating on every source edit.
COPY package.json package-lock.json ./
# `npm ci` rather than `install`: it installs exactly the lockfile, so a build
# can never silently pick up a newer transitive dependency than the one tested.
RUN npm ci

COPY . .

# Vite inlines env vars at build time, so the API base must be known here
# rather than at container start. It defaults to a relative path served through
# this image's own nginx proxy; override only for a deployment that puts the
# API on a different origin.
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Type errors fail the image build. A container that ships despite them just
# moves the failure to the browser.
RUN npm run build


FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# The unprivileged image already runs as a non-root user (uid 101) and listens
# on 8080, so no user juggling is needed here.

COPY --chown=nginx:nginx nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder --chown=nginx:nginx /build/dist /usr/share/nginx/html

EXPOSE 8080

# Hits the server's own /healthz, which is terminated by nginx, so the frontend
# does not report unhealthy merely because the backend is still starting.
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD ["/bin/sh", "-c", "wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1"]
