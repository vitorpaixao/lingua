FROM node:20-slim

RUN npm install -g opencode-ai@latest

COPY vite-template/ /template/

WORKDIR /template
RUN npm install

COPY opencode.json /template/opencode.json

WORKDIR /project

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3000 4096

ENTRYPOINT ["/entrypoint.sh"]
