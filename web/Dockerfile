# --- build stage ---
FROM node:22-slim AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
# Harden against flaky networks / proxies that reset long connections (ECONNRESET):
# more retries, longer timeouts, and one socket at a time (slower but resilient).
RUN npm config set fetch-retries 5 \
 && npm config set fetch-retry-factor 2 \
 && npm config set fetch-retry-mintimeout 10000 \
 && npm config set fetch-retry-maxtimeout 120000 \
 && npm config set fetch-timeout 600000 \
 && npm ci --no-audit --no-fund --maxsockets 1
COPY . .
# Disable MSW in the production build
ENV VITE_USE_MSW=false
RUN npm run build && rm -f /app/dist/mockServiceWorker.js

# --- runtime stage ---
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
