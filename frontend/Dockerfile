# Stage 0, "build-stage", based on Node.js, to build and compile the frontend
FROM node:24-alpine AS build-stage

WORKDIR /app

# Copy package files for better layer caching
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build arguments baked into the Vite bundle
ARG VITE_API_URL
ARG VITE_API_TIMEOUT_MS=30000
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_API_TIMEOUT_MS=${VITE_API_TIMEOUT_MS}

# Build the application
RUN npm run build


# Stage 1, based on Nginx, to have only the compiled app, ready for production with Nginx
FROM nginx:1.29-alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy built assets from build stage
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Copy nginx configuration files
COPY ./nginx/index.conf /etc/nginx/conf.d/default.conf


# Expose port 80
EXPOSE 80

# Health check
# 127.0.0.1: localhost ::1 ga resolve bo'lib IPv4-only nginx'da unhealthy berardi
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
