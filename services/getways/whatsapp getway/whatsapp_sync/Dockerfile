# Use a minimal Node.js base with Alpine
FROM node:18-alpine

# Create app group and user early
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Set working directory
WORKDIR /app

# Install system dependencies for Puppeteer and Chromium
RUN apk add --no-cache \
    chromium \
    nss \
    freetype \
    harfbuzz \
    ca-certificates \
    ttf-freefont \
    dumb-init

# Ensure logs and node_modules directories exist with correct ownership
RUN mkdir -p /app/logs /app/node_modules \
 && chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Copy dependencies file and install only production deps plus Puppeteer
COPY --chown=appuser:appgroup package*.json ./
RUN npm install --omit=dev && npm install puppeteer

# Copy application source code
COPY --chown=appuser:appgroup . .

# Expose the sync service port
EXPOSE 8080

# Proper init handling
ENTRYPOINT ["dumb-init", "--"]

# Start the sync service
CMD ["node", "sync_api.js"]
