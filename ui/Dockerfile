FROM node:20-bullseye-slim

WORKDIR /app

# Manifests first for layer caching
COPY ui/package*.json ./

# Install deps; fallback if no lockfile
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

# Copy the rest
COPY ui/ .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
