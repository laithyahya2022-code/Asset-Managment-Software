# ── Build stage ───────────────────────────────────────────────────────
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --no-audit --no-fund
COPY tsconfig*.json ./
COPY src ./src
RUN npm run build && npm prune --omit=dev

# ── Runtime stage ─────────────────────────────────────────────────────
FROM node:22-alpine
ENV NODE_ENV=production
WORKDIR /app
RUN addgroup -S itam && adduser -S itam -G itam
COPY --from=build --chown=itam:itam /app/node_modules ./node_modules
COPY --from=build --chown=itam:itam /app/dist ./dist
COPY --chown=itam:itam package.json ./
USER itam
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/api/v1/health || exit 1
CMD ["node", "dist/main.js"]
