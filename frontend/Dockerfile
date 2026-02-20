# Use Node 18 Alpine
FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
# Using npm install for dev (fast)
RUN npm install

# Copy source
COPY . .

# Expose port 3000
EXPOSE 3000

# Start dev server
CMD ["npm", "run", "dev"]
