# syntax=docker/dockerfile:1
# Multi-stage build for Audible AI Web
# Stage 1: Dependencies
FROM node:22-alpine AS deps
WORKDIR /app

RUN apk add --no-cache python3 make g++ libc6-compat

COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

# Stage 2: Builder
FROM node:22-alpine AS builder
WORKDIR /app

RUN apk add --no-cache libc6-compat
COPY --from=deps /app/node_modules ./node_modules

COPY package*.json ./
COPY tsconfig.json ./
COPY next.config.ts ./
COPY components.json ./
COPY sentry.edge.config.ts ./
COPY sentry.server.config.ts ./
COPY postcss.config.mjs ./
COPY public ./public
COPY src ./src

ENV NEXT_PUBLIC_NODE_ENV="oss"
ENV NEXT_TELEMETRY_DISABLED="1"
ENV BACKEND_URL="http://api:8000"
ENV NODE_OPTIONS="--max-old-space-size=4096"

RUN npm run build && \
    rm -rf /tmp/* /root/.npm /root/.next/cache

# Stage 3: Runner (production image)
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3010

CMD ["sh", "-c", "echo '🚀 Audible AI ready at http://localhost:3010' && PORT=3010 node server.js"]
