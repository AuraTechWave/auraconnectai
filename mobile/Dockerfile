# Base image for React Native development
FROM node:18-alpine AS base

# Install basic dependencies
RUN apk add --no-cache \
    bash \
    git \
    openssh \
    python3 \
    make \
    g++

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./
COPY yarn.lock* ./

# Install dependencies
RUN yarn install --frozen-lockfile || npm ci

# Copy source code
COPY . .

# Development stage
FROM base AS development

# Expose Metro bundler port
EXPOSE 8081

# Start Metro bundler
CMD ["yarn", "start"]

# Build stage for production bundles
FROM base AS builder

# Build the app bundles
RUN yarn build:android && yarn build:ios

# Production stage (for serving built files)
FROM nginx:alpine AS production

# Copy built files
COPY --from=builder /app/android/app/build/outputs/apk/release/*.apk /usr/share/nginx/html/
COPY --from=builder /app/ios/build/*.ipa /usr/share/nginx/html/

# Add a simple index.html
RUN echo '<!DOCTYPE html><html><head><title>AuraConnect Mobile Builds</title></head><body><h1>AuraConnect Mobile App Builds</h1><ul><li><a href="app-release.apk">Android APK</a></li><li><a href="AuraConnect.ipa">iOS IPA</a></li></ul></body></html>' > /usr/share/nginx/html/index.html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
