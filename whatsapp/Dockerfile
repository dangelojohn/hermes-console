# whatsapp-web.js drives a headless Chrome under the hood (puppeteer), so the
# image needs Chrome + its system deps. Using the official puppeteer image so
# we don't reinvent the apt-install list.
FROM ghcr.io/puppeteer/puppeteer:23.10.4

USER root
WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev && npm cache clean --force

COPY bridge.js ./

# Persistent session lives at /data (mounted volume in compose). Puppeteer
# image's pptruser owns it once compose chowns the mount.
ENV WHATSAPP_SESSION_PATH=/data/whatsapp-session
USER pptruser

EXPOSE 8901
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
  CMD wget -qO- http://127.0.0.1:8901/health > /dev/null 2>&1 || exit 1

CMD ["node", "bridge.js"]
