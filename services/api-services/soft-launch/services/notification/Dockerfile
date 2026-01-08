FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --omit=dev

COPY . .

ENV PORT=8561
EXPOSE 8561

CMD ["node", "app.js"]
