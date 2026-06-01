# --- build stage ---
FROM node:22-slim AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
# Disable MSW in the production build
ENV VITE_USE_MSW=false
RUN npm run build && rm -f /app/dist/mockServiceWorker.js

# --- runtime stage ---
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
