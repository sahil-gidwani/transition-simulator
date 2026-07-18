# syntax=docker/dockerfile:1
# Built from the repo root: docker build -f client/Dockerfile .
FROM node:22-bookworm-slim AS build

# Optional extra root CAs for TLS-inspecting proxies (see docker/certs/README.md).
# node-slim ships no trust-store tooling, so install it; the extras directory
# holds only a README by default and update-ca-certificates ignores non-.crt files.
COPY docker/certs/ /usr/local/share/ca-certificates/extra/
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates
ENV NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt

WORKDIR /repo
# npm workspace: the only lockfile lives at the repo root. --ignore-scripts
# skips the husky prepare hook (needs .git); platform binaries are
# optionalDependencies and still install.
COPY package.json package-lock.json ./
COPY client/package.json client/
RUN npm ci --ignore-scripts
COPY client/ client/
RUN npm run build -w client

FROM nginx:1.29-alpine
COPY client/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/client/dist/ /usr/share/nginx/html/
EXPOSE 80
