FROM node:24-alpine AS build-stage

WORKDIR /app

# Copy package files for better layer caching
COPY package*.json ./

RUN npm ci

COPY . .

# Build arguments baked into the Vite bundle
ARG VITE_API_URL
ARG VITE_API_TIMEOUT_MS=30000
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_API_TIMEOUT_MS=${VITE_API_TIMEOUT_MS}

RUN npm run build


FROM nginx:1.29-alpine

RUN rm /etc/nginx/conf.d/default.conf

COPY --from=build-stage /app/dist /usr/share/nginx/html

COPY ./nginx/index.conf /etc/nginx/conf.d/default.conf


EXPOSE 80

# 127.0.0.1: localhost ::1 ga resolve bo'lib IPv4-only nginx'da unhealthy berardi
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
