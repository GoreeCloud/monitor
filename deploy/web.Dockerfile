FROM node:24-alpine AS builder
WORKDIR /build
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY apps/web/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine
COPY deploy/web.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist/ /usr/share/nginx/html/
EXPOSE 8080
USER 101:101
HEALTHCHECK --interval=30s --timeout=5s CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
