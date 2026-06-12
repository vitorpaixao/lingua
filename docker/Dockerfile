FROM node:22-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g opencode-ai@latest

WORKDIR /

COPY entrypoint.sh /entrypoint.sh
COPY lingua-vite.config.mjs /lingua-vite.config.mjs
COPY exec_server.mjs /exec_server.mjs
RUN chmod +x /entrypoint.sh

EXPOSE 3000 4096 4097

ENTRYPOINT ["/entrypoint.sh"]
